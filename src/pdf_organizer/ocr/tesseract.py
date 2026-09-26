"""
Local Tesseract OCR backend implementation.
Executes purely locally without remote calls.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from .base import OCRBackend, OCRResult


class TesseractOCRBackend:
    """Local OCR engine invoking Tesseract binary."""

    def __init__(
        self,
        tesseract_cmd: str = "tesseract",
        lang: str = "fra+eng",
    ) -> None:
        self.tesseract_cmd = tesseract_cmd
        self.lang = lang
        self._cached_version: Optional[str] = None

    @property
    def engine_name(self) -> str:
        return "tesseract"

    @property
    def engine_version(self) -> str:
        if self._cached_version is not None:
            return self._cached_version

        if not self.is_available():
            self._cached_version = "unavailable"
            return self._cached_version

        try:
            res = subprocess.run(
                [self.tesseract_cmd, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
            )
            first_line = (res.stdout or res.stderr).splitlines()[0]
            self._cached_version = first_line.strip()
        except Exception:
            self._cached_version = "unknown"
        return self._cached_version

    def is_available(self) -> bool:
        """Check if tesseract binary exists in PATH."""
        return shutil.which(self.tesseract_cmd) is not None

    def extract_text(self, pdf_path: Path) -> OCRResult:
        """Run local Tesseract on the given PDF."""
        pdf_path = Path(pdf_path).resolve()
        if not pdf_path.exists():
            return OCRResult(
                text="",
                confidence=0.0,
                engine=self.engine_name,
                version=self.engine_version,
                success=False,
                error=f"File not found: {pdf_path}",
            )

        if not self.is_available():
            return OCRResult(
                text="",
                confidence=0.0,
                engine=self.engine_name,
                version="unavailable",
                success=False,
                error="Tesseract binary not installed or not in PATH (sudo apt install tesseract-ocr)",
            )

        # PyMuPDF rendering + tesseract
        try:
            import fitz  # type: ignore

            doc = fitz.open(str(pdf_path))
            all_text_parts = []
            page_confidences = []

            with tempfile.TemporaryDirectory(prefix="pdf_ocr_") as tmpdir:
                for idx, page in enumerate(doc):
                    # Render page at 300 DPI for good OCR quality
                    pix = page.get_pixmap(dpi=200)
                    img_path = Path(tmpdir) / f"page_{idx}.png"
                    pix.save(str(img_path))

                    # Invoke tesseract stdout
                    cmd = [
                        self.tesseract_cmd,
                        str(img_path),
                        "stdout",
                        "-l",
                        self.lang,
                    ]
                    proc = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                        timeout=60,
                    )
                    if proc.returncode == 0:
                        text_page = proc.stdout.strip()
                        if text_page:
                            all_text_parts.append(text_page)
                            page_confidences.append(0.85)
                    else:
                        return OCRResult(
                            text="",
                            confidence=0.0,
                            engine=self.engine_name,
                            version=self.engine_version,
                            success=False,
                            error=f"Tesseract page {idx} failed: {proc.stderr}",
                        )
            doc.close()

            combined_text = "\n\n".join(all_text_parts).strip()
            avg_conf = (
                sum(page_confidences) / len(page_confidences)
                if page_confidences
                else 0.0
            )

            return OCRResult(
                text=combined_text,
                confidence=avg_conf,
                engine=self.engine_name,
                version=self.engine_version,
                success=True,
                error=None,
            )
        except ImportError:
            # PyMuPDF not available: try direct tesseract on pdf (tesseract 3.03+ supports pdf input directly)
            try:
                with tempfile.TemporaryDirectory(prefix="pdf_ocr_direct_") as tmpdir:
                    out_base = Path(tmpdir) / "output"
                    cmd = [
                        self.tesseract_cmd,
                        str(pdf_path),
                        str(out_base),
                        "-l",
                        self.lang,
                    ]
                    proc = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                        timeout=120,
                    )
                    txt_file = out_base.with_suffix(".txt")
                    if txt_file.exists():
                        text_content = txt_file.read_text(encoding="utf-8").strip()
                        return OCRResult(
                            text=text_content,
                            confidence=0.80 if text_content else 0.0,
                            engine=self.engine_name,
                            version=self.engine_version,
                            success=True,
                            error=None,
                        )
                    return OCRResult(
                        text="",
                        confidence=0.0,
                        engine=self.engine_name,
                        version=self.engine_version,
                        success=False,
                        error=f"Tesseract failed: {proc.stderr}",
                    )
            except Exception as e:
                return OCRResult(
                    text="",
                    confidence=0.0,
                    engine=self.engine_name,
                    version=self.engine_version,
                    success=False,
                    error=f"OCR execution error: {str(e)}",
                )
        except Exception as e:
            return OCRResult(
                text="",
                confidence=0.0,
                engine=self.engine_name,
                version=self.engine_version,
                success=False,
                error=f"OCR execution error: {str(e)}",
            )
