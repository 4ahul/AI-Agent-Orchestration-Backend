"""
PDF Processing Service.
- Multi-page support
- Structured extraction: text, headings, tables, metadata
- Corrupted file detection
- Memory-efficient streaming (no full file in memory)
"""
import hashlib
import io
from pathlib import Path
from typing import Any

import pdfplumber
import fitz  # PyMuPDF

from app.core.exceptions import PDFProcessingError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def compute_checksum(file_bytes: bytes) -> str:
    """SHA-256 checksum for duplicate detection."""
    return hashlib.sha256(file_bytes).hexdigest()


def validate_pdf_bytes(data: bytes) -> None:
    """Validate PDF magic bytes — catches corrupted/fake files early."""
    if not data.startswith(b"%PDF"):
        raise PDFProcessingError("File is not a valid PDF (missing PDF header)")
    if len(data) < 1024:
        raise PDFProcessingError("PDF file is too small to be valid")


def extract_pdf_data(file_path: str) -> dict[str, Any]:
    """
    Extract structured data from a PDF file.
    Returns a rich JSON-serializable dict consumed by PDF Analyzer Agent.
    Uses pdfplumber for text/tables and PyMuPDF for metadata.
    """
    path = Path(file_path)
    if not path.exists():
        raise PDFProcessingError(f"File not found: {file_path}")

    try:
        # ── Metadata extraction via PyMuPDF ───────────────────────
        with fitz.open(str(path)) as doc:
            metadata = dict(doc.metadata)
            page_count = doc.page_count
            toc = doc.get_toc()  # Table of contents / bookmarks

        # ── Text, Tables, Headings via pdfplumber ─────────────────
        pages_data: list[dict] = []
        all_text_blocks: list[str] = []

        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                tables = []

                # Extract tables if present
                raw_tables = page.extract_tables()
                for table in raw_tables:
                    if table:
                        cleaned = [
                            [cell.strip() if cell else "" for cell in row]
                            for row in table
                        ]
                        tables.append(cleaned)

                # Heuristic heading detection (larger/bold text blocks)
                words = page.extract_words(extra_attrs=["size", "fontname"])
                headings = _extract_headings(words)

                pages_data.append({
                    "page_number": i + 1,
                    "text": page_text,
                    "headings": headings,
                    "tables": tables,
                    "word_count": len(page_text.split()),
                })
                all_text_blocks.append(page_text)

        full_text = "\n\n".join(all_text_blocks)
        key_entities = _extract_key_entities(full_text)

        result = {
            "filename": path.name,
            "page_count": page_count,
            "metadata": {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "creation_date": metadata.get("creationDate", ""),
            },
            "table_of_contents": [
                {"level": item[0], "title": item[1], "page": item[2]} for item in toc
            ],
            "pages": pages_data,
            "full_text": full_text[:50000],  # Cap to avoid token explosion
            "word_count": len(full_text.split()),
            "key_entities": key_entities,
            "summary_hint": full_text[:2000],  # First ~2000 chars as context
        }

        logger.info("PDF extracted", filename=path.name, pages=page_count)
        return result

    except PDFProcessingError:
        raise
    except Exception as e:
        logger.error("PDF extraction failed", error=str(e), path=str(path))
        raise PDFProcessingError(f"Failed to extract PDF content: {str(e)}")


def _extract_headings(words: list[dict]) -> list[str]:
    """Detect likely headings by font size threshold."""
    if not words:
        return []

    try:
        sizes = [w.get("size", 12) for w in words if w.get("size")]
        if not sizes:
            return []
        avg_size = sum(sizes) / len(sizes)
        threshold = avg_size * 1.3

        seen = set()
        headings = []
        for word in words:
            size = word.get("size", 0)
            text = word.get("text", "").strip()
            if size >= threshold and text and text not in seen and len(text) > 3:
                seen.add(text)
                headings.append(text)
        return headings[:20]  # Cap at 20 headings per page
    except Exception:
        return []


def _extract_key_entities(text: str) -> dict[str, list[str]]:
    """
    Simple heuristic entity extraction.
    In production this can be replaced with a SpaCy NER call.
    """
    import re

    # Email addresses
    emails = re.findall(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b", text)
    # Phone numbers (basic)
    phones = re.findall(r"\+?\d[\d\s\-().]{7,}\d", text)
    # URLs
    urls = re.findall(r"https?://[^\s<>\"{}|\\^`\[\]]+", text)
    # Capitalized proper nouns (heuristic)
    proper_nouns = re.findall(r"\b[A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})*\b", text)

    return {
        "emails": list(set(emails))[:10],
        "phone_numbers": list(set(phones))[:5],
        "urls": list(set(urls))[:10],
        "proper_nouns": list(set(proper_nouns))[:30],
    }
