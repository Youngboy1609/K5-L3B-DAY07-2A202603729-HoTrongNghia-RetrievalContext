import unittest

from src.evaluation import source_aware_metrics, retrieval_metrics, source_aware_evidence_match, validate_benchmark


def fixtures():
    chunk = {"id": "c1", "text": "Evidence quote", "source_id": "doc", "page": 1, "metadata": {}}
    rows = []
    for split, answers, absent in (("dev", 16, 2), ("test", 6, 2)):
        for i in range(answers):
            rows.append({"id": f"{split}-a{i}", "split": split, "answerable": True,
                         "question": f"Question {split} {i}?", "expected_answer": "answer",
                         "gold": [{"source_id": "doc", "page": 1, "chunk_id": "c1", "evidence": "Evidence quote"}]})
        for i in range(absent):
            rows.append({"id": f"{split}-u{i}", "split": split, "answerable": False,
                         "question": f"Absent {split} {i}?", "expected_answer": None, "gold": [],
                         "absence_reason": "searched the full corpus"})
    return rows, [chunk]


class EvaluationTests(unittest.TestCase):
    def test_source_aware_match_accepts_child_only_when_quote_is_present(self):
        gold = {"chunk_id": "parent", "source_id": "doc", "page": 1, "evidence": "needed fact"}
        good = [{"id": "parent-part-01", "parent_id": "parent", "source": "doc", "page": 1,
                 "text": "context needed fact more"}]
        sibling = [{"id": "parent-part-02", "parent_id": "parent", "source": "doc", "page": 1,
                    "text": "other unrelated details"}]
        wrong_page = [{**good[0], "page": 2}]
        self.assertTrue(source_aware_evidence_match(gold, good))
        self.assertFalse(source_aware_evidence_match(gold, sibling))
        self.assertFalse(source_aware_evidence_match(gold, wrong_page))

    def test_wrong_source_title_cannot_satisfy_other_document(self):
        gold = {"chunk_id": "p", "source_id": "other", "page": 1, "evidence": "fact"}
        self.assertFalse(source_aware_evidence_match(gold, [{"id": "p", "source":
            "World Development Report 2024", "page": 1, "text": "fact"}]))

    def test_source_metrics_accept_child_but_require_both_hops(self):
        gold = [{"chunk_id": "p", "source_id": "doc", "page": 1, "evidence": "fact"},
                {"chunk_id": "b", "source_id": "doc", "page": 2, "evidence": "second"}]
        child = {"id": "p-part-01", "parent_id": "p", "source_id": "doc", "page": 1, "text": "fact"}
        t = {"query_id": "q", "contexts": [child], "events": [{"name": "search", "type": "tool",
             "ranked_ids": ["p-part-01"]}]}
        m = source_aware_metrics([{"id": "q", "answerable": True, "gold": gold}], [t], [child])
        self.assertEqual(m["hit_at_1"]["n"], 1)
        self.assertEqual(m["context_evidence_rate"]["n"], 0)

    def test_source_metrics_never_restore_unsent_text_from_corpus(self):
        child = {"id": "p-part-01", "parent_id": "p", "source_id": "doc", "page": 1, "text": "fact"}
        trace = {"query_id": "q", "events": [], "contexts": [{**child, "text": "", "visual_opened": True}]}
        question = {"id": "q", "answerable": True, "gold": [
            {"chunk_id": "p", "source_id": "doc", "page": 1, "evidence": "fact"}]}
        self.assertEqual(source_aware_metrics([question], [trace], [child])["context_evidence_rate"]["n"], 0)

    def test_core_counts_and_source_evidence_are_validated(self):
        rows, chunks = fixtures()
        self.assertEqual(validate_benchmark(rows, chunks, suite="core")["total"], 26)
        rows[0]["gold"][0]["evidence"] = "not present"
        with self.assertRaises(ValueError):
            validate_benchmark(rows, chunks, suite="core")

    def test_unanswerable_must_have_absence_reason(self):
        rows, chunks = fixtures()
        rows[-1].pop("absence_reason")
        with self.assertRaises(ValueError):
            validate_benchmark(rows, chunks, suite="core")

    def test_multihop_retrieval_requires_all_evidence_in_context(self):
        question = {"id": "q", "answerable": True,
                    "gold": [{"chunk_id": "a"}, {"chunk_id": "b"}]}
        trace = {"query_id": "q", "events": [{"type": "tool", "name": "search", "evidence_ids": ["a", "b", "x"]}],
                 "contexts": [{"id": "a"}]}
        result = retrieval_metrics([question], [trace])
        self.assertEqual(result["hit_at_1"]["n"], 1)
        self.assertEqual(result["evidence_hit_at_3"]["n"], 1)
        self.assertEqual(result["context_evidence_rate"]["n"], 0)


if __name__ == "__main__":
    unittest.main()
