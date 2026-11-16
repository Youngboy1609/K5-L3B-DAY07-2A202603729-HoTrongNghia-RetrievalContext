"""Restore permitted Day6 vectors to a new isolated replay DB, never the original DB."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg

from day6.starter.src.models import Chunk
from day6.starter.src.store import PgVectorStore
from src.store import Lab6ReadOnlyStore


def main():
    url = os.environ.get("CORE_REPLAY_DATABASE_URL",
                         "postgresql://replay:replay_local_only@127.0.0.1:55435/core_replay")
    target = urlparse(url)
    if target.hostname not in {"127.0.0.1", "localhost"} or target.port != 55435 or target.path != "/core_replay":
        raise ValueError("Replay target must be local core_replay on port 55435")
    rows = json.loads(Path("data/core/chunks.json").read_text(encoding="utf-8"))
    expected = json.loads(Path("data/core/export_manifest.json").read_text(encoding="utf-8"))["rows_sha256_before"]
    store = PgVectorStore(url, 1024)
    store.create_schema()
    with psycopg.connect(url) as conn:
        count = conn.execute("SELECT count(*) FROM lab_chunks").fetchone()[0]
    if not count:
        chunks = []
        for row in rows:
            meta = dict(row["metadata"])
            source = meta.pop("lab6_source_path", row["source"])
            chunks.append(Chunk(row["id"], row["source_id"], source, row["page"], row["text"], meta))
        store.upsert("C", chunks, [row["embedding"] for row in rows])
    # An existing database is checked, never replaced or cleared.
    _, snapshot = Lab6ReadOnlyStore(url).export("C")
    if snapshot["rows_sha256"] != expected:
        raise RuntimeError("Replay DB differs from the source snapshot; no existing rows were replaced")
    print(json.dumps({"status": "verified", "rows": snapshot["row_count"],
                      "rows_sha256": snapshot["rows_sha256"], "original_day6_untouched": True}))


if __name__ == "__main__":
    main()
