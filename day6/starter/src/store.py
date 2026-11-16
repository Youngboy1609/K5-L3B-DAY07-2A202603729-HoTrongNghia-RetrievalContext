"""Persistent exact cosine search with allowlisted metadata filters."""
from typing import Any
import hashlib
import json
import math
import psycopg
from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url, self.dimensions = database_url, dimensions

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS lab_chunks (
                strategy text NOT NULL, chunk_id text NOT NULL, document_id text NOT NULL,
                source text NOT NULL, page integer NOT NULL, content text NOT NULL,
                metadata jsonb NOT NULL, embedding vector({self.dimensions}) NOT NULL,
                PRIMARY KEY(strategy, chunk_id))""")
            conn.execute("CREATE INDEX IF NOT EXISTS lab_chunks_meta_idx ON lab_chunks USING gin (metadata)")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have equal lengths")
        for vector in vectors:
            if len(vector) != self.dimensions or not all(math.isfinite(float(x)) for x in vector):
                raise ValueError("vector dimensions or values are invalid")
        with psycopg.connect(self.database_url) as conn:
            with conn.transaction():
                conn.execute("DELETE FROM lab_chunks WHERE strategy=%s", (strategy,))
                for chunk, vector in zip(chunks, vectors, strict=True):
                    conn.execute("""INSERT INTO lab_chunks
                        (strategy,chunk_id,document_id,source,page,content,metadata,embedding)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::vector)""",
                        (strategy,chunk.chunk_id,chunk.document_id,chunk.source,chunk.page,
                         chunk.text,json.dumps(chunk.metadata,ensure_ascii=False),
                         "["+",".join(str(float(x)) for x in vector)+"]"))

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if top_k <= 0 or len(query_vector) != self.dimensions:
            raise ValueError("top_k must be positive and query vector dimensions must match")
        if not all(math.isfinite(float(x)) for x in query_vector):
            raise ValueError("query vector contains non-finite values")
        filters = filters or {}
        unknown = set(filters) - {"chapter"}
        if unknown:
            raise ValueError(f"Unsupported filters: {sorted(unknown)}")
        where = "strategy=%s"
        params: list[Any] = [strategy]
        if "chapter" in filters:
            where += " AND (metadata->>'chapter')::int=%s"
            params.append(int(filters["chapter"]))
        vector="["+",".join(str(float(x)) for x in query_vector)+"]"
        with psycopg.connect(self.database_url) as conn:
            rows=conn.execute(f"""SELECT chunk_id,content,metadata,
                1-(embedding <=> %s::vector) AS score FROM lab_chunks
                WHERE {where} ORDER BY embedding <=> %s::vector, chunk_id LIMIT %s""",
                (vector,*params,vector,top_k)).fetchall()
        return [{"chunk_id":r[0],"text":r[1],"metadata":r[2],"score":float(r[3])} for r in rows]

    def snapshot(self) -> dict[str, Any]:
        """Hash persisted rows so a freeze also identifies the indexed corpus."""
        digest = hashlib.sha256()
        counts: dict[str, int] = {}
        with psycopg.connect(self.database_url) as conn:
            server_version, pgvector_version = conn.execute("""SELECT current_setting('server_version'),
                (SELECT extversion FROM pg_extension WHERE extname='vector')""").fetchone()
            rows = conn.execute("""SELECT strategy,chunk_id,document_id,source,page,content,metadata::text,embedding::text
                FROM lab_chunks ORDER BY strategy,chunk_id""").fetchall()
        for row in rows:
            counts[row[0]] = counts.get(row[0], 0) + 1
            digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            digest.update(b"\n")
        return {"postgres_version": server_version, "pgvector_version": pgvector_version,
                "row_count": len(rows), "counts_by_strategy": counts, "sha256": digest.hexdigest()}
