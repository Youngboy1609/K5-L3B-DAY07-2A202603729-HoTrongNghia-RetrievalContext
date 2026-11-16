"""Command line for ingestion, dev selection, freeze and held-out test."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from uuid import uuid4
from importlib.metadata import version

from dotenv import load_dotenv
from .chunking import by_paragraph, fixed_size
from .embeddings import QwenEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf
from .store import PgVectorStore

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "starter"
SOURCE = REPO / "data/thinkpython2.pdf"
QUESTIONS = REPO / "benchmark/questions.jsonl"
PROTOCOL = REPO / "benchmark/protocol.json"
CONFIG = ROOT / "artifacts/strategies.json"
LOCAL = REPO / ".lab-local"
RESULTS = ROOT / "results"


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_config() -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    a, b, c = config["A"], config["B"], config["C"]
    if a["chunking"] != "fixed" or b["chunking"] != "paragraph" or c["chunking"] != b["chunking"]:
        raise ValueError("Expected fixed A and identical paragraph chunking for B/C")
    if b["size_chars"] != c["size_chars"] or b["overlap"] != c["overlap"]:
        raise ValueError("B and C must use the same chunk boundaries")
    if (config["dimensions"] != QwenEmbedder.dimensions or config["device"] != "cuda"
            or config["dtype"] != "float16" or config["metric"] != "cosine"
            or config["search"] != "exact" or config["query_prompt"] != "query"
            or config["document_prompt"] is not None or not config["normalized"]):
        raise ValueError("Embedding or retrieval config does not match this implementation")
    return config


def build():
    config = load_config()
    pages = load_pdf(SOURCE, "think-python-2e", "data/thinkpython2.pdf")
    a = [c for page in pages for c in fixed_size(page, config["A"]["size_chars"], config["A"]["overlap"])]
    b = [c for page in pages for c in by_paragraph(page, config["B"]["size_chars"])]
    return pages, {"A": a, "B": b, "C": b}


def embedding_fingerprint(config: dict) -> str:
    values = {key: config[key] for key in (
        "model", "model_revision", "dimensions", "dtype", "max_seq_length",
        "normalized", "query_prompt", "document_prompt")}
    raw = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def ingest():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
    started = time.perf_counter()
    pages, chunks = build()
    config = load_config()
    LOCAL.mkdir(parents=True, exist_ok=True)
    cache_path = LOCAL / "embeddings-v1.json"
    model_fingerprint = embedding_fingerprint(config)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    if cache.get("embedding_fingerprint") != model_fingerprint or cache.get("schema_version") != 1:
        cache = {"schema_version": 1, "embedding_fingerprint": model_fingerprint, "vectors": {}}
    vectors_by_id = cache["vectors"]
    cached_ids_before_run = set(vectors_by_id)

    embedder = QwenEmbedder(config["model"], batch_size=config["batch_size"],
                            revision=config["model_revision"], max_seq_length=config["max_seq_length"])
    new_chunks = {c.chunk_id: c.text for group in (chunks["A"], chunks["B"]) for c in group
                  if c.chunk_id not in vectors_by_id}
    if new_chunks:
        vectors = embedder.embed_documents(list(new_chunks.values()))
        vectors_by_id.update({key: vec for key, vec in zip(new_chunks, vectors, strict=True)})
    cache_write_started = time.perf_counter()
    temporary_cache = cache_path.with_suffix(".tmp")
    temporary_cache.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
    temporary_cache.replace(cache_path)
    cache_write_seconds = time.perf_counter() - cache_write_started

    store = PgVectorStore(os.environ["DATABASE_URL"], embedder.dimensions)
    store.create_schema()
    db_started = time.perf_counter()
    for strategy, group in chunks.items():
        store.upsert(strategy, group, [vectors_by_id[c.chunk_id] for c in group])
    db_write_seconds = time.perf_counter() - db_started
    lengths = [len(c.text) for group in (chunks["A"], chunks["B"]) for c in group]
    token_lengths = [len(embedder.model.tokenizer(c.text, add_special_tokens=True, truncation=False)["input_ids"])
                     for group in (chunks["A"], chunks["B"]) for c in group]
    log = {
        "run_id": run_id, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "pages": len(pages), "characters": sum(len(p.text) for p in pages),
        "empty_pages": [], "chunk_counts": {s: len(v) for s, v in chunks.items()},
        "char_length": {"min": min(lengths), "median": statistics.median(lengths), "max": max(lengths)},
        "document_token_length_max": max(token_lengths),
        "new_embeddings": len(new_chunks),
        "cache_hits": len({c.chunk_id for group in (chunks["A"], chunks["B"]) for c in group} & cached_ids_before_run),
        "cache_entries": len(vectors_by_id), "embedding_cache_fingerprint": model_fingerprint,
        "model_load_and_probe_seconds": round(embedder.load_seconds, 3),
        "document_encode_seconds": round(getattr(embedder, "last_encode_seconds", 0.0), 3),
        "cache_write_seconds": round(cache_write_seconds, 3),
        "database_write_seconds": round(db_write_seconds, 3),
        "total_ingest_seconds": round(time.perf_counter() - started, 3),
        "peak_vram_bytes": int(__import__("torch").cuda.max_memory_allocated()),
        "peak_vram_reserved_bytes": int(__import__("torch").cuda.max_memory_reserved()),
        "runtime": {
            "python": sys.version.split()[0],
            "gpu": __import__("torch").cuda.get_device_name(0),
            "cuda_runtime": __import__("torch").version.cuda,
            "packages": {name: version(name) for name in (
                "pdfplumber", "sentence-transformers", "transformers", "torch", "psycopg")},
        },
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "ingestion_runs.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(log, ensure_ascii=False) + "\n")
    write_json(RESULTS / "ingestion_log.json", log)
    snapshot = store.snapshot()
    write_json(RESULTS / "store_snapshot.json", snapshot)


def code_fingerprint() -> str:
    digest = hashlib.sha256()
    paths = sorted((ROOT / "src").glob("*.py")) + [ROOT / "requirements.txt"]
    for path in paths:
        digest.update(path.relative_to(REPO).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def fingerprint(store: PgVectorStore | None = None):
    config = load_config()
    store = store or PgVectorStore(os.environ["DATABASE_URL"], config["dimensions"])
    files = {
        "source_sha256": SOURCE, "questions_sha256": QUESTIONS,
        "protocol_sha256": PROTOCOL,
        "strategies_sha256": CONFIG,
    }
    value = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}
    value.update({"code_sha256": code_fingerprint(), "model": config["model"],
                  "model_revision": config["model_revision"],
                  "embedding_fingerprint": embedding_fingerprint(config),
                  "store_snapshot": store.snapshot()})
    return value


def evaluate(split: str):
    config = load_config()
    frozen = LOCAL / "frozen.json"
    store = PgVectorStore(os.environ["DATABASE_URL"], config["dimensions"])
    current = fingerprint(store)
    if split == "test":
        if not frozen.exists() or json.loads(frozen.read_text(encoding="utf-8")) != current:
            raise RuntimeError("Test is locked until freeze; code, inputs, model, config, or indexed rows changed")
    elif split == "dev":
        write_json(LOCAL / "dev_fingerprint.json", current)
    pages, chunks = build()
    del pages, chunks
    embedder = QwenEmbedder(config["model"], batch_size=config["batch_size"],
                            revision=config["model_revision"], local_files_only=True,
                            max_seq_length=config["max_seq_length"])
    questions = [q for q in read_jsonl(QUESTIONS) if q["split"] == split]
    traces = []
    for q in questions:
        query_started = time.perf_counter()
        qvector = embedder.embed_query(q["question"])
        query_embedding_seconds = time.perf_counter() - query_started
        filters = {"chapter": q["filter"]["chapter"]} if q.get("filter") else None
        for strategy in ("A", "B", "C"):
            used = filters if strategy == "C" else None
            search_started = time.perf_counter()
            hits = store.search(strategy, qvector, 3, used)
            search_seconds = time.perf_counter() - search_started
            result = evaluate_query(q, hits)
            traces.append({"strategy": strategy, "split": split, "question": q,
                           "filter_applied": used,
                           "query_embedding_seconds": round(query_embedding_seconds, 6),
                           "search_seconds": round(search_seconds, 6), **result})
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"traces-{split}.jsonl"
    path.write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in traces), encoding="utf-8")
    return traces


def select_dev():
    traces = read_jsonl(RESULTS / "traces-dev.jsonl")
    metrics = summarize(traces)
    candidates = {}
    for strategy in ("A", "B", "C"):
        rows = [t for t in traces if t["strategy"] == strategy]
        filter_rows = [t for t in rows if t["question"].get("filter")]
        compliant = [t for t in filter_rows if all(
            hit["metadata"].get("chapter") == t["question"]["filter"]["chapter"] for hit in t["hits"])]
        candidates[strategy] = {
            "evidence_hit_at_3": metrics[f"{strategy}/dev"]["evidence_hit_at_3"],
            "hit_at_1": metrics[f"{strategy}/dev"]["hit_at_1"],
            "filter_compliance": ({"numerator": len(compliant), "denominator": len(filter_rows)}
                                  if strategy == "C" else None),
            "median_search_seconds": round(statistics.median(t["search_seconds"] for t in rows), 6),
        }
    choice = sorted(("A", "B", "C"), key=lambda s: (
        -candidates[s]["evidence_hit_at_3"]["numerator"],
        -candidates[s]["hit_at_1"]["numerator"],
        -(candidates[s]["filter_compliance"]["numerator"] if candidates[s]["filter_compliance"] else -1),
        {"C": 0, "B": 1, "A": 2}[s]))[0]
    write_json(RESULTS / "selection.json", {
        "selected_strategy": choice,
        "criterion": "Dev only: Evidence Hit@3, then Hit@1, then C filter compliance; final tie prefers the filter-capable C. Latency is reported but excluded because the sample is short and query order is fixed.",
        "candidates": candidates,
        "status": "provisional until student completes the manual coherence, metadata, and grounding audit",
    })


def build_manual_audit():
    load_config()
    questions = {q["id"]: q for q in read_jsonl(QUESTIONS)}
    sample_ids = json.loads(PROTOCOL.read_text(encoding="utf-8"))["manual_audit_sample"]
    traces = read_jsonl(RESULTS / "traces-test.jsonl")
    trace_by_key = {(trace["question_id"], trace["strategy"]): trace for trace in traces}
    pages, chunks = build()
    page_chapters = {page.page: page.metadata["chapter"] for page in pages}
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    coherence_rows = []
    for anchor in protocol["coherence_anchors"]:
        source_text = next(page.text for page in pages if page.page == anchor["page"])
        pattern = r"\s+".join(re.escape(part) for part in anchor["quote"].split())
        match = re.search(pattern, source_text, re.IGNORECASE)
        if not match:
            raise ValueError(f"Coherence anchor {anchor['id']} is missing from extracted page {anchor['page']}")
        for strategy in ("A", "B", "C"):
            covering = [chunk for chunk in chunks[strategy] if chunk.page == anchor["page"]
                        and chunk.start_offset <= match.start() and chunk.end_offset >= match.end()]
            overlapping = [chunk for chunk in chunks[strategy] if chunk.page == anchor["page"]
                           and chunk.start_offset < match.end() and chunk.end_offset > match.start()]
            selected = covering or overlapping
            coherence_rows.append({
                "strategy": strategy, "anchor_id": anchor["id"], "page": anchor["page"],
                "source_offset": match.start(), "source_quote": anchor["quote"],
                "coverage": "full" if covering else ("partial" if overlapping else "missing"),
                "chunks": [{"chunk_id": chunk.chunk_id, "start_offset": chunk.start_offset,
                            "end_offset": chunk.end_offset, "text": chunk.text} for chunk in selected],
                "student_score_0_to_2": None, "student_reason": None,
            })

    metadata_rows, grounding_rows = [], []
    for question_id in sample_ids:
        question = questions[question_id]
        for strategy in ("A", "B", "C"):
            trace = trace_by_key[(question_id, strategy)]
            expected_filter = question.get("filter", {}).get("chapter") if strategy == "C" else None
            for rank, hit in enumerate(trace["hits"], start=1):
                metadata = hit["metadata"]
                expected_chapter = page_chapters.get(metadata.get("page"))
                metadata_rows.append({
                    "strategy": strategy, "question_id": question_id, "rank": rank,
                    "chunk_id": hit["chunk_id"], "text": hit["text"], "metadata": metadata,
                    "expected_from_whitelist": {"document_id": "think-python-2e",
                                                "source": "data/thinkpython2.pdf",
                                                "page": metadata.get("page"), "chapter": expected_chapter},
                    "automated_mapping_check": {
                        "document_id": metadata.get("document_id") == "think-python-2e",
                        "source": metadata.get("source") == "data/thinkpython2.pdf",
                        "page_in_whitelist": expected_chapter is not None,
                        "chapter_matches_page": metadata.get("chapter") == expected_chapter,
                    },
                    "filter_expected_chapter": expected_filter,
                    "filter_matches": (expected_filter is None or metadata.get("chapter") == expected_filter),
                    "student_confirmed": None, "student_note": None,
                })
            grounding_rows.append({
                "strategy": strategy, "question_id": question_id,
                "question": question["question"], "expected_answer": question["expected_answer"],
                "gold_page": question["gold_page"], "gold_evidence": question["evidence_quote"],
                "filter_applied": trace["filter_applied"],
                "top3": [{"rank": rank, "chunk_id": hit["chunk_id"], "page": hit["metadata"].get("page"),
                          "text": hit["text"], "automatic_exact_evidence_hit": trace["hit_flags"][rank - 1]}
                         for rank, hit in enumerate(trace["hits"], start=1)],
                "student_score_0_to_2": None, "student_reason": None,
            })

    write_json(RESULTS / "manual_review.json", {
        "status": "pending student review; no human scores have been entered",
        "reviewer": None, "review_date": None,
        "sample_question_ids": sample_ids,
        "coherence_scale": {"0": "fragment/unusable", "1": "relevant but incomplete", "2": "coherent and independently understandable"},
        "grounding_scale": {"0": "no useful evidence", "1": "relevant but incomplete", "2": "top-3 supports answer with source trace"},
        "coherence_rows": coherence_rows,
        "metadata_rows": metadata_rows,
        "grounding_rows": grounding_rows,
        "automated_checks_are_not_manual_judgments": True,
        "instructions": "Inspect each displayed chunk and compare metadata/evidence to the PDF. Enter reviewer/date, a 0-2 score and a concise reason in the corresponding null fields. Do not replace nulls with AI-generated ratings.",
    })


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "dev", "freeze", "test", "audit"])
    args = parser.parse_args()
    if args.command == "ingest":
        ingest()
    elif args.command == "dev":
        traces = evaluate("dev")
        write_json(RESULTS / "metrics-dev.json", summarize(traces))
    elif args.command == "freeze":
        current = fingerprint()
        dev_marker = LOCAL / "dev_fingerprint.json"
        if not dev_marker.exists() or json.loads(dev_marker.read_text(encoding="utf-8")) != current:
            raise RuntimeError("Run dev on the current code, inputs, configuration, model, and database before freeze")
        write_json(LOCAL / "frozen.json", current)
        select_dev()
    elif args.command == "test":
        traces = evaluate("test")
        write_json(RESULTS / "metrics-test.json", summarize(traces))
    elif args.command == "audit":
        build_manual_audit()


if __name__ == "__main__":
    main()
