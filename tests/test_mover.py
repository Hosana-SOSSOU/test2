"""Unit tests for FileMover execution engine."""

import json
import tempfile
import unittest
from pathlib import Path
from src.pdf_organizer.config import SafetyConfig
from src.pdf_organizer.hashing import compute_file_sha256
from src.pdf_organizer.models import MovePlan
from src.pdf_organizer.mover import FileMover


class TestMover(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.journal_path = self.base_path / "operations.json"
        self.mover = FileMover(
            safety_config=SafetyConfig(collision_strategy="RENAME"),
            operations_log_path=self.journal_path,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normal_move(self):
        src = self.base_path / "doc.pdf"
        src.write_bytes(b"%PDF-1.4 test document content")
        sha = compute_file_sha256(src)

        dest = self.base_path / "dest_folder" / "doc.pdf"

        plan = MovePlan(
            source=src,
            destination=dest,
            category="Test",
            score=0.9,
            reason="Good",
            sha256=sha,
            status="PROPOSED",
        )

        logs = self.mover.execute_plan([plan])
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].status, "SUCCESS")

        self.assertFalse(src.exists())
        self.assertTrue(dest.exists())
        self.assertEqual(compute_file_sha256(dest), sha)

        # Verify journal
        self.assertTrue(self.journal_path.exists())
        with open(self.journal_path, "r", encoding="utf-8") as f:
            journal_data = json.load(f)
        self.assertEqual(len(journal_data), 1)
        self.assertEqual(journal_data[0]["status"], "SUCCESS")

    def test_never_overwrite_and_rename_strategy(self):
        # Target exists
        dest_folder = self.base_path / "target"
        dest_folder.mkdir()
        existing = dest_folder / "file.pdf"
        existing.write_bytes(b"%PDF-1.4 existing file that MUST NEVER BE OVERWRITTEN")
        existing_sha = compute_file_sha256(existing)

        # Incoming file with same name but different content
        src = self.base_path / "file.pdf"
        src.write_bytes(b"%PDF-1.4 new incoming file content")
        src_sha = compute_file_sha256(src)

        plan = MovePlan(
            source=src,
            destination=existing,
            category="Target",
            score=0.85,
            reason="Match",
            sha256=src_sha,
            status="PROPOSED",
        )

        logs = self.mover.execute_plan([plan])
        self.assertEqual(logs[0].status, "SUCCESS")

        # STRICT VERIFICATION: existing file unchanged
        self.assertTrue(existing.exists())
        self.assertEqual(compute_file_sha256(existing), existing_sha)

        # Incoming file renamed to file_1.pdf
        renamed = dest_folder / "file_1.pdf"
        self.assertTrue(renamed.exists())
        self.assertEqual(compute_file_sha256(renamed), src_sha)

    def test_hash_mismatch_aborts_move(self):
        src = self.base_path / "tampered.pdf"
        src.write_bytes(b"%PDF-1.4 modified after planning")

        dest = self.base_path / "target" / "tampered.pdf"

        plan = MovePlan(
            source=src,
            destination=dest,
            category="Target",
            score=0.9,
            reason="Match",
            sha256="expected_different_sha_from_earlier",
            status="PROPOSED",
        )

        logs = self.mover.execute_plan([plan])
        self.assertEqual(logs[0].status, "FAILED")
        self.assertTrue(src.exists())
        self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
