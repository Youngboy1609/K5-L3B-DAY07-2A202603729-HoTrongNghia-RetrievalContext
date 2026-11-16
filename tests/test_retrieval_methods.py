import unittest

from src.retrieval import CoreRetrieval, reciprocal_rank_fusion


def row(chunk_id, strategy="test"):
    return {"id": chunk_id, "text": chunk_id, "source_id": "doc", "source": "doc.pdf",
            "page": 1, "metadata": {}, "score": 0.1, "strategy": strategy}


class DenseStub:
    def __init__(self, rows):
        self.rows = rows
        self.seen = []

    def search(self, vector, *, strategy, filters, top_k):
        self.seen.append((strategy, filters, top_k))
        return self.rows[:top_k]


class RetrievalTests(unittest.TestCase):
    def test_rrf_deduplicates_and_uses_deterministic_tie_break(self):
        got = reciprocal_rank_fusion([[row("b"), row("a")], [row("a"), row("b")]])
        self.assertEqual([r["id"] for r in got], ["a", "b"])
        self.assertEqual(got[0]["strategy"], "rrf")
        self.assertEqual(len(got[0]["rrf_components"]), 2)

    def test_rrf_rejects_duplicate_ids_inside_one_ranking(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([[row("x"), row("x")]])

    def test_hybrid_applies_same_filter_to_dense_and_lexical(self):
        chunks = [row("a"), row("b")]
        chunks[0]["text"] = "tuple immutable"
        chunks[0]["metadata"] = {"chapter": 12}
        chunks[1]["text"] = "list mutable"
        chunks[1]["metadata"] = {"chapter": 10}
        dense = DenseStub([row("a", "dense"), row("b", "dense")])
        got = CoreRetrieval(chunks, dense).search("H1", "tuple", [0.0] * 1024,
                                                  filters={"chapter": 12}, top_k=2)
        self.assertEqual([x["id"] for x in got], ["a"])
        self.assertEqual(dense.seen[0][1], {"chapter": 12})


if __name__ == "__main__":
    unittest.main()
