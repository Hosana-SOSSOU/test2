"""Unit tests for duplicate detection engine."""

import tempfile
import unittest
from pathlib import Path
from src.pdf_organizer.duplicates import DuplicateDetector
from src.pdf_organizer.extractor import DocumentExtractor


class TestDuplicates(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.detector = DuplicateDetector()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_identical_files_and_different_filenames(self):
        content_a = b"%PDF-1.4 book A content with unique hash bytes 123456"
        content_b = b"%PDF-1.4 book B different content 7891011"

        # Group 1: 3 copies of content_a with different names & directories
        f1 = self.base_path / "book_original.pdf"
        f2 = self.base_path / "book_copy.pdf"
        sub = self.base_path / "sub"
        sub.mkdir()
        f3 = sub / "downloaded_book.pdf"

        f1.write_bytes(content_a)
        f2.write_bytes(content_a)
        f3.write_bytes(content_a)

        # Unique file B
        f4 = self.base_path / "different.pdf"
        f4.write_bytes(content_b)

        # Group 2: 2 copies of content_c
        content_c = b"%PDF-1.4 third unique group content 9999"
        f5 = self.base_path / "group2_a.pdf"
        f6 = self.base_path / "group2_b.pdf"
        f5.write_bytes(content_c)
        f6.write_bytes(content_c)

        extractor = DocumentExtractor()
        all_paths = [f1, f2, f3, f4, f5, f6]
        docs = [extractor.process(p) for p in all_paths]

        duplicate_groups = self.detector.find_duplicates_from_documents(docs)

        # Expect 2 groups
        self.assertEqual(len(duplicate_groups), 2)

        # Group 1 has 3 files
        group1 = next(g for g in duplicate_groups if len(g.files) == 3)
        self.assertEqual(group1.size_bytes, len(content_a))
        self.assertEqual(set(group1.files), {f1, f2, f3})

        # Group 2 has 2 files
        group2 = next(g for g in duplicate_groups if len(g.files) == 2)
        self.assertEqual(group2.size_bytes, len(content_c))
        self.assertEqual(set(group2.files), {f5, f6})

        # Verify no files were deleted
        for p in all_paths:
            self.assertTrue(p.exists())


if __name__ == "__main__":
    unittest.main()
