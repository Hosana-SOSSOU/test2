"""OCR subsystem for PDF Organizer."""

from .base import OCRBackend, OCRResult, OCRCache
from .tesseract import TesseractOCRBackend

__all__ = ["OCRBackend", "OCRResult", "OCRCache", "TesseractOCRBackend"]
