"""Page-bounded fixed-window and paragraph-aware chunking."""
import hashlib
import re
from .models import Chunk, DocumentPage


def _chunk(page: DocumentPage, text: str, start: int, end: int, strategy: str) -> Chunk:
    identity = f"{page.document_id}:{page.page}:{strategy}:{start}:{end}:{text}"
    metadata = dict(page.metadata) | {"document_id": page.document_id, "source": page.source,
                                     "page": page.page, "printed_page": page.printed_page}
    return Chunk(hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24],
                 page.document_id, page.source, page.page, text, metadata, start, end)


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split each page into fixed character windows with stable source offsets."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("size must be positive and overlap must be in [0, size)")
    chunks = []
    step = size - overlap
    for start in range(0, len(page.text), step):
        end = min(start + size, len(page.text))
        text = page.text[start:end].strip()
        if text:
            chunks.append(_chunk(page, text, start, end, "A"))
        if end == len(page.text):
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Pack source blocks to a strict character cap, preferring line/sentence boundaries."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    blocks = [(m.start(), m.end(), m.group().strip()) for m in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", page.text, re.S)]
    pieces: list[tuple[int, int, str]] = []
    for start, end, block in blocks:
        if len(block) <= max_size:
            pieces.append((start, end, block))
            continue
        cursor = 0
        while cursor < len(block):
            stop = min(cursor + max_size, len(block))
            if stop < len(block):
                minimum = cursor + max(1, int(max_size * 0.55))
                line_boundary = block.rfind("\n", minimum, stop)
                sentence_boundary = block.rfind(". ", minimum, stop)
                word_boundary = block.rfind(" ", minimum, stop)
                if line_boundary >= minimum:
                    stop = line_boundary
                elif sentence_boundary >= minimum:
                    stop = sentence_boundary + 1
                elif word_boundary >= minimum:
                    stop = word_boundary
            local_start = cursor
            raw_value = block[local_start:stop]
            value = raw_value.strip()
            if value:
                leading = len(raw_value) - len(raw_value.lstrip())
                actual_start = start + local_start + leading
                pieces.append((actual_start, actual_start + len(value), value))
            cursor = max(stop, cursor + 1)
    chunks: list[Chunk] = []
    current: list[tuple[int, int, str]] = []
    current_len = 0
    for item in pieces:
        start, end, text = item
        separator_len = 2 if current else 0
        if current and current_len + separator_len + len(text) > max_size:
            chunks.append(_chunk(page, "\n\n".join(part[2] for part in current), current[0][0], current[-1][1], "B"))
            current, current_len = [], 0
        current.append(item)
        current_len += (2 if len(current) > 1 else 0) + len(text)
    if current:
        chunks.append(_chunk(page, "\n\n".join(part[2] for part in current), current[0][0], current[-1][1], "B"))
    return chunks
