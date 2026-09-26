"""
Metadata extraction for files and PDF document structures.
Supports PyMuPDF (fitz) with graceful fallback for basic PDF object parsing.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def get_filesystem_metadata(path: Path) -> Tuple[int, datetime]:
    """Retrieve size in bytes and last modification datetime."""
    stat = path.stat()
    size_bytes = stat.st_size
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    return size_bytes, mtime


def extract_pdf_metadata(path: Path) -> Tuple[Optional[int], Optional[str], Optional[str], Dict[str, Optional[str]], Optional[str]]:
    """
    Extract page_count, title, author, pdf_metadata dict, error.
    Tries PyMuPDF (fitz) first, falls back to direct trailer regex scanning.
    """
    error: Optional[str] = None
    page_count: Optional[int] = None
    title: Optional[str] = None
    author: Optional[str] = None
    metadata_dict: Dict[str, Optional[str]] = {}

    # Attempt PyMuPDF (fitz)
    try:
        import fitz  # type: ignore
        try:
            doc = fitz.open(str(path))
            page_count = len(doc)
            meta = doc.metadata or {}
            title = meta.get("title") or None
            author = meta.get("author") or None
            metadata_dict = {
                "format": meta.get("format"),
                "title": title,
                "author": author,
                "subject": meta.get("subject"),
                "keywords": meta.get("keywords"),
                "creator": meta.get("creator"),
                "producer": meta.get("producer"),
                "creationDate": meta.get("creationDate"),
                "modDate": meta.get("modDate"),
            }
            doc.close()
            return page_count, title, author, metadata_dict, None
        except Exception as e:
            error = f"PyMuPDF error: {str(e)}"
    except ImportError:
        pass

    # Fallback basic PDF trailer/object parser (safe, read-only binary scan)
    try:
        with open(path, "rb") as f:
            header = f.read(1024)
            if b"%PDF-" not in header:
                return None, None, None, {}, "Not a valid PDF file (missing %PDF- header)"

            f.seek(0)
            content = f.read()

        # Approximate page count via /Type\s*/Page\b
        pages = len(re.findall(rb"/Type\s*/Page\b", content))
        if pages > 0:
            page_count = pages

        # Look for Title and Author in metadata strings
        title_match = re.search(rb"/Title\s*\((.*?)\)", content)
        if title_match:
            try:
                title = title_match.group(1).decode("latin-1", errors="ignore").strip()
            except Exception:
                pass

        author_match = re.search(rb"/Author\s*\((.*?)\)", content)
        if author_match:
            try:
                author = author_match.group(1).decode("latin-1", errors="ignore").strip()
            except Exception:
                pass

        metadata_dict = {
            "title": title,
            "author": author,
            "pages_estimated": str(page_count) if page_count else None,
        }
        return page_count, title, author, metadata_dict, error
    except Exception as e:
        return None, None, None, {}, f"Error reading PDF: {str(e)}"
