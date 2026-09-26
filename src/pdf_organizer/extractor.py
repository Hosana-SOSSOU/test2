"""
Document text extraction and quality inspection.
Distinguishes between standard digital PDFs and scanned documents needing OCR.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path
from typing import Optional
from .config import OCRConfig
from .hashing import compute_file_sha256
from .metadata import extract_pdf_metadata, get_filesystem_metadata
from .models import Document, OCRStatus, TextStatus


class DocumentExtractor:
    """Extracts text, metadata, and performs text quality assessment."""

    def __init__(self, ocr_config: Optional[OCRConfig] = None) -> None:
        self.ocr_config = ocr_config or OCRConfig()

    def process(self, path: Path, compute_hash: bool = True) -> Document:
        """Fully inspect and extract information from a PDF file."""
        path = Path(path).resolve()

        # Step 1: Filesystem metadata
        try:
            size_bytes, mtime = get_filesystem_metadata(path)
        except OSError as e:
            return Document(
                path=path,
                filename=path.name,
                size_bytes=0,
                modified_at=mtime if "mtime" in locals() else None,  # type: ignore
                text_status=TextStatus.ERROR,
                error=f"Filesystem access error: {str(e)}",
            )

        # Step 2: Hashing
        sha256: Optional[str] = None
        if compute_hash:
            try:
                sha256 = compute_file_sha256(path)
            except OSError as e:
                return Document(
                    path=path,
                    filename=path.name,
                    size_bytes=size_bytes,
                    modified_at=mtime,
                    text_status=TextStatus.ERROR,
                    error=f"Hashing error: {str(e)}",
                )

        # Step 3: PDF structure and metadata
        page_count, title, author, pdf_metadata, meta_error = extract_pdf_metadata(path)

        # Step 4: Text extraction
        extracted_text, extract_error = self._extract_raw_text(path)
        combined_error = meta_error or extract_error

        text_length = len(extracted_text.strip())

        # Step 5: Text quality analysis & OCR need evaluation
        text_status = TextStatus.TEXT_AVAILABLE
        ocr_status = OCRStatus.NOT_REQUIRED

        if combined_error and not extracted_text:
            text_status = TextStatus.ERROR
            ocr_status = OCRStatus.FAILED
        elif page_count is not None and page_count > 0:
            avg_chars_per_page = text_length / max(page_count, 1)
            # If text length is nearly zero or average chars per page is below threshold
            if text_length < 20 or avg_chars_per_page < self.ocr_config.min_text_len_per_page:
                text_status = TextStatus.OCR_REQUIRED
                ocr_status = OCRStatus.PENDING if self.ocr_config.enabled else OCRStatus.UNAVAILABLE
            else:
                text_status = TextStatus.TEXT_AVAILABLE
                ocr_status = OCRStatus.NOT_REQUIRED
        else:
            if text_length > 30:
                text_status = TextStatus.TEXT_AVAILABLE
                ocr_status = OCRStatus.NOT_REQUIRED
            else:
                text_status = TextStatus.EMPTY
                ocr_status = OCRStatus.NOT_REQUIRED

        return Document(
            path=path,
            filename=path.name,
            size_bytes=size_bytes,
            modified_at=mtime,
            page_count=page_count,
            title=title,
            author=author,
            pdf_metadata=pdf_metadata,
            text=extracted_text,
            text_length=text_length,
            text_status=text_status,
            sha256=sha256,
            ocr_status=ocr_status,
            error=combined_error,
        )

    def _extract_raw_text(self, path: Path) -> tuple[str, Optional[str]]:
        """Extract text content using PyMuPDF (fitz) or fallback stream scanner."""
        # 1. PyMuPDF
        try:
            import fitz  # type: ignore
            try:
                doc = fitz.open(str(path))
                text_parts = []
                for page in doc:
                    txt = page.get_text()
                    if txt:
                        text_parts.append(txt)
                doc.close()
                return "\n".join(text_parts).strip(), None
            except Exception as e:
                return "", f"PyMuPDF extraction failed: {str(e)}"
        except ImportError:
            pass

        # 2. Resilient fallback for pure python: extract compressed streams (FlateDecode)
        try:
            with open(path, "rb") as f:
                content = f.read()

            extracted_chunks = []
            # Extract plain BT ... ET text blocks
            bt_matches = re.findall(rb"BT[\s\S]*?ET", content)
            for block in bt_matches:
                # Find (text) Tj or [(t)(e)(x)(t)] TJ
                tj_matches = re.findall(rb"\((.*?)\)\s*Tj", block)
                for tm in tj_matches:
                    try:
                        extracted_chunks.append(tm.decode("latin-1", errors="ignore"))
                    except Exception:
                        pass

            # Search compressed stream blocks
            stream_matches = re.finditer(rb"stream[\r\n]+([\s\S]*?)[\r\n]+endstream", content)
            for m in stream_matches:
                stream_data = m.group(1)
                try:
                    decompressed = zlib.decompress(stream_data)
                    # Search text inside decompressed stream
                    decomp_bt = re.findall(rb"BT[\s\S]*?ET", decompressed)
                    for block in decomp_bt:
                        tj_matches = re.findall(rb"\((.*?)\)\s*Tj", block)
                        for tm in tj_matches:
                            try:
                                extracted_chunks.append(tm.decode("latin-1", errors="ignore"))
                            except Exception:
                                pass
                except Exception:
                    continue

            result_text = " ".join(extracted_chunks).strip()
            return result_text, None
        except Exception as e:
            return "", f"Stream extraction failed: {str(e)}"
