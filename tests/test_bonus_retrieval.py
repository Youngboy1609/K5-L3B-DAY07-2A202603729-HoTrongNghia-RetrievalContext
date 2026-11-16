import unittest

from src.bonus_retrieval import BonusRetrieval


def row(cid, page, modality="text"):
    return {"id": cid, "text": "middle income development chart growth", "source_id": "wdr2024",
            "source": "World Development Report 2024", "page": page,
            "metadata": {"page": page, "modality": modality}, "score": 0.5}


class StoreStub:
    def __init__(self, rows):
        self.rows = rows

    def search(self, strategy, vector, *, top_k):
        return [{"chunk_id": r["id"], "text": r["text"], "metadata": r["metadata"], "score": r["score"]}
                for r in self.rows[:top_k]]


class BonusRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.rows = [row("a", 10, "chart"), row("b", 11, "text"), row("c", 10, "text")]
        self.retrieval = BonusRetrieval(self.rows, StoreStub(self.rows))

    def test_page_and_modality_filters_apply_to_all_methods(self):
        for method in ("D0", "L0", "H1"):
            got = self.retrieval.search(method, "growth chart", [0.0] * 1024,
                                        filters={"page": 10, "modality": "chart"}, top_k=10)
            self.assertEqual([r["id"] for r in got], ["a"])

    def test_unknown_filter_is_rejected(self):
        with self.assertRaises(ValueError):
            self.retrieval.search("D0", "query", [0.0] * 1024, filters={"path": "x"})


if __name__ == "__main__":
    unittest.main()
