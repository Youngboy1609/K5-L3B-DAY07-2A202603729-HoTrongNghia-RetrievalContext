"""Read-only bridge to the Lab6 pgvector index."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import psycopg


class Lab6ReadOnlyStore:
    """Read Lab6 rows without permitting this client to write to that database."""

    def __init__(self, database_url: str, dimensions: int = 1024) -> None:
        if not database_url or dimensions <= 0:
            raise ValueError("database_url and positive dimensions are required")
        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self):
        return psycopg.connect(
            self.database_url, connect_timeout=10,
            options="-c default_transaction_read_only=on -c statement_timeout=30000",
        )

    @staticmethod
    def _digest(rows: list[tuple[Any, ...]]) -> str:
        digest = hashlib.sha256()
        for row in rows:
            digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()

    def export(self, strategy: str = "C") -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if strategy not in {"A", "B", "C"}:
            raise ValueError("strategy must be A, B, or C")
        with self._connect() as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                server_version, vector_version = conn.execute(
                    "SELECT current_setting('server_version'), "
                    "(SELECT extversion FROM pg_extension WHERE extname='vector')"
                ).fetchone()
                raw_rows = conn.execute(
                    "SELECT strategy,chunk_id,document_id,source,page,content,metadata::text,embedding::text "
                    "FROM lab_chunks WHERE strategy=%s ORDER BY chunk_id",
                    (strategy,),
                ).fetchall()
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in raw_rows:
            st, chunk_id, document_id, source, page, content, metadata_text, embedding_text = row
            if st != strategy or chunk_id in seen:
                raise ValueError("Lab6 export contains wrong strategy or duplicate chunk IDs")
            seen.add(chunk_id)
            metadata = json.loads(metadata_text)
            vector = json.loads(embedding_text)
            if len(vector) != self.dimensions or not all(math.isfinite(float(v)) for v in vector):
                raise ValueError(f"chunk {chunk_id} has an invalid embedding")
            if page < 1 or not isinstance(metadata, dict):
                raise ValueError(f"chunk {chunk_id} has invalid source metadata")
            metadata = {**metadata, "lab6_source_path": source}
            mapped_source = "day6/data/thinkpython2.pdf" if source == "data/thinkpython2.pdf" else source
            output.append({
                "id": chunk_id,
                "text": content,
                "source_id": document_id,
                "source": mapped_source,
                "page": page,
                "metadata": metadata,
                "embedding": [float(v) for v in vector],
            })
        return output, {
            "strategy": strategy,
            "row_count": len(raw_rows),
            "unique_ids": len(seen),
            "postgres_version": server_version,
            "pgvector_version": vector_version,
            "rows_sha256": self._digest(raw_rows),
        }

    def search(self, query_vector: list[float], *, strategy: str = "C",
               filters: dict[str, Any] | None = None, top_k: int = 20) -> list[dict[str, Any]]:
        if strategy not in {"A", "B", "C"} or not 1 <= top_k <= 100:
            raise ValueError("invalid strategy or top_k")
        if len(query_vector) != self.dimensions or not all(math.isfinite(float(v)) for v in query_vector):
            raise ValueError("query embedding has the wrong dimension or a non-finite value")
        filters = filters or {}
        if set(filters) - {"chapter"}:
            raise ValueError("only the chapter filter is supported")
        vector = "[" + ",".join(str(float(v)) for v in query_vector) + "]"
        where = "strategy=%s"
        params: list[Any] = [strategy]
        if "chapter" in filters:
            chapter = filters["chapter"]
            if not isinstance(chapter, int) or chapter < 0:
                raise ValueError("chapter must be a non-negative integer")
            where += " AND (metadata->>'chapter')::int=%s"
            params.append(chapter)
        with self._connect() as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                rows = conn.execute(
                    f"SELECT chunk_id,content,document_id,source,page,metadata, "
                    f"1-(embedding <=> %s::vector) AS score FROM lab_chunks "
                    f"WHERE {where} ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s",
                    (vector, *params, vector, top_k),
                ).fetchall()
        results = []
        for chunk_id, content, document_id, source, page, metadata, score in rows:
            mapped_source = "day6/data/thinkpython2.pdf" if source == "data/thinkpython2.pdf" else source
            results.append({"id": chunk_id, "text": content, "source_id": document_id,
                            "source": mapped_source, "page": page, "metadata": metadata,
                            "score": float(score), "strategy": strategy})
        if len(results) > top_k or len({r["id"] for r in results}) != len(results):
            raise RuntimeError("Lab6 search returned invalid result cardinality")
        return results
