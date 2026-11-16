"""Construct the real local-GPU and isolated-DB agent runtime."""

from __future__ import annotations

import json
import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from day6.starter.src.embeddings import QwenEmbedder
from day6.starter.src.store import PgVectorStore
from src.agent import Agent
from src.bonus_retrieval import BonusRetrieval
from src.ingest_bonus import make_region_opener
from src.model import OpenRouterClient
from src.retrieval import CoreRetrieval
from src.store import Lab6ReadOnlyStore


@lru_cache(maxsize=1)
def _embedder():
    # Reuse one real CUDA model for sequential config comparisons in a process.
    return QwenEmbedder(revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3", batch_size=1,
                        local_files_only=True, max_seq_length=512)


def create_agent(suite: str, *, config: str = "D0", pilot: bool = False) -> Agent:
    load_dotenv(override=False)
    os.environ.setdefault("PGCONNECT_TIMEOUT", "10")
    config_path = Path("configs") / f"{config}.json"
    run_config = json.loads(config_path.read_text(encoding="utf-8"))
    if run_config.get("config") != config:
        raise ValueError("config file does not match requested run config")
    embedder = _embedder()
    region_opener = None
    if suite == "core":
        chunks = json.loads(Path("data/core/chunks.json").read_text(encoding="utf-8"))
        database_url = os.environ.get("DAY6_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("DAY6_DATABASE_URL is missing")
        store = Lab6ReadOnlyStore(database_url)
        retrieval = CoreRetrieval(chunks, store)
    elif suite == "bonus":
        database_url = os.environ.get("LAB7_DATABASE_URL", "").strip()
        if not database_url or "55433" in database_url:
            raise RuntimeError("LAB7_DATABASE_URL must point to the isolated Lab7 database")
        chunks_path = Path("data/bonus/index/embedded_chunks.jsonl")
        if not chunks_path.exists():
            raise RuntimeError("Bonus index is missing; run ingest-bonus and index-bonus first")
        chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        source_chunks = [json.loads(line) for line in Path("data/bonus/index/chunks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        index_manifest = json.loads(Path("data/bonus/index/vector_index.json").read_text(encoding="utf-8"))
        if hashlib.sha256(chunks_path.read_bytes()).hexdigest() != index_manifest["embedded_chunks_sha256"]:
            raise RuntimeError("Bonus embedding rows changed; rebuild the index before evaluation")
        store = PgVectorStore(database_url, dimensions=1024)
        retrieval = BonusRetrieval(chunks, store, source_chunks=source_chunks)
        region_opener = make_region_opener(
            ".lab-local/research/wdr2024-full-candidate.pdf", "data/bonus/index/regions.jsonl",
            page_by_id={row["id"]: row["page"] for row in chunks if isinstance(row.get("page"), int)})
    else:
        raise ValueError("suite must be core or bonus")

    def search(method: str, query: str, vector: list[float], filters: dict[str, Any], top_k: int):
        return retrieval.search(method, query, vector, filters=filters, top_k=top_k)

    provider = (os.environ.get("OPENROUTER_CORE_PROVIDER", "relace").strip().lower()
                if suite == "core" else os.environ.get("OPENROUTER_PROVIDER", "wafer").strip().lower())
    client = OpenRouterClient(provider_override=provider)
    return Agent(client, search, embedder.embed_query, region_opener,
                 max_turns=run_config["max_model_turns"],
                 context_budget=run_config["context_text_budget_tokens"],
                 candidate_limit=run_config["candidate_limit"],
                 max_search_calls=run_config["max_search_calls"],
                 max_regions=run_config["max_regions"],
                 image_token_reserve=run_config["image_token_reserve"],
                 pilot=pilot)
