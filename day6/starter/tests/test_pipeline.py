import unittest
from pathlib import Path

from src.chunking import by_paragraph, fixed_size
from src.evaluation import evaluate_query, summarize
from src.ingestion import load_pdf, normalize_text
from src.models import Chunk, DocumentPage


REPO = Path(__file__).resolve().parents[2]


class IngestionTests(unittest.TestCase):
    def test_normalization_preserves_indentation_and_collapses_excess_blank_lines(self):
        self.assertEqual(normalize_text("header\r\n    code  \r\n\r\n\r\n next  "), "header\n    code\n\n next")
        self.assertEqual(normalize_text("imme-\ndiately before"), "immediately before")

    def test_pdf_whitelist_has_35_nonempty_pages_with_chapter_metadata(self):
        pages = load_pdf(REPO / "data/thinkpython2.pdf", "think-python-2e", "data/thinkpython2.pdf")
        self.assertEqual(len(pages), 35)
        self.assertGreater(sum(len(page.text) for page in pages), 57684)
        self.assertEqual(pages[0].page, 93)
        self.assertEqual(pages[-1].page, 143)
        self.assertTrue(all(len(page.text) >= 300 and "chapter" in page.metadata for page in pages))
        chunks = [chunk for page in pages for chunk in by_paragraph(page, 500)]
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk.text) <= 500 for chunk in chunks))

    def test_pdf_extraction_preserves_paragraphs_and_relative_code_indentation(self):
        pages = load_pdf(REPO / "data/thinkpython2.pdf", "think-python-2e", "data/thinkpython2.pdf")
        page = next(page for page in pages if page.page == 127)
        self.assertIn("\n\n", page.text)
        self.assertRegex(page.text, r"def histogram\(s\):\n\s{2,}d = dict\(\)")


class ChunkingTests(unittest.TestCase):
    def setUp(self):
        self.page = DocumentPage("doc", "source.pdf", 7, "First paragraph.\n\nSecond paragraph has more words.")

    def test_fixed_chunks_are_page_bounded_and_have_stable_ids(self):
        first = fixed_size(self.page, 12, 2)
        second = fixed_size(self.page, 12, 2)
        self.assertEqual([chunk.chunk_id for chunk in first], [chunk.chunk_id for chunk in second])
        self.assertTrue(all(len(chunk.text) <= 12 and chunk.page == 7 for chunk in first))

    def test_empty_text_and_invalid_size(self):
        empty = DocumentPage("doc", "source.pdf", 7, "")
        self.assertEqual(fixed_size(empty, 12, 0), [])
        with self.assertRaises(ValueError):
            fixed_size(self.page, 5, 5)
        with self.assertRaises(ValueError):
            by_paragraph(self.page, 0)

    def test_paragraph_chunks_respect_cap_and_keep_provenance(self):
        chunks = by_paragraph(self.page, 24)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk.text) <= 24 for chunk in chunks))
        self.assertTrue(all(chunk.metadata["page"] == 7 for chunk in chunks))

    def test_paragraph_packing_counts_join_separators_toward_cap(self):
        page = DocumentPage("doc", "source.pdf", 7, "xx\n\nxx\n\nxx")
        chunks = by_paragraph(page, 8)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk.text) <= 8 for chunk in chunks))

    def test_paragraph_chunks_keep_real_blocks_separate_when_they_do_not_fit(self):
        page = DocumentPage("doc", "source.pdf", 7, "First block.\n\nSecond block.")
        chunks = by_paragraph(page, 18)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.text) <= 18 for chunk in chunks))


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.question = {
            "id": "q1", "split": "dev", "gold_source_id": "doc", "gold_page": 7,
            "evidence_quote": "complete evidence sentence.",
        }

    def hit(self, page=7, text="A complete evidence sentence."):
        return {"chunk_id": "c1", "text": text,
                "metadata": {"document_id": "doc", "page": page}}

    def test_hit_requires_correct_source_page_and_complete_quote(self):
        self.assertTrue(evaluate_query(self.question, [self.hit()])["evidence_hit_at_3"])
        self.assertFalse(evaluate_query(self.question, [self.hit(page=8)])["evidence_hit_at_3"])
        self.assertFalse(evaluate_query(self.question, [self.hit(text="complete evidence")])["evidence_hit_at_3"])

    def test_alternate_gold_evidence_and_empty_results(self):
        question = {**self.question, "gold_evidence": [
            {"gold_source_id": "doc", "gold_page": 8, "evidence_quote": "alternate evidence."}
        ]}
        self.assertTrue(evaluate_query(question, [self.hit(page=8, text="alternate evidence.")])["hit_at_1"])
        self.assertFalse(evaluate_query(self.question, [])["hit_at_1"])

    def test_summary_keeps_n_over_n_denominators(self):
        traces = [
            {"strategy": "A", "split": "dev", "hit_at_1": True, "evidence_hit_at_3": True},
            {"strategy": "A", "split": "dev", "hit_at_1": False, "evidence_hit_at_3": False},
        ]
        self.assertEqual(summarize(traces)["A/dev"]["hit_at_1"], {"numerator": 1, "denominator": 2})


if __name__ == "__main__":
    unittest.main()
