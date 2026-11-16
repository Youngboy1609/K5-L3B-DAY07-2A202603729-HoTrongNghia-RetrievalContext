"""Run a single benchmark split while keeping gold fields outside the agent."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from src.agent import Agent
from src.evaluation import load_jsonl, retrieval_metrics, source_aware_metrics
from src.model import BudgetError
from src.runtime import create_agent


def run_dev(suite: str, config: str, *, split: str = "dev", questions_path: str | Path | None = None,
            output_path: str | Path | None = None) -> dict[str, Any]:
    if suite not in {"core", "bonus"} or config not in {"D0", "L0", "H1", "H2"} or split not in {"dev", "test"}:
        raise ValueError("invalid suite or config")
    questions_path = Path(questions_path or f"benchmark/{suite}/questions.jsonl")
    if split == "test":
        _validate_frozen_inputs(suite, config, questions_path)
    rows = [q for q in load_jsonl(questions_path) if q.get("split") == split]
    if not rows:
        raise ValueError(f"{split} split is empty")
    output_path = Path(output_path or f"results/{suite}/{split}/{config}.jsonl")
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite existing run: {output_path}")
    agent = create_agent(suite, config=config)
    if suite == "core":
        index_hash = hashlib.sha256(Path("data/core/chunks.json").read_bytes()).hexdigest()
    else:
        manifest_path = Path("data/bonus/index/vector_index.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        index_hash = manifest["db_snapshot"]["sha256"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    traces = []
    stopped_for_budget = False
    run_id = uuid.uuid4().hex
    with output_path.open("x", encoding="utf-8") as stream:
        for row in rows:
            # Only query text/metadata go to the agent. Gold and expected answer stay here.
            try:
                trace = agent.run(row["question"], query_id=row["id"], suite=suite, split=split,
                                  config=config, index_hash=index_hash)
            except BudgetError:
                stopped_for_budget = True
                break
            traces.append(trace)
            trace["run_id"] = run_id
            stream.write(json.dumps(trace, ensure_ascii=False) + "\n")
            stream.flush()
    completed_ids = {trace["query_id"] for trace in traces}
    pending_ids = [row["id"] for row in rows if row["id"] not in completed_ids]
    metrics = retrieval_metrics(rows[:len(traces)], traces) if traces else {}
    corpus = (json.loads(Path("data/core/chunks.json").read_text(encoding="utf-8")) if suite == "core"
              else load_jsonl("data/bonus/index/embedded_chunks.jsonl"))
    evidence_metrics = source_aware_metrics(rows[:len(traces)], traces, corpus)
    costs = [float(t["cost_usd"]) for t in traces]
    summary = {"suite": suite, "split": split, "config": config, "run_id": run_id, "n": len(traces),
               "status": "incomplete_budget_blocked" if stopped_for_budget else "complete",
               "pending_query_ids": pending_ids,
               "errors": sum(bool(t["errors"]) or t["status"] == "error" for t in traces),
               "cost_usd": sum(costs), "latency_ms_median": _median(t["latency_ms"]["total"] for t in traces),
               "retrieval": metrics, "retrieval_source_quote": evidence_metrics, "trace_path": str(output_path)}
    summary_path = output_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _validate_frozen_inputs(suite: str, config: str, questions_path: Path) -> None:
    manifest_path = Path("results/run_manifest.json")
    if not manifest_path.is_file():
        raise ValueError("test split is locked until results/run_manifest.json is frozen")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    suite_manifest = manifest.get("suites", {}).get(suite, {})
    allowed = {suite_manifest.get("baseline_config"), suite_manifest.get("selected_config")}
    if manifest.get("schema_version") != 1 or config not in allowed or not suite_manifest.get("frozen"):
        raise ValueError("requested suite/config is not included in the frozen run manifest")
    for relative, expected in manifest.get("files", {}).items():
        path = Path(relative)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"frozen input changed or is missing: {relative}")
    questions_hash = hashlib.sha256(questions_path.read_bytes()).hexdigest()
    if questions_hash != suite_manifest.get("benchmark_sha256"):
        raise ValueError("test benchmark does not match frozen benchmark hash")
    if suite_manifest.get("snapshot_rows_sha256"):
        import os
        from dotenv import load_dotenv
        from src.freeze import live_snapshot, effective_provider
        load_dotenv(override=False)
        if (effective_provider(suite) != suite_manifest.get("provider")
                or os.environ.get("OPENROUTER_MODEL", "z-ai/glm-5.3-flash") != suite_manifest.get("model")
                or os.environ.get("OPENROUTER_ALLOW_FALLBACKS", "false").lower() != "false"):
            raise ValueError("effective model/provider/fallback policy differs from frozen run")
        if live_snapshot(suite) != suite_manifest["snapshot_rows_sha256"]:
            raise ValueError("live database rows differ from frozen snapshot")


def _median(values) -> float | None:
    values = sorted(values)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
