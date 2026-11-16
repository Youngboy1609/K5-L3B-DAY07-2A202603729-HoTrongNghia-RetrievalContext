import unittest

from src.context import pack_context


def row(chunk_id, text):
    return {"id": chunk_id, "source": "source.pdf", "page": 12, "text": text}


class ContextPackingTests(unittest.TestCase):
    def test_preserves_source_and_deduplicates_ids(self):
        result = pack_context([row("c1", "evidence"), row("c1", "duplicate")],
                              budget_tokens=100, overhead_tokens=5)
        self.assertEqual(result["ids"], ["c1"])
        self.assertIn("source.pdf | page 12", result["text"])

    def test_does_not_truncate_chunks_or_exceed_estimated_budget(self):
        rows = [row("large", "x" * 300), row("small", "fact")]
        result = pack_context(rows, budget_tokens=40, overhead_tokens=5)
        self.assertNotIn("large", result["ids"])
        self.assertLessEqual(result["estimated_tokens"], 40)

    def test_image_and_tool_overhead_reduce_text_budget(self):
        result = pack_context([row("c1", "fact")], budget_tokens=20,
                              overhead_tokens=5, image_tokens=16)
        self.assertEqual(result["ids"], [])


if __name__ == "__main__":
    unittest.main()
