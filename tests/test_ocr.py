"""Unit tests for OCR backend interface and caching."""

import tempfile
import unittest
from pathlib import Path
from src.pdf_organizer.ocr.base import OCRCache, OCRResult
from src.pdf_organizer.ocr.tesseract import TesseractOCRBackend


class MockOCRBackend:
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.calls = 0

    @property
    def engine_name(self) -> str:
        return "mock_ocr"

    @property
    def engine_version(self) -> str:
        return "1.0.0"

    def is_available(self) -> bool:
        return True

    def extract_text(self, pdf_path: Path) -> OCRResult:
        self.calls += 1
        if self.should_succeed:
            return OCRResult(
                text="Extracted text through OCR: neural network backpropagation",
                confidence=0.92,
                engine=self.engine_name,
                version=self.engine_version,
                success=True,
            )
        return OCRResult(
            text="",
            confidence=0.0,
            engine=self.engine_name,
            version=self.engine_version,
            success=False,
            error="OCR Engine failed to process pages",
        )


class TestOCR(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name) / "cache"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_backend_unavailable(self):
        # Fake command that does not exist in PATH
        backend = TesseractOCRBackend(tesseract_cmd="non_existent_binary_xyz_123")
        self.assertFalse(backend.is_available())
        dummy_path = Path(self.temp_dir.name) / "dummy.pdf"
        dummy_path.write_bytes(b"%PDF-1.4 dummy")
        result = backend.extract_text(dummy_path)
        self.assertFalse(result.success)
        self.assertIn("not installed", result.error or "")

    def test_ocr_success_and_failure(self):
        mock_success = MockOCRBackend(should_succeed=True)
        res_ok = mock_success.extract_text(Path("test.pdf"))
        self.assertTrue(res_ok.success)
        self.assertIn("neural network", res_ok.text)

        mock_fail = MockOCRBackend(should_succeed=False)
        res_fail = mock_fail.extract_text(Path("test.pdf"))
        self.assertFalse(res_fail.success)
        self.assertIsNotNone(res_fail.error)

    def test_ocr_cache(self):
        cache = OCRCache(self.cache_dir)
        doc_hash = "abcdef1234567890abcdef1234567890"

        # Initially no cache
        self.assertIsNone(cache.get(doc_hash, "mock_ocr", "1.0.0"))

        result = OCRResult(
            text="Cached OCR content",
            confidence=0.89,
            engine="mock_ocr",
            version="1.0.0",
            success=True,
        )
        cache.set(doc_hash, "mock_ocr", "1.0.0", result)

        # Retrieve
        cached = cache.get(doc_hash, "mock_ocr", "1.0.0")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.text, "Cached OCR content")
        self.assertEqual(cached.confidence, 0.89)


if __name__ == "__main__":
    unittest.main()
