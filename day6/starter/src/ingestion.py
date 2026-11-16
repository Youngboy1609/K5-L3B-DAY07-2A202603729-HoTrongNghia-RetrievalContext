"""Read the selected PDF pages and preserve page-level provenance."""
import re
import unicodedata
from pathlib import Path
import pdfplumber
from .models import DocumentPage

SELECTED_PAGES = {
    **{page: (8, "Strings", page - 22) for page in range(93, 101)},
    **{page: (10, "Lists", page - 22) for page in range(111, 122)},
    **{page: (11, "Dictionaries", page - 22) for page in range(125, 134)},
    **{page: (12, "Tuples", page - 22) for page in range(137, 144)},
}

def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract selected physical pages; fail if any selected page is blank."""
    pages: list[DocumentPage] = []
    with pdfplumber.open(path) as pdf:
        for physical_page, (chapter, title, printed_page) in SELECTED_PAGES.items():
            if physical_page > len(pdf.pages):
                raise ValueError(f"PDF is missing physical page {physical_page}")
            layout_text = pdf.pages[physical_page - 1].extract_text(layout=True, x_tolerance=1) or ""
            text = normalize_text(layout_text, remove_page_margin=True)
            if len(text) < 300:
                raise ValueError(f"Selected page {physical_page} has only {len(text)} characters")
            pages.append(DocumentPage(
                document_id=document_id, source=source, page=physical_page,
                printed_page=printed_page, text=text,
                metadata={"chapter": chapter, "chapter_title": title},
            ))
    return pages


def normalize_text(text: str, remove_page_margin: bool = False) -> str:
    """Normalize extracted text, optionally removing the PDF's common left margin."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if remove_page_margin:
        indents = [len(line) - len(line.lstrip(" \t")) for line in lines if line.strip()]
        margin = min(indents, default=0)
        lines = [line[margin:] if line.strip() else "" for line in lines]
    normalized = []
    for line in lines:
        line = re.sub(r"[\t ]+$", "", line)
        if line:
            leading = line[:len(line) - len(line.lstrip(" "))]
            body = re.sub(r"[\t ]{2,}", " ", line[len(leading):])
            line = leading + body
        normalized.append(line)
    joined = re.sub(r"(?<=[A-Za-z])-\n(?=[a-z])", "", "\n".join(normalized))
    return re.sub(r"\n{3,}", "\n\n", joined).strip()
