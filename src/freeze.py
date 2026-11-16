"""Freeze a dev-selected experiment against exact file bytes and live DB rows."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from day6.starter.src.store import PgVectorStore
from src.store import Lab6ReadOnlyStore


def live_snapshot(suite):
    os.environ.setdefault("PGCONNECT_TIMEOUT", "10")
    if suite == "core":
        return Lab6ReadOnlyStore(os.environ["DAY6_DATABASE_URL"]).export("C")[1]["rows_sha256"]
    return PgVectorStore(os.environ["LAB7_DATABASE_URL"], 1024).snapshot()["sha256"]


def effective_provider(suite):
    return os.environ.get("OPENROUTER_CORE_PROVIDER", "relace") if suite == "core" else os.environ.get("OPENROUTER_PROVIDER", "wafer")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--suite", choices=["core", "bonus"], required=True)
    p.add_argument("--selected", choices=["D0", "L0", "H1", "H2"], required=True)
    args = p.parse_args()
    load_dotenv(override=False)
    target = Path("results/run_manifest.json")
    m = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"schema_version": 1, "files": {}, "suites": {}}
    if m["suites"].get(args.suite, {}).get("frozen"):
        raise ValueError("Suite already frozen; preserve its record before preparing another experiment")
    required = [Path(f"benchmark/{args.suite}/questions.jsonl"),
                Path(f"results/{args.suite}/selection-final.json"),
                Path(f"results/{args.suite}/dev/comparison-final.json"),
                Path("data/core/chunks.json"), Path("requirements.txt"), Path(".gitattributes")]
    if args.suite == "bonus":
        required += [Path("data/bonus/manifest.json"), Path("data/bonus/index/vector_index.json"),
                     Path("data/bonus/index/embedded_chunks.jsonl"), Path("data/bonus/index/regions.jsonl")]
    selection = json.loads(required[1].read_text(encoding="utf-8"))
    if selection["selected_config"] != args.selected or selection.get("test_used_for_selection"):
        raise ValueError("Selection must match the dev-only decision")
    paths = [*Path("src").glob("*.py"), *Path("configs").glob("*.json"),
             *Path("day6/starter/src").glob("*.py"), Path("starter/baseline.py"), *required]
    for path in paths:
        m["files"][path.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    model = os.environ.get("OPENROUTER_MODEL", "z-ai/glm-5.3-flash")
    m["suites"][args.suite] = {"frozen": True, "baseline_config": "D0", "selected_config": args.selected,
        "benchmark_sha256": m["files"][f"benchmark/{args.suite}/questions.jsonl"],
        "snapshot_rows_sha256": live_snapshot(args.suite), "model": model,
        "provider": effective_provider(args.suite), "fallbacks": False,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat()}
    target.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "frozen", "suite": args.suite, "selected": args.selected, "files": len(m["files"])}))


if __name__ == "__main__":
    main()
