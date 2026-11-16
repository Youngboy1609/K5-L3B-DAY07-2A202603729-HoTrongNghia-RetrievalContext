"""Bounded, provenance-preserving context packing."""

from __future__ import annotations

import math
from typing import Any


def estimate_tokens(text: str) -> int:
    """Conservative UTF-8 byte estimate; provider-reported tokens are logged separately."""
    return max(1, math.ceil(len(text.encode("utf-8")) / 3))


def pack_context(rows: list[dict[str, Any]], *, budget_tokens: int,
                 overhead_tokens: int = 350, image_tokens: int = 0) -> dict[str, Any]:
    if budget_tokens <= 0 or overhead_tokens < 0 or image_tokens < 0:
        raise ValueError("context budget and overhead are invalid")
    remaining = budget_tokens - overhead_tokens - image_tokens
    if remaining <= 0:
        return {"text": "", "ids": [], "chunks": [], "estimated_tokens": overhead_tokens + image_tokens}
    blocks: list[str] = []
    ids: list[str] = []
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    used = 0
    for row in rows:
        chunk_id = row.get("id")
        if not isinstance(chunk_id, str) or not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        source = row.get("source", row.get("source_id", "unknown source"))
        page = row.get("page", "?")
        text = row.get("text", "")
        if not isinstance(text, str) or not text.strip():
            continue
        block = f"[{chunk_id} | {source} | page {page}]\n{text.strip()}"
        block_tokens = estimate_tokens(block)
        separator_tokens = 2 if blocks else 0
        if used + separator_tokens + block_tokens > remaining:
            continue
        blocks.append(block)
        ids.append(chunk_id)
        selected.append(row)
        used += separator_tokens + block_tokens
    return {"text": "\n\n".join(blocks), "ids": ids, "chunks": selected,
            "estimated_tokens": used + overhead_tokens + image_tokens}
