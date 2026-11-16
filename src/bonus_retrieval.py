"""Dense, TF-IDF and hybrid search over the isolated WDR bonus namespace."""

from __future__ import annotations

import re
from typing import Any

from starter.baseline import TfidfIndex
from src.retrieval import reciprocal_rank_fusion


_REFERENCE = re.compile(r"\b(figure|table)\s+([A-Z0-9]+\s*\.\s*\d+)\b", re.I)


def _references(text: str) -> set[str]:
    return {kind.casefold() + ":" + re.sub(r"\s+", "", label).casefold()
            for kind, label in _REFERENCE.findall(text)}


class BonusRetrieval:
    def __init__(self, chunks: list[dict[str, Any]], store: Any, *,
                 source_chunks: list[dict[str, Any]] | None = None) -> None:
        if not chunks or len({c.get("id") for c in chunks}) != len(chunks):
            raise ValueError("bonus corpus must be non-empty with unique IDs")
        self.chunks, self.store = chunks, store
        self.source_chunks = source_chunks or chunks
        self.parents = {row["id"]: row for row in self.source_chunks}
        self.children_by_parent: dict[str, list[dict[str, Any]]] = {}
        for row in chunks:
            metadata = row.get("metadata") or {}
            parent_id = metadata.get("parent_id", row["id"])
            parent = self.parents.get(parent_id)
            if parent and (parent.get("source_id") != row.get("source_id")
                           or parent.get("page") != row.get("page")):
                raise ValueError("child parent source/page provenance mismatch")
            self.children_by_parent.setdefault(parent_id, []).append(row)
        self.parent_lexical = TfidfIndex(self.source_chunks)

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
        parent_lexical = self.parent_lexical.search(query, top_k=top_k)
        references = _references(query)
        anchored = []
        if references:
            for parent in self.source_chunks:
                parent_id = parent["id"]
                metadata = parent.get("metadata") or {}
                header = " ".join((parent.get("text", "")[:500], str(metadata.get("title", ""))))
                if references & _references(header):
                    anchored.append(parent)
            anchored.sort(key=lambda row: (-sum(1 / (60 + i) for i, hit in enumerate(parent_lexical, 1)
                                               if hit["id"] == row["id"]), row["page"], row["id"]))
        parent_ranked = []
        seen_parent_ranked = set()
        for parent in [*anchored, *parent_lexical]:
            parent_id = parent["id"]
            children = self.children_by_parent.get(parent_id, [])
            if children:
                # Keep evidence IDs tied to text actually supplied; the full parent is
                # a candidate only when it is itself an embedded, retrievable row.
                for child in children:
                    if child["id"] in allowed and child["id"] not in seen_parent_ranked:
                        parent_ranked.append(child)
                        seen_parent_ranked.add(child["id"])
            elif parent_id in allowed:
                parent_ranked.append(allowed[parent_id])
        fused = reciprocal_rank_fusion([dense, lexical, parent_ranked])
        if anchored:
            anchored_ids = {row["id"] for parent in anchored
                            for row in self.children_by_parent.get(parent["id"], []) if row["id"] in allowed}
            prioritized = [row for row in fused if row["id"] in anchored_ids]
            fused = prioritized + [row for row in fused if row["id"] not in anchored_ids]
        return fused[:top_k]


def _normalize_db_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    return {"id": row["chunk_id"], "text": row["text"], "source_id": "wdr2024",
            "source": "World Development Report 2024", "page": metadata.get("page", row.get("page")),
            "metadata": metadata, "bbox": metadata.get("bbox"), "modality": metadata.get("modality"),
            "score": row["score"], "strategy": "dense"}
