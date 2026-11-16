"""Dense, TF-IDF and hybrid search over the isolated WDR bonus namespace."""

from __future__ import annotations

from typing import Any

from starter.baseline import TfidfIndex
from src.retrieval import reciprocal_rank_fusion


class BonusRetrieval:
    def __init__(self, chunks: list[dict[str, Any]], store: Any) -> None:
        if not chunks or len({c.get("id") for c in chunks}) != len(chunks):
            raise ValueError("bonus corpus must be non-empty with unique IDs")
        self.chunks, self.store = chunks, store

    def search(self, method: str, query: str, query_vector: list[float], *,
               filters: dict[str, Any] | None = None, top_k: int = 20) -> list[dict[str, Any]]:
        if method not in {"D0", "L0", "H1", "H2"} or not query.strip() or not 1 <= top_k <= 100:
            raise ValueError("invalid method, query, or top_k")
        filters = filters or {}
        if set(filters) - {"page", "modality"}:
            raise ValueError("only page and modality filters are supported")
        selected = [r for r in self.chunks
                    if ("page" not in filters or r.get("page", r.get("metadata", {}).get("page")) == filters["page"])
                    and ("modality" not in filters or r.get("modality", r.get("metadata", {}).get("modality")) == filters["modality"])]
        # The preserved Lab6 store API lacks bonus-specific filters; over-fetch its hard cap
        # then apply page/modality allowlists here before returning the requested cutoff.
        dense_rows = self.store.search("WDR", query_vector, top_k=100)
        dense = [_normalize_db_row(r) for r in dense_rows]
        allowed = {r["id"] for r in selected}
        dense = [r for r in dense if r["id"] in allowed]
        if method == "D0":
            return dense[:top_k]
        lexical = []
        if selected:
            lexical = [{**r, "strategy": "tfidf"} for r in TfidfIndex(selected).search(query, top_k=top_k)]
        if method == "L0":
            return lexical
        return reciprocal_rank_fusion([dense, lexical])[:top_k]


def _normalize_db_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    return {"id": row["chunk_id"], "text": row["text"], "source_id": "wdr2024",
            "source": "World Development Report 2024", "page": metadata.get("page", row.get("page")),
            "metadata": metadata, "bbox": metadata.get("bbox"), "modality": metadata.get("modality"),
            "score": row["score"], "strategy": "dense"}
