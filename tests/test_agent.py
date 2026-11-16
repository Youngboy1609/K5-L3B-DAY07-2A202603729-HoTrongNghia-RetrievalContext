import json
import unittest
from decimal import Decimal

from src.agent import Agent, TOOLS


class FakeClient:
    model = "test/model"
    provider = "test-provider"

    def __init__(self, turns):
        self.turns = iter(turns)
        self.tool_schemas = []
        self.messages = []

    def chat(self, messages, **kwargs):
        self.tool_schemas.append(kwargs.get("tools", []))
        self.messages.append(json.loads(json.dumps(messages)))
        return type("Response", (), {"data": next(self.turns), "cost_usd": Decimal("0.001"), "elapsed_ms": 1.0})()


def response(message, reason="stop"):
    return {"choices": [{"finish_reason": reason, "message": message}]}


class AgentTests(unittest.TestCase):
    def test_second_search_has_room_and_full_ranking_is_preserved(self):
        rows = [{"id": f"a{i}", "text": "x" * 750, "source": "doc", "page": i} for i in range(12)]
        client = FakeClient([])
        agent = Agent(client, lambda *args: rows if args[1] == "first" else [
            {"id": "hop2", "text": "second hop evidence", "source": "doc", "page": 20}],
            lambda q: [], context_budget=4000)
        allowed, retrieved = {}, {}
        first = agent._dispatch("search", {"query": "first"}, "H2", allowed, set(),
                                suite="bonus", retrieved=retrieved)
        second = agent._dispatch("search", {"query": "second"}, "H2", allowed, set(),
                                 suite="bonus", retrieved=retrieved, search_number=2)
        self.assertEqual(len(first["ranked_ids"]), 12)
        self.assertIn("hop2", second["evidence_ids"])

    def test_visual_open_accepts_retrieved_unpacked_candidate_without_unsent_text(self):
        row = {"id": "candidate", "text": "not sent to model", "source": "doc", "page": 1}
        agent = Agent(FakeClient([]), lambda *args: [], lambda q: [],
                      lambda cid: {"id": cid, "page": 1, "image_url": "data:image/png;base64,AA=="})
        allowed = {}
        result = agent._dispatch("open_region", {"id": "candidate"}, "H2", allowed, set(),
                                 suite="bonus", retrieved={"candidate": row})
        self.assertIn("region", result)
        self.assertEqual(allowed["candidate"]["text"], "")
        self.assertTrue(allowed["candidate"]["visual_opened"])

    def test_search_cap_replies_to_every_tool_call_in_batch(self):
        calls = [{"id": f"c{i}", "type": "function", "function": {
            "name": "search", "arguments": '{"query":"q"}'}} for i in range(6)]
        client = FakeClient([response({"role": "assistant", "tool_calls": calls}, "tool_calls"),
                             response({"role": "assistant", "content": "Insufficient evidence."})])
        Agent(client, lambda *args: [], lambda q: []).run("question")
        replies = [m["tool_call_id"] for m in client.messages[-1] if m["role"] == "tool"]
        self.assertEqual(replies, [c["id"] for c in calls])

    def test_clear_first_person_refusal_does_not_require_citation_repair(self):
        client = FakeClient([response({"role": "assistant", "content":
            "The search results do not include the requested figure. I cannot provide the requested value."})])
        result = Agent(client, lambda *args: [], lambda q: []).run("Unsupported question")
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["errors"], [])
        self.assertFalse(any(e.get("type") == "citation_repair" for e in result["events"]))

    def test_missing_citation_gets_one_bounded_repair(self):
        search = response({"role": "assistant", "tool_calls": [{"id": "s", "type": "function",
            "function": {"name": "search", "arguments": '{"query":"chart"}'}}]}, "tool_calls")
        client = FakeClient([search, response({"role": "assistant", "content": "Orange excludes China."}),
            response({"role": "assistant", "content": "Orange excludes China [E:e1]."})])
        rows = [{"id": "e1", "text": "Orange excludes China", "source": "doc", "page": 1}]
        t = Agent(client, lambda *args: rows, lambda q: []).run("Which series?")
        self.assertEqual(t["citations"], ["e1"])
        self.assertEqual(t["errors"], [])
        self.assertEqual(client.tool_schemas[-1], [])
        self.assertTrue(any(e.get("type") == "citation_repair" for e in t["events"]))

    def test_failed_citation_repair_abstains_without_inventing_citation(self):
        search = response({"role": "assistant", "tool_calls": [{"id": "s", "type": "function",
            "function": {"name": "search", "arguments": '{"query":"chart"}'}}]}, "tool_calls")
        client = FakeClient([search, response({"role": "assistant", "content": "Orange excludes China."}),
            response({"role": "assistant", "content": "Orange excludes China."})])
        rows = [{"id": "e1", "text": "Orange excludes China", "source": "doc", "page": 1}]
        t = Agent(client, lambda *args: rows, lambda q: []).run("Which series?")
        self.assertEqual(t["status"], "abstain")
        self.assertIn("citation_missing", t["errors"])
        self.assertEqual(t["citations"], [])
        self.assertEqual(len(client.messages), 3)

    def test_open_region_image_is_sent_as_image_part_and_not_tool_text(self):
        client = FakeClient([
            response({"role": "assistant", "tool_calls": [{"id": "s1", "type": "function", "function": {
                "name": "search", "arguments": '{"query":"figure"}'}}]}, "tool_calls"),
            response({"role": "assistant", "tool_calls": [{"id": "o1", "type": "function", "function": {
                "name": "open_region", "arguments": '{"id":"e1"}'}}]}, "tool_calls"),
            response({"role": "assistant", "content": "The figure shows evidence [E:e1]."}),
        ])
        rows = [{"id": "e1", "text": "Figure region", "source": "report", "page": 4, "metadata": {}}]
        agent = Agent(client, lambda *args: rows, lambda q: [0.0],
                      lambda cid: {"id": cid, "page": 4, "image_url": "data:image/png;base64,AA=="})
        result = agent.run("What does the figure show?", suite="bonus")
        sent = client.messages[-1]
        parts = [part for message in sent if isinstance(message.get("content"), list)
                 for part in message["content"]]
        self.assertEqual(sum(part.get("type") == "image_url" for part in parts), 1)
        self.assertFalse(any("base64" in str(message.get("content")) for message in sent
                             if message.get("role") == "tool"))
        self.assertNotIn("base64", json.dumps(result))

    def test_native_search_tool_roundtrip_preserves_id_and_validates_citation(self):
        rows = [{"id": "e1", "text": "A tuple is immutable.", "source": "book.pdf", "page": 3,
                 "metadata": {}, "score": 0.9}]
        client = FakeClient([
            response({"role": "assistant", "tool_calls": [{"id": "tc1", "type": "function", "function": {
                "name": "search", "arguments": json.dumps({"query": "tuple"})}}]}, "tool_calls"),
            response({"role": "assistant", "content": "A tuple is immutable [E:e1]."}),
        ])
        agent = Agent(client, lambda m, q, v, f, k: rows, lambda q: [0.0] * 1024)
        result = agent.run("What is a tuple?", query_id="q1")
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["citations"], ["e1"])
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["cost_usd"], "0.002")
        self.assertEqual(result["errors"], [])
        self.assertTrue(any(t["function"]["name"] == "open_region" for t in TOOLS))
        self.assertNotIn("method", TOOLS[0]["function"]["parameters"]["properties"])
        self.assertEqual([tool["function"]["name"] for tool in client.tool_schemas[0]], ["search"])

    def test_bonus_search_schema_does_not_expose_core_chapter_filter(self):
        client = FakeClient([response({"role": "assistant", "content": "Insufficient evidence."})])
        agent = Agent(client, lambda *args: [], lambda q: [0.0] * 1024)

        agent.run("Question?", suite="bonus", config="D0")

        search = client.tool_schemas[0][0]["function"]
        self.assertNotIn("chapter", search["parameters"]["properties"])

    def test_unknown_tool_is_rejected_and_does_not_call_search(self):
        client = FakeClient([
            response({"role": "assistant", "tool_calls": [{"id": "tc1", "type": "function", "function": {
                "name": "delete_files", "arguments": "{}"}}]}, "tool_calls"),
            response({"role": "assistant", "content": "Insufficient evidence to answer."}),
        ])
        called = []
        agent = Agent(client, lambda *args: called.append(args) or [], lambda q: [])
        result = agent.run("Question?")
        self.assertEqual(called, [])
        self.assertEqual(result["status"], "abstain")
        self.assertTrue(result["errors"])

    def test_model_cannot_change_retrieval_method_fixed_by_config(self):
        client = FakeClient([
            response({"role": "assistant", "tool_calls": [{"id": "tc1", "type": "function", "function": {
                "name": "search", "arguments": json.dumps({"query": "tuple", "method": "H2"})}}]}, "tool_calls"),
            response({"role": "assistant", "content": "Insufficient evidence to answer."}),
        ])
        called = []
        agent = Agent(client, lambda *args: called.append(args) or [], lambda q: [0.0] * 1024)
        result = agent.run("Question?", config="D0")
        self.assertEqual(called, [])
        self.assertTrue(result["errors"])

    def test_search_limit_stops_model_loop_and_returns_abstention(self):
        calls = [{"id": f"tc{i}", "type": "function", "function": {
            "name": "search", "arguments": json.dumps({"query": f"query {i}"})}} for i in range(6)]
        client = FakeClient([response({"role": "assistant", "tool_calls": calls}, "tool_calls"),
                             response({"role": "assistant", "content": "Insufficient evidence to answer."})])
        dispatched = []
        agent = Agent(client, lambda *args: dispatched.append(args) or [], lambda q: [0.0] * 1024,
                      max_search_calls=4)
        result = agent.run("Question?", config="D0")
        self.assertEqual(len(dispatched), 4)
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["warnings"], ["maximum_search_calls_reached"])
        self.assertEqual(len(result["latency_ms"]["model_calls"]), 2)
        self.assertEqual(client.tool_schemas[1], [])

    def test_search_limit_is_not_mislabeled_as_tool_validation_error(self):
        calls = [{"id": f"tc{i}", "type": "function", "function": {
            "name": "search", "arguments": json.dumps({"query": f"query {i}"})}} for i in range(5)]
        client = FakeClient([response({"role": "assistant", "tool_calls": calls}, "tool_calls"),
                             response({"role": "assistant", "content": "Insufficient evidence."})])
        agent = Agent(client, lambda *args: [], lambda q: [0.0] * 1024, max_search_calls=4)

        result = agent.run("Question?", config="D0")

        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["warnings"], ["maximum_search_calls_reached"])
        limit_events = [e for e in result["events"] if e.get("error")]
        self.assertEqual(limit_events[-1]["error"], "search_limit_reached")

    def test_search_limit_allows_one_final_answer_without_tools(self):
        calls = [{"id": f"tc{i}", "type": "function", "function": {
            "name": "search", "arguments": json.dumps({"query": f"query {i}"})}} for i in range(5)]
        client = FakeClient([
            response({"role": "assistant", "tool_calls": calls}, "tool_calls"),
            response({"role": "assistant", "content": "Evidence answers the question [E:e1]."}),
        ])
        rows = [{"id": "e1", "text": "Evidence", "source": "book.pdf", "page": 1, "metadata": {}}]
        agent = Agent(client, lambda *args: rows, lambda q: [0.0] * 1024, max_search_calls=4)

        result = agent.run("Question?", config="D0")

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["warnings"], ["maximum_search_calls_reached"])
        self.assertEqual(result["tool_calls"], 5)
        self.assertEqual(client.tool_schemas[1], [])

    def test_explicit_must_abstain_language_sets_abstain_status(self):
        client = FakeClient([response({"role": "assistant", "content":
                                      "The retrieved passage does not cover this. I must abstain."})])
        agent = Agent(client, lambda *args: [], lambda q: [])

        result = agent.run("Question?")

        self.assertEqual(result["status"], "abstain")

    def test_citation_outside_context_is_flagged(self):
        client = FakeClient([response({"role": "assistant", "content": "Answer [E:invented]."})])
        agent = Agent(client, lambda *args: [], lambda q: [])
        result = agent.run("Question?")
        self.assertIn("citation_outside_retrieved_context", result["errors"])

    def test_page_annotation_is_checked_against_retrieved_metadata(self):
        client = FakeClient([
            response({"role": "assistant", "tool_calls": [{"id": "tc1", "type": "function", "function": {
                "name": "search", "arguments": json.dumps({"query": "query"})}}]}, "tool_calls"),
            response({"role": "assistant", "content": "Answer [E:e1, p. 99]."}),
        ])
        rows = [{"id": "e1", "text": "Evidence", "source": "book.pdf", "page": 3, "metadata": {}}]
        agent = Agent(client, lambda *args: rows, lambda q: [0.0] * 1024)
        result = agent.run("Question?")
        self.assertEqual(result["citations"], ["e1"])
        self.assertIn("citation_page_mismatch", result["errors"])

    def test_open_region_requires_previously_retrieved_id(self):
        client = FakeClient([
            response({"role": "assistant", "tool_calls": [{"id": "tc1", "type": "function", "function": {
                "name": "open_region", "arguments": '{"id":"arbitrary-path"}'}}]}, "tool_calls"),
            response({"role": "assistant", "content": "Insufficient evidence to answer."}),
        ])
        opened = []
        agent = Agent(client, lambda *args: [], lambda q: [], lambda cid: opened.append(cid))
        result = agent.run("Question?")
        self.assertEqual(opened, [])
        self.assertTrue(result["errors"])

    def test_open_region_obeys_image_token_budget(self):
        agent = Agent(FakeClient([]), lambda *args: [], lambda q: [],
                      lambda cid: {"image_url": "data:image/png;base64,AA=="},
                      context_budget=20_000, max_regions=0)
        with self.assertRaises(ValueError):
            agent._dispatch("open_region", {"id": "e1"}, "D0",
                             {"e1": {"id": "e1", "text": "short", "page": 1}}, set())


if __name__ == "__main__":
    unittest.main()
