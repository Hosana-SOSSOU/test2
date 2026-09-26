"""Unit tests for DocumentExtractor and OCR detection."""

import tempfile
import unittest
from pathlib import Path
from src.pdf_organizer.config import OCRConfig
from src.pdf_organizer.extractor import DocumentExtractor
from src.pdf_organizer.models import OCRStatus, TextStatus


class TestExtractor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.extractor = DocumentExtractor(OCRConfig(min_text_len_per_page=30))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_textual_pdf(self):
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
            b"4 0 obj << /Title (Quantum Mechanics) >> endobj\n"
            b"stream\n"
            b"BT /F1 12 Tf (In quantum mechanics, eigenvalues and wavefunctions describe states.) Tj ET\n"
            b"endstream\n"
            b"xref\n0 5\ntrailer << /Root 1 0 R /Info 4 0 R >>\n%%EOF"
        )
        file_path = self.base_path / "quantum.pdf"
        file_path.write_bytes(pdf_bytes)

        doc = self.extractor.process(file_path)
        self.assertEqual(doc.text_status, TextStatus.TEXT_AVAILABLE)
        self.assertEqual(doc.ocr_status, OCRStatus.NOT_REQUIRED)
        self.assertGreater(doc.text_length, 20)
        self.assertIsNotNone(doc.sha256)

    def test_ocr_required_pdf(self):
        # A PDF with 2 pages declared, but zero text stream
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
            b"4 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
            b"xref\n0 5\ntrailer << /Root 1 0 R >>\n%%EOF"
        )
        file_path = self.base_path / "scanned_doc.pdf"
        file_path.write_bytes(pdf_bytes)

        doc = self.extractor.process(file_path)
        self.assertEqual(doc.text_status, TextStatus.OCR_REQUIRED)
        self.assertEqual(doc.ocr_status, OCRStatus.PENDING)
        self.assertEqual(doc.text_length, 0)

    def test_corrupted_pdf(self):
        file_path = self.base_path / "corrupted.pdf"
        file_path.write_bytes(b"garbage not a pdf file at all")

        doc = self.extractor.process(file_path)
        self.assertEqual(doc.text_status, TextStatus.ERROR)
        self.assertIsNotNone(doc.error)


if __name__ == "__main__":
    unittest.main()
