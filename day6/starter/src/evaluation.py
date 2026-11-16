"""Evidence-aware retrieval metrics; manual quality labels stay separate."""
from typing import Any
import re
import unicodedata


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text).casefold()).strip()


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    golds = question.get("gold_evidence") or [{
        "gold_source_id": question["gold_source_id"], "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
    }]
    def is_hit(item: dict[str, Any]) -> bool:
        for gold in golds:
            metadata=item.get("metadata",{})
            if metadata.get("document_id") != gold["gold_source_id"] or metadata.get("page") != gold["gold_page"]:
                continue
            quote = _norm(gold["evidence_quote"])
            if quote and quote in _norm(item.get("text","")):
                return True
        return False
    flags=[is_hit(hit) for hit in hits]
    return {"question_id":question["id"],"hit_flags":flags,
            "hit_at_1":bool(flags and flags[0]),"evidence_hit_at_3":any(flags[:3]),"hits":hits}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str,str],list[dict[str,Any]]] = {}
    for trace in traces:
        groups.setdefault((trace["strategy"],trace["split"]),[]).append(trace)
    return {f"{strategy}/{split}":{
        "hit_at_1":{"numerator":sum(t["hit_at_1"] for t in rows),"denominator":len(rows)},
        "evidence_hit_at_3":{"numerator":sum(t["evidence_hit_at_3"] for t in rows),"denominator":len(rows)},
    } for (strategy,split),rows in sorted(groups.items())}
