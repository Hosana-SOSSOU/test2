"""Unit tests for metadata extraction."""

import tempfile
import unittest
from pathlib import Path
from src.pdf_organizer.metadata import extract_pdf_metadata, get_filesystem_metadata


class TestMetadata(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_filesystem_metadata(self):
        sample = self.base_path / "sample.pdf"
        data = b"%PDF-1.4 hello world metadata test"
        sample.write_bytes(data)

        size, mtime = get_filesystem_metadata(sample)
        self.assertEqual(size, len(data))
        self.assertIsNotNone(mtime)

    def test_pdf_metadata_extraction(self):
        # Create a syntactically valid basic PDF snippet with title and author
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj\n"
            b"<< /Type /Catalog /Pages 2 0 R >>\n"
            b"endobj\n"
            b"2 0 obj\n"
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
            b"endobj\n"
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R >>\n"
            b"endobj\n"
            b"4 0 obj\n"
            b"<< /Title (Linear Algebra Foundations) /Author (Ada Lovelace) >>\n"
            b"endobj\n"
            b"xref\n"
            b"0 5\n"
            b"trailer\n"
            b"<< /Root 1 0 R /Info 4 0 R >>\n"
            b"%%EOF\n"
        )
        sample = self.base_path / "linear_algebra.pdf"
        sample.write_bytes(pdf_bytes)

        page_count, title, author, metadata_dict, error = extract_pdf_metadata(sample)
        self.assertIsNone(error)
        self.assertEqual(title, "Linear Algebra Foundations")
        self.assertEqual(author, "Ada Lovelace")
        self.assertIn("title", metadata_dict)


if __name__ == "__main__":
    unittest.main()
