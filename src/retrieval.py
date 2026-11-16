"""Dense, TF-IDF and reciprocal-rank fusion over one pinned corpus."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from starter.baseline import TfidfIndex


def reciprocal_rank_fusion(rankings: list[list[dict[str, Any]]], *, k: int = 60) -> list[dict[str, Any]]:
    if k <= 0:
        raise ValueError("RRF k must be positive")
    score_by_id: dict[str, float] = defaultdict(float)
    row_by_id: dict[str, dict[str, Any]] = {}
    components: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rows in rankings:
        seen_in_ranking: set[str] = set()
        for rank, row in enumerate(rows, start=1):
            chunk_id = row.get("id")
            if not isinstance(chunk_id, str) or not chunk_id or chunk_id in seen_in_ranking:
                raise ValueError("each ranking must contain unique non-empty IDs")
            seen_in_ranking.add(chunk_id)
            score_by_id[chunk_id] += 1.0 / (k + rank)
            row_by_id.setdefault(chunk_id, row)
            components[chunk_id].append({"rank": rank, "source": row.get("strategy")})
    return [
        {**row_by_id[chunk_id], "score": score_by_id[chunk_id], "strategy": "rrf",
         "rrf_components": components[chunk_id]}
        for chunk_id in sorted(score_by_id, key=lambda cid: (-score_by_id[cid], cid))
    ]


class CoreRetrieval:
    """Expose the three Lab7 methods while keeping dense queries on Lab6 C."""

    METHODS = {"D0": "dense", "L0": "tfidf", "H1": "hybrid", "H2": "hybrid"}

    def __init__(self, chunks: list[dict[str, Any]], dense_store: Any) -> None:
        if not chunks or len({c.get("id") for c in chunks}) != len(chunks):
            raise ValueError("core corpus must be non-empty with unique IDs")
        self.chunks = chunks
        self.dense_store = dense_store
        self.by_id = {c["id"]: c for c in chunks}

    def _lexical(self, query: str, *, filters: dict[str, Any] | None, top_k: int) -> list[dict[str, Any]]:
        selected = self.chunks
        if filters and "chapter" in filters:
            selected = [c for c in self.chunks if c.get("metadata", {}).get("chapter") == filters["chapter"]]
        if not selected:
            return []
        rows = TfidfIndex(selected).search(query, top_k=top_k)
        return [{**row, "id": row["id"], "strategy": "tfidf"} for row in rows]

    def _dense(self, query_vector: list[float], *, filters: dict[str, Any], top_k: int) -> list[dict[str, Any]]:
        rows = self.dense_store.search(query_vector, strategy="C", filters=filters, top_k=top_k)
        if "chapter" in filters:
            rows = [r for r in rows if r.get("metadata", {}).get("chapter") == filters["chapter"]]
        return rows

    def search(self, method: str, query: str, query_vector: list[float], *,
               filters: dict[str, Any] | None = None, top_k: int = 20) -> list[dict[str, Any]]:
        if method not in self.METHODS or not query.strip() or not 1 <= top_k <= 100:
            raise ValueError("invalid method, query, or top_k")
        filters = filters or {}
        if set(filters) - {"chapter"}:
            raise ValueError("only the chapter filter is supported")
        kind = self.METHODS[method]
        if kind == "dense":
            return self._dense(query_vector, filters=filters, top_k=top_k)
        lexical = self._lexical(query, filters=filters, top_k=top_k)
        if kind == "tfidf":
            return lexical
        dense = self._dense(query_vector, filters=filters, top_k=top_k)
        return reciprocal_rank_fusion([dense, lexical], k=60)[:top_k]
