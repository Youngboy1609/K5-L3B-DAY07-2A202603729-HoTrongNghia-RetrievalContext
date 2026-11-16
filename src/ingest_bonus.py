"""Full-document text/table inventory and local visual-region crop builder."""

from __future__ import annotations

import hashlib
import base64
import json
import re
from pathlib import Path
from typing import Any

import pdfplumber


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _token_windows(text: str, limit: int = 420, overlap: int = 40) -> list[str]:
    words = text.split()
    if not words:
        return []
    output = []
    start = 0
    while start < len(words):
        end = min(start + limit, len(words))
        output.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return output


def ingest_bonus(pdf_path: str | Path, *, output_dir: str | Path = "data/bonus/index",
                 crop_dir: str | Path = ".lab-local/research/wdr2024-crops") -> dict[str, Any]:
    pdf_path, output_dir, crop_dir = Path(pdf_path), Path(output_dir), Path(crop_dir)
    if not pdf_path.is_file() or pdf_path.suffix.casefold() != ".pdf":
        raise ValueError("a local PDF file is required")
    output_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=False) or ""
            page_tables = page.find_tables()
            page_errors: list[str] = []
            page_chunks: list[str] = []
            for ordinal, block in enumerate(_token_windows(text)):
                page_chunks.append(block)
                cid = f"wdr-p{page_no:03d}-text-{ordinal:02d}"
                chunks.append({"id": cid, "text": block, "source_id": "wdr2024", "source": "World Development Report 2024",
                               "page": page_no, "modality": "text", "bbox": None, "rights_status": "verify_before_redistribution"})
            table_count = 0
            for table_no, table in enumerate(page_tables, start=1):
                rows = table.extract() or []
                normalized = [[str(cell or "").strip() for cell in row] for row in rows]
                table_text = "\n".join(" | ".join(row) for row in normalized if any(row)).strip()
                if not table_text:
                    continue
                bbox = [round(float(v), 2) for v in table.bbox]
                cid = f"wdr-p{page_no:03d}-table-{table_no:02d}"
                caption_context = text[max(0, text.lower().find("table") - 240):][:500] if "table" in text.lower() else ""
                chunks.append({"id": cid, "text": f"Extracted table, preserve columns and units.\n{caption_context}\n{table_text}",
                               "source_id": "wdr2024", "source": "World Development Report 2024", "page": page_no,
                               "modality": "table", "bbox": bbox, "rights_status": "verify_before_redistribution"})
                table_count += 1
                regions.append({"id": cid, "page": page_no, "bbox": bbox, "modality": "table", "crop": None,
                                "caption": caption_context, "rights_status": "verify_before_redistribution"})
            visual_count = 0
            # Embedded PDF images are located precisely. Charts drawn as vector paths are represented
            # by full-page local visual regions and can be opened on demand by the agent.
            visual_objects = list(page.images)
            caption_hits = list(re.finditer(r"(?im)^\s*(?:figure|fig\.|chart|map|box)\s+[A-Z0-9.\-]+[^\n]*", text))
            for visual_no, image in enumerate(visual_objects, start=1):
                bbox = [round(float(image[k]), 2) for k in ("x0", "top", "x1", "bottom")]
                cid = f"wdr-p{page_no:03d}-image-{visual_no:02d}"
                crop_path = crop_dir / f"{cid}.png"
                try:
                    page.crop(tuple(image[k] for k in ("x0", "top", "x1", "bottom"))).to_image(resolution=120).save(crop_path)
                    crop_sha = _sha(crop_path)
                except Exception:
                    crop_sha = None
                    page_errors.append(f"crop_failed:{cid}")
                chunks.append({"id": cid, "text": "Visual region requiring image inspection; use open_region for source image.",
                               "source_id": "wdr2024", "source": "World Development Report 2024", "page": page_no,
                               "modality": "image", "bbox": bbox, "rights_status": "verify_before_redistribution"})
                regions.append({"id": cid, "page": page_no, "bbox": bbox, "crop": str(crop_path) if crop_sha else None,
                                "sha256": crop_sha, "caption": None, "modality": "image",
                                "rights_status": "verify_before_redistribution"})
                visual_count += 1
            for caption_no, match in enumerate(caption_hits, start=1):
                # A caption is indexed with its exact page/source; bbox is approximate text geometry
                # and is not treated as the figure crop or as visual evidence.
                line = match.group(0).strip()
                caption_id = f"wdr-p{page_no:03d}-caption-{caption_no:02d}"
                chunks.append({"id": caption_id, "text": line,
                               "source_id": "wdr2024", "source": "World Development Report 2024", "page": page_no,
                               "modality": "caption", "bbox": None, "rights_status": "verify_before_redistribution"})
                regions.append({"id": caption_id, "page": page_no, "bbox": [0, 0, float(page.width), float(page.height)],
                                "crop": None, "sha256": None, "caption": line, "modality": "caption_visual",
                                "rights_status": "verify_before_redistribution"})
            if not visual_objects and text.strip():
                cid = f"wdr-p{page_no:03d}-page-visual"
                regions.append({"id": cid, "page": page_no, "bbox": [0, 0, float(page.width), float(page.height)],
                                "crop": None, "sha256": None, "caption": None, "modality": "page_visual",
                                "rights_status": "verify_before_redistribution"})
            inventory.append({"page": page_no, "width": round(float(page.width), 2), "height": round(float(page.height), 2),
                              "text_chars": len(text), "text_chunks": len(page_chunks), "tables": table_count,
                              "embedded_images": visual_count, "captions": len(caption_hits),
                              "status": "indexed" if text.strip() or table_count or visual_count or caption_hits else "empty_or_unextractable",
                              "errors": page_errors})
    _write_jsonl(output_dir / "chunks.jsonl", chunks)
    _write_jsonl(output_dir / "page_inventory.jsonl", inventory)
    _write_jsonl(output_dir / "regions.jsonl", regions)
    summary = {"schema_version": 1, "source_pdf_sha256": _sha(pdf_path), "physical_pages": len(inventory),
               "indexed_chunks": len(chunks), "pages_with_text": sum(x["text_chars"] > 0 for x in inventory),
               "tables": sum(x["tables"] for x in inventory), "embedded_images": sum(x["embedded_images"] for x in inventory),
               "caption_mentions": sum(x["captions"] for x in inventory),
               "pages_with_processing_errors": [x["page"] for x in inventory if x["errors"]],
               "pages_empty_or_unextractable": [x["page"] for x in inventory if x["status"] != "indexed"],
               "all_region_rights_pending_review": True, "source_pdf_committed": False}
    (output_dir / "ingestion_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def make_region_opener(pdf_path: str | Path, regions_path: str | Path,
                       crop_root: str | Path = ".lab-local/research/wdr2024-crops",
                       *, page_by_id: dict[str, int] | None = None):
    """Create an ID-only resolver; callers never provide arbitrary paths or coordinates."""
    pdf_path, crop_root = Path(pdf_path).resolve(), Path(crop_root).resolve()
    regions = {row["id"]: row for row in
               (json.loads(line) for line in Path(regions_path).read_text(encoding="utf-8").splitlines() if line.strip())}
    page_visuals = {row["page"]: row for row in regions.values() if row.get("modality") == "page_visual"}
    page_by_id = page_by_id or {}

    def open_region(chunk_id: str) -> dict[str, Any] | None:
        import re
        parent_id = re.sub(r"-part-\d+$", "", chunk_id)
        region = regions.get(chunk_id) or regions.get(parent_id)
        if region is None:
            page = page_by_id.get(chunk_id) or page_by_id.get(parent_id)
            region = page_visuals.get(page)
        if region is None:
            return None
        local_path = Path(region["crop"]).resolve() if region.get("crop") else None
        if local_path and local_path.exists():
            if not local_path.is_relative_to(crop_root):
                raise ValueError("cached crop escapes the approved local crop directory")
            raw = local_path.read_bytes()
        else:
            with pdfplumber.open(pdf_path) as pdf:
                page_no = region["page"]
                if not isinstance(page_no, int) or not 1 <= page_no <= len(pdf.pages):
                    raise ValueError("invalid page reference")
                page = pdf.pages[page_no - 1]
                bbox = region.get("bbox") or [0, 0, page.width, page.height]
                if len(bbox) != 4 or not all(isinstance(v, (int, float)) for v in bbox):
                    raise ValueError("invalid region bbox")
                x0, top, x1, bottom = bbox
                x0, top = max(0, x0), max(0, top)
                x1, bottom = min(page.width, x1), min(page.height, bottom)
                if x1 <= x0 or bottom <= top:
                    raise ValueError("empty region bbox")
                image = page.crop((x0, top, x1, bottom)).to_image(resolution=220).original
                from io import BytesIO
                buffer = BytesIO()
                image.save(buffer, format="PNG", optimize=True)
                raw = buffer.getvalue()
        if len(raw) > 5_000_000:
            raise ValueError("rendered region exceeds the 5 MB image request limit")
        return {"id": chunk_id, "page": region["page"], "bbox": region.get("bbox"),
                "modality": region["modality"], "rights_status": region["rights_status"],
                "image_url": "data:image/png;base64," + base64.b64encode(raw).decode("ascii")}
    return open_region
