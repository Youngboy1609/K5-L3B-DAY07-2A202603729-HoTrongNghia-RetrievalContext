"""Compare original dev queries without model rewriting or API calls."""
import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from day6.starter.src.store import PgVectorStore
from src.bonus_retrieval import BonusRetrieval
from src.evaluation import load_jsonl, retrieval_metrics, source_aware_metrics
from src.retrieval import CoreRetrieval
from src.runtime import _embedder
from src.store import Lab6ReadOnlyStore


def compare(suite, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError("Refusing to overwrite original-query comparison")
    load_dotenv(override=False)
    os.environ.setdefault("PGCONNECT_TIMEOUT", "10")
    if suite == "core":
        chunks = json.loads(Path("data/core/chunks.json").read_text(encoding="utf-8"))
        retrieval = CoreRetrieval(chunks, Lab6ReadOnlyStore(os.environ["DAY6_DATABASE_URL"]))
    elif suite == "bonus":
        chunks = load_jsonl("data/bonus/index/embedded_chunks.jsonl")
        retrieval = BonusRetrieval(chunks, PgVectorStore(os.environ["LAB7_DATABASE_URL"], 1024))
    else:
        raise ValueError("Unknown suite")
    questions = [q for q in load_jsonl(f"benchmark/{suite}/questions.jsonl") if q["split"] == "dev" and q["answerable"]]
    model = _embedder()
    traces = {config: [] for config in ["D0", "L0", "H1", "H2"]}
    for q in questions:
        started = time.perf_counter()
        vector = model.embed_query(q["question"])
        embed_ms = (time.perf_counter() - started) * 1000
        for config in traces:
            started = time.perf_counter()
            rows = retrieval.search(config, q["question"], vector, filters={}, top_k=20)
            traces[config].append({"query_id": q["id"], "query": q["question"], "filters": {},
                "embedding_ms": embed_ms, "retrieval_ms": (time.perf_counter() - started) * 1000,
                "events": [{"type": "tool", "name": "search", "ranked_ids": [r["id"] for r in rows]}],
                "top3": [{k: r.get(k) for k in ["id", "source", "page", "score"]} for r in rows[:3]], "contexts": []})
    result = {"suite": suite, "split": "dev", "query_mode": "original_without_rewrite",
        "top_k": 20, "cutoff_for_comparison": 3, "api_cost_usd": 0,
        "context_note": "No model context is assembled here; context coverage is reported separately for the agent runs.",
        "configs": {c: {"retrieval_id_exact": retrieval_metrics(questions, ts),
                         "retrieval_source_quote": source_aware_metrics(questions, ts, chunks), "traces": ts}
                    for c, ts in traces.items()}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["core", "bonus"], required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = compare(args.suite, args.output)
    print(json.dumps({"suite": args.suite, "status": "complete", "api_cost_usd": result["api_cost_usd"]}))


if __name__ == "__main__":
    main()
