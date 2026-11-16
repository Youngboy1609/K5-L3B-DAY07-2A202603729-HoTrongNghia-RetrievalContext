"""Embed the complete extracted WDR corpus into the Lab7-only pgvector store."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from day6.starter.src.embeddings import QwenEmbedder
from day6.starter.src.models import Chunk
from day6.starter.src.store import PgVectorStore


def prepare_embedding_rows(rows: list[dict], tokenizer) -> list[dict]:
    prepared = []
    for row in rows:
        ids = tokenizer.encode(row["text"], add_special_tokens=False)
        spans = [ids[i:i + 450] for i in range(0, len(ids), 450)] or [[]]
        for part_no, token_span in enumerate(spans, start=1):
            value = tokenizer.decode(token_span, skip_special_tokens=True).replace("\x00", " ").strip()
            if not value:
                continue
            suffix = f"-part-{part_no:02d}" if len(spans) > 1 else ""
            prepared.append({**row, "id": row["id"] + suffix, "text": value,
                             "metadata": {"parent_id": row["id"], "page": row["page"],
                                          "modality": row["modality"], "bbox": row.get("bbox"),
                                          "rights_status": row["rights_status"]}})
    return prepared


def index_bonus(chunks_path: str | Path = "data/bonus/index/chunks.jsonl", *,
                report_path: str | Path = "data/bonus/index/vector_index.json") -> dict:
    load_dotenv(override=False)
    database_url = os.environ.get("LAB7_DATABASE_URL", "").strip()
    if not database_url or "55433" in database_url:
        raise RuntimeError("LAB7_DATABASE_URL must point to the isolated Lab7 database")
    rows = [json.loads(line) for line in Path(chunks_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("bonus chunks must be non-empty and have unique IDs")
    # 6 GB laptop GPU: one long sequence per forward avoids the measured batch-8 OOM.
    embedder = QwenEmbedder(revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3", batch_size=1,
                            local_files_only=True, max_seq_length=512)
    tokenized_rows = prepare_embedding_rows(rows, embedder.model.tokenizer)
    vectors: list[list[float]] = []
    encoding_seconds = 0.0
    for start in range(0, len(tokenized_rows), 32):
        vectors.extend(embedder.embed_documents([r["text"] for r in tokenized_rows[start:start + 32]]))
        encoding_seconds += embedder.last_encode_seconds
    embedded_path = Path(chunks_path).with_name("embedded_chunks.jsonl")
    embedded_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in tokenized_rows), encoding="utf-8")
    chunks = [Chunk(r["id"], r["source_id"], r["source"], r["page"], r["text"], r["metadata"])
              for r in tokenized_rows]
    store = PgVectorStore(database_url, dimensions=1024)
    store.create_schema()
    store.upsert("WDR", chunks, vectors)
    snapshot = store.snapshot()
    result = {"schema_version": 1, "source_chunks": len(rows), "embedded_chunks": len(chunks),
              "dimensions": 1024, "embedding_model": embedder.model_name,
              "revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3", "device": str(embedder.model.device),
              "normalization": "PDF extraction NUL bytes replaced with spaces before embedding/storage",
              "load_seconds": embedder.load_seconds, "encode_seconds": encoding_seconds,
              "embedded_chunks_path": str(embedded_path),
              "embedded_chunks_sha256": hashlib.sha256(embedded_path.read_bytes()).hexdigest(),
              "db_snapshot": snapshot, "source_sha256": hashlib.sha256(Path(chunks_path).read_bytes()).hexdigest()}
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
