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

    def test_exact_figure_reference_prioritizes_matching_parent_not_prefix_neighbour(self):
        parents = [
            {**row("p1", 1), "id": "fig-1-2", "text": "Figure 1.2 Relevant growth evidence"},
            {**row("p11", 11), "id": "fig-11-2", "text": "Figure 11.2 Irrelevant middle income evidence"},
        ]
        children = [
            {**parents[0], "id": "fig-1-2-part-01", "text": "Relevant growth evidence",
             "metadata": {"parent_id": "fig-1-2", "page": 1, "modality": "text"}},
            {**parents[1], "id": "fig-11-2-part-01", "text": "Irrelevant middle income evidence",
             "metadata": {"parent_id": "fig-11-2", "page": 11, "modality": "text"}},
        ]
        retrieval = BonusRetrieval(children, StoreStub(children), source_chunks=parents)
        got = retrieval.search("H1", "Figure 1.2 growth", [0.0] * 1024, top_k=2)
        self.assertEqual(got[0]["id"], "fig-1-2-part-01")
        self.assertNotEqual(got[0]["id"], "fig-11-2-part-01")

    def test_two_explicit_references_keep_both_parents_in_candidates(self):
        parents = [
            {**row("table", 81), "id": "Table-S-1", "text": "Table S.1 Malaysia social mobility"},
            {**row("fig", 175), "id": "Figure-6-3", "text": "Figure 6.3 clean energy investment"},
        ]
        children = [{**p, "id": p["id"] + "-part-01",
                     "metadata": {"parent_id": p["id"], "page": p["page"], "modality": "text"}}
                    for p in parents]
        retrieval = BonusRetrieval(children, StoreStub(children), source_chunks=parents)
        got = retrieval.search("H1", "Table S.1 and Figure 6.3", [0.0] * 1024, top_k=2)
        self.assertEqual({r["id"] for r in got}, {"Table-S-1-part-01", "Figure-6-3-part-01"})


if __name__ == "__main__":
    unittest.main()
