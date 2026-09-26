"""Unit tests for PDFScanner."""

import tempfile
import unittest
from pathlib import Path
from src.pdf_organizer.config import ScannerConfig
from src.pdf_organizer.scanner import PDFScanner


class TestPDFScanner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_recursive_discovery_and_extensions(self):
        # Create directory hierarchy
        sub1 = self.base_path / "subdir1"
        sub2 = self.base_path / "subdir1" / "nested"
        sub1.mkdir(parents=True)
        sub2.mkdir(parents=True)

        # Create pdf, PDF, and non-pdf files
        (self.base_path / "root.pdf").write_bytes(b"%PDF-1.4 dummy content " * 10)
        (sub1 / "uppercase.PDF").write_bytes(b"%PDF-1.5 UPPERCASE CONTENT " * 10)
        (sub2 / "nested.pdf").write_bytes(b"%PDF-1.4 NESTED CONTENT " * 10)
        (self.base_path / "notes.txt").write_text("not a pdf")
        (sub1 / "image.png").write_bytes(b"\x89PNG dummy")

        scanner = PDFScanner(ScannerConfig(min_file_size_bytes=10))
        found = scanner.scan_path(self.base_path)

        found_names = [p.name for p in found]
        self.assertIn("root.pdf", found_names)
        self.assertIn("uppercase.PDF", found_names)
        self.assertIn("nested.pdf", found_names)
        self.assertNotIn("notes.txt", found_names)
        self.assertNotIn("image.png", found_names)
        self.assertEqual(len(found), 3)

    def test_missing_directory(self):
        scanner = PDFScanner()
        missing_path = self.base_path / "does_not_exist"
        found = scanner.scan_path(missing_path)
        self.assertEqual(found, [])

    def test_symlink_handling(self):
        real_pdf = self.base_path / "real.pdf"
        real_pdf.write_bytes(b"%PDF-1.4 content " * 15)

        link_pdf = self.base_path / "link.pdf"
        try:
            link_pdf.symlink_to(real_pdf)
        except OSError:
            # Skip symlink test if filesystem doesn't permit
            return

        # Config: follow_symlinks = False
        scanner_no_sym = PDFScanner(ScannerConfig(follow_symlinks=False, min_file_size_bytes=10))
        res_no = scanner_no_sym.scan_path(self.base_path)
        self.assertEqual(len(res_no), 1)
        self.assertEqual(res_no[0].name, "real.pdf")

        # Config: follow_symlinks = True
        scanner_sym = PDFScanner(ScannerConfig(follow_symlinks=True, min_file_size_bytes=10))
        res_sym = scanner_sym.scan_path(self.base_path)
        self.assertEqual(len(res_sym), 2)


if __name__ == "__main__":
    unittest.main()
