"""Lab7 local preparation and smoke commands."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src.index_bonus import index_bonus
from src.evaluation import load_jsonl, validate_benchmark
from src.ingest_bonus import ingest_bonus
from src.model import OpenRouterClient
from src.runner import run_dev
from src.runtime import create_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Lab7 agentic retrieval workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser("preflight", help="check local models and database isolation")
    preflight.add_argument("--skip-gpu", action="store_true")
    ingest = commands.add_parser("ingest-bonus", help="extract all PDF pages, tables and visual regions")
    ingest.add_argument("--pdf", default=".lab-local/research/wdr2024-full-candidate.pdf")
    ingest.add_argument("--output", default="data/bonus/index")
    index = commands.add_parser("index-bonus", help="embed bonus corpus on CUDA into Lab7 pgvector")
    index.add_argument("--chunks", default="data/bonus/index/chunks.jsonl")
    commands.add_parser("reconcile-unknown-cost", help="count a timed-out API request reservation as fully spent")
    validate = commands.add_parser("validate-benchmark", help="check benchmark structure and gold source references")
    validate.add_argument("--suite", choices=("core", "bonus"), required=True)
    validate.add_argument("--questions", default=None)
    dev = commands.add_parser("dev", help="run one dev config without exposing gold to the agent")
    dev.add_argument("--suite", choices=("core", "bonus"), required=True)
    dev.add_argument("--config", choices=("D0", "L0", "H1", "H2"), required=True)
    dev.add_argument("--questions", default=None)
    dev.add_argument("--output", default=None)
    test = commands.add_parser("test", help="run a frozen test split with the selected or baseline config")
    test.add_argument("--suite", choices=("core", "bonus"), required=True)
    test.add_argument("--config", choices=("D0", "L0", "H1", "H2"), required=True)
    test.add_argument("--questions", default=None)
    test.add_argument("--output", default=None)
    smoke = commands.add_parser("smoke", help="one real agent run against a selected corpus")
    smoke.add_argument("--suite", choices=("core", "bonus"), required=True)
    smoke.add_argument("--config", choices=("D0", "L0", "H1", "H2"), default="D0")
    smoke.add_argument("--query", default=None)
    smoke.add_argument("--pilot", action="store_true", help="also apply the local pilot budget cap")
    smoke.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.command == "preflight":
        print(json.dumps(_preflight(args.skip_gpu), indent=2))
    elif args.command == "ingest-bonus":
        print(json.dumps(ingest_bonus(args.pdf, output_dir=args.output), ensure_ascii=False, indent=2))
    elif args.command == "index-bonus":
        print(json.dumps(index_bonus(args.chunks), ensure_ascii=False, indent=2))
    elif args.command == "reconcile-unknown-cost":
        bound = OpenRouterClient().reconcile_unknown_as_upper_bound()
        print(json.dumps({"status": "reconciled_upper_bound", "cost_usd_upper_bound": str(bound)}))
    elif args.command == "validate-benchmark":
        questions_path = args.questions or f"benchmark/{args.suite}/questions.jsonl"
        chunks_path = "data/core/chunks.json" if args.suite == "core" else "data/bonus/index/chunks.jsonl"
        if args.suite == "core":
            chunks = json.loads(Path(chunks_path).read_text(encoding="utf-8"))
        else:
            chunks = load_jsonl(chunks_path)
        print(json.dumps(validate_benchmark(load_jsonl(questions_path), chunks, suite=args.suite), indent=2))
    elif args.command == "dev":
        print(json.dumps(run_dev(args.suite, args.config, questions_path=args.questions, output_path=args.output), indent=2))
    elif args.command == "test":
        print(json.dumps(run_dev(args.suite, args.config, split="test", questions_path=args.questions,
                                 output_path=args.output), indent=2))
    elif args.command == "smoke":
        query = args.query or ("What does the source say about string find when a character is absent?"
                               if args.suite == "core" else "What does the report identify as the middle-income trap?")
        agent = create_agent(args.suite, config=args.config, pilot=args.pilot)
        trace = agent.run(query, query_id=f"smoke-{args.suite}", suite=args.suite, split="dev", config=args.config)
        raw = json.dumps(trace, ensure_ascii=False, indent=2)
        print(raw)
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw + "\n", encoding="utf-8")


def _preflight(skip_gpu: bool) -> dict:
    load_dotenv(override=False)
    result = {"model": os.environ.get("OPENROUTER_MODEL", "z-ai/glm-5.3-flash"),
              "provider": os.environ.get("OPENROUTER_PROVIDER", "wafer"),
              "core_text_provider": os.environ.get("OPENROUTER_CORE_PROVIDER", "relace"),
              "fallbacks": os.environ.get("OPENROUTER_ALLOW_FALLBACKS", "false").lower() == "true",
              "api_key_present": bool(os.environ.get("OPENROUTER_API_KEY", "").strip()),
              "bonus_pdf_present": Path(".lab-local/research/wdr2024-full-candidate.pdf").is_file()}
    if not result["api_key_present"]:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    if not skip_gpu:
        import torch
        result["cuda_available"] = torch.cuda.is_available()
        if not result["cuda_available"]:
            raise RuntimeError("CUDA is required for the selected Qwen embedding model")
        result["gpu_name"] = torch.cuda.get_device_name(0)
    from dotenv import load_dotenv as _load
    _load(override=False)
    import psycopg
    for name in ("DAY6_DATABASE_URL", "LAB7_DATABASE_URL"):
        url = os.environ.get(name, "").strip()
        if not url:
            raise RuntimeError(f"{name} is missing")
        if name == "LAB7_DATABASE_URL" and "55433" in url:
            raise RuntimeError("Lab7 database URL must not point to the Lab6 port")
        with psycopg.connect(url, options="-c default_transaction_read_only=on -c statement_timeout=10000") as conn:
            result[name] = conn.execute("SELECT current_setting('server_version')").fetchone()[0]
            result[name + "_extensions"] = [r[0] for r in conn.execute(
                "SELECT extname || '=' || extversion FROM pg_extension WHERE extname='vector'").fetchall()]
            if name == "LAB7_DATABASE_URL":
                row = conn.execute("SELECT count(*) FROM lab_chunks WHERE strategy='WDR'").fetchone()
                result["wdr_rows"] = row[0]
    return result


if __name__ == "__main__":
    main()
