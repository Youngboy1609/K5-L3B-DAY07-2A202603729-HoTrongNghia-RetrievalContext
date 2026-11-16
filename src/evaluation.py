"""Benchmark integrity checks and deterministic retrieval metric aggregation."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


BONUS_GROUPS = {
    "dev": {"table": 5, "image_diagram": 4, "chart": 4, "multihop": 4, "text": 3, "unanswerable": 4},
    "test": {"table": 6, "image_diagram": 5, "chart": 5, "multihop": 4, "text": 4, "unanswerable": 6},
}


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("benchmark is empty")
    return rows


def validate_benchmark(rows: list[dict[str, Any]], chunks: list[dict[str, Any]], *, suite: str) -> dict[str, Any]:
    if suite not in {"core", "bonus"}:
        raise ValueError("suite must be core or bonus")
    chunk_by_id = {row.get("id"): row for row in chunks}
    if not chunks or len(chunk_by_id) != len(chunks) or None in chunk_by_id:
        raise ValueError("corpus chunk IDs must be present and unique")
    ids: set[str] = set()
    normalized_questions: set[str] = set()
    groups: dict[str, Counter] = {"dev": Counter(), "test": Counter()}
    counts = {split: {"answerable": 0, "unanswerable": 0} for split in ("dev", "test")}
    for question in rows:
        qid = question.get("id")
        split = question.get("split")
        prompt = question.get("question")
        if not isinstance(qid, str) or not qid.strip() or qid in ids:
            raise ValueError("benchmark question IDs must be unique non-empty strings")
        ids.add(qid)
        if split not in counts or not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"question {qid}: invalid split or prompt")
        normalized = re.sub(r"\W+", " ", unicodedata.normalize("NFKC", prompt).casefold()).strip()
        if normalized in normalized_questions:
            raise ValueError(f"question {qid}: duplicate normalized prompt")
        normalized_questions.add(normalized)
        answerable = question.get("answerable")
        gold = question.get("gold")
        if not isinstance(answerable, bool) or not isinstance(gold, list):
            raise ValueError(f"question {qid}: answerable and gold are required")
        if answerable:
            if not isinstance(question.get("expected_answer"), str) or not question["expected_answer"].strip() or not gold:
                raise ValueError(f"question {qid}: answerable entries need answer and gold")
            for evidence in gold:
                cid = evidence.get("chunk_id")
                source = chunk_by_id.get(cid)
                if source is None or source.get("source_id") != evidence.get("source_id") or source.get("page") != evidence.get("page"):
                    raise ValueError(f"question {qid}: gold chunk/source/page does not resolve")
                quote = evidence.get("evidence")
                if not isinstance(quote, str) or not quote or quote not in source.get("text", ""):
                    raise ValueError(f"question {qid}: evidence quote is not in the cited source chunk")
            if question.get("primary_group") == "unanswerable":
                raise ValueError(f"question {qid}: answerable question cannot be in unanswerable group")
            counts[split]["answerable"] += 1
        else:
            if gold or not isinstance(question.get("absence_reason"), str) or not question["absence_reason"].strip():
                raise ValueError(f"question {qid}: unanswerable entries need an empty gold list and absence_reason")
            if question.get("primary_group") not in {None, "unanswerable"}:
                raise ValueError(f"question {qid}: unanswerable question has an answerable group")
            counts[split]["unanswerable"] += 1
        if suite == "bonus":
            group = question.get("primary_group")
            if group not in BONUS_GROUPS[split]:
                raise ValueError(f"question {qid}: invalid bonus primary_group")
            groups[split][group] += 1
            if group == "multihop" and len({(g.get("source_id"), g.get("page")) for g in gold}) < 2:
                raise ValueError(f"question {qid}: multi-hop question needs evidence from at least two pages")
    if suite == "core":
        expected = {"dev": {"answerable": 16, "unanswerable": 2}, "test": {"answerable": 6, "unanswerable": 2}}
        if len(rows) != 26 or counts != expected:
            raise ValueError(f"core suite must contain 26 cases with counts {expected}; got {counts}")
    else:
        if len(rows) != 54:
            raise ValueError("bonus suite must contain exactly 54 cases (24 dev + 30 test)")
        for split, expected_groups in BONUS_GROUPS.items():
            if dict(groups[split]) != expected_groups:
                raise ValueError(f"bonus {split} group counts must be {expected_groups}; got {dict(groups[split])}")
    return {"suite": suite, "total": len(rows), "counts": counts,
            "groups": {split: dict(counter) for split, counter in groups.items()},
            "semantic_dev_test_overlap_review": "manual review required"}


def retrieval_metrics(rows: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    question_by_id = {row["id"]: row for row in rows}
    matched = [trace for trace in traces if trace.get("query_id") in question_by_id]
    answerable = [trace for trace in matched if question_by_id[trace["query_id"]]["answerable"]]
    if not answerable:
        return {"answerable_n": 0, "hit_at_1": None, "evidence_hit_at_3": None, "context_evidence_rate": None}
    at1 = at3 = context_hits = 0
    for trace in answerable:
        q = question_by_id[trace["query_id"]]
        required = {e["chunk_id"] for e in q["gold"]}
        events = [e for e in trace.get("events", []) if e.get("type") == "tool" and e.get("name") == "search"]
        first_rank = events[0].get("ranked_ids", events[0].get("evidence_ids", [])) if events else []
        at1 += int(bool(required.intersection(first_rank[:1])))
        at3 += int(required.issubset(set(first_rank[:3])))
        context_ids = {c.get("id") for c in trace.get("contexts", [])}
        context_hits += int(required.issubset(context_ids))
    n = len(answerable)
    return {"answerable_n": n, "hit_at_1": {"n": at1, "N": n, "rate": at1 / n},
            "evidence_hit_at_3": {"n": at3, "N": n, "rate": at3 / n},
            "context_evidence_rate": {"n": context_hits, "N": n, "rate": context_hits / n}}


def source_aware_evidence_match(gold: dict[str, Any], candidates: list[dict[str, Any]]) -> bool:
    """Match original evidence to a retrieved child only when its text supports the quote."""
    parent_id = gold.get("chunk_id")
    source_id = gold.get("source_id")
    page = gold.get("page")
    evidence = gold.get("evidence")
    if not all(isinstance(value, str) and value for value in (parent_id, source_id, evidence)):
        return False
    for row in candidates:
        metadata = row.get("metadata") or {}
        if (row.get("parent_id", metadata.get("parent_id", row.get("id"))) != parent_id
                or (row.get("source_id") or row.get("source")) != source_id
                or row.get("page") != page):
            continue
        if evidence in str(row.get("text", "")):
            return True
    return False


def source_aware_metrics(rows: list[dict[str, Any]], traces: list[dict[str, Any]],
                         corpus: list[dict[str, Any]]) -> dict[str, Any]:
    """Quote/provenance diagnostic, not a semantic or visual correctness grade."""
    questions = {q["id"]: q for q in rows if q["answerable"]}
    by_id = {c["id"]: c for c in corpus}
    n = top1 = top3 = contexts = 0
    for trace in traces:
        q = questions.get(trace["query_id"])
        if not q:
            continue
        n += 1
        searches = [e for e in trace.get("events", []) if e.get("name") == "search"]
        ranks = searches[0].get("ranked_ids", []) if searches else []
        # Preserve the same top-k positions even if a corpus ID is missing.
        first = [by_id[cid] for cid in ranks[:1] if cid in by_id]
        three = [by_id[cid] for cid in ranks[:3] if cid in by_id]
        gold = q["gold"]
        top1 += int(any(source_aware_evidence_match(g, first) for g in gold))
        top3 += int(all(source_aware_evidence_match(g, three) for g in gold))
        sent = []
        for row in trace.get("contexts", []):
            # Only provenance may be restored from corpus, never unsent text.
            original = by_id.get(row["id"], {})
            sent.append({**original, **row, "source_id": row.get("source_id") or original.get("source_id")})
        contexts += int(all(source_aware_evidence_match(g, sent) for g in gold))
    metric = lambda count: {"n": count, "N": n, "rate": count / n if n else None}
    return {"version": "source_quote_v1", "answerable_n": n, "hit_at_1": metric(top1),
            "evidence_hit_at_3": metric(top3), "context_evidence_rate": metric(contexts),
            "limitation": "Exact source/page/parent and quote required; visual facts and semantic equivalents need review."}
