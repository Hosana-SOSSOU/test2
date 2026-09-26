"""Unit tests for RollbackManager."""

import tempfile
import unittest
from pathlib import Path
from src.pdf_organizer.config import SafetyConfig
from src.pdf_organizer.hashing import compute_file_sha256
from src.pdf_organizer.models import MovePlan
from src.pdf_organizer.mover import FileMover
from src.pdf_organizer.undo import RollbackManager


class TestUndo(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.journal_path = self.base_path / "operations.json"
        self.mover = FileMover(
            safety_config=SafetyConfig(),
            operations_log_path=self.journal_path,
        )
        self.manager = RollbackManager(log_path=self.journal_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normal_rollback(self):
        src = self.base_path / "original.pdf"
        src.write_bytes(b"%PDF-1.4 rollback test bytes")
        sha = compute_file_sha256(src)

        dest = self.base_path / "organized" / "original.pdf"

        # 1. Execute move
        plan = MovePlan(source=src, destination=dest, category="Cat", score=0.9, reason="Test", sha256=sha, status="PROPOSED")
        self.mover.execute_plan([plan])

        self.assertFalse(src.exists())
        self.assertTrue(dest.exists())

        # 2. Undo move
        undo_logs = self.manager.undo_all()
        self.assertEqual(len(undo_logs), 1)
        self.assertEqual(undo_logs[0].status, "SUCCESS")

        # 3. Verify file is back to original
        self.assertTrue(src.exists())
        self.assertFalse(dest.exists())
        self.assertEqual(compute_file_sha256(src), sha)

    def test_rollback_aborted_if_file_tampered_at_destination(self):
        src = self.base_path / "tamper_test.pdf"
        src.write_bytes(b"%PDF-1.4 initial content")
        sha = compute_file_sha256(src)
        dest = self.base_path / "organized" / "tamper_test.pdf"

        plan = MovePlan(source=src, destination=dest, category="Cat", score=0.9, reason="Test", sha256=sha, status="PROPOSED")
        self.mover.execute_plan([plan])

        # Tamper with file at destination
        dest.write_bytes(b"%PDF-1.4 unexpected changed bytes by another tool")

        # Rollback should refuse because hash does not match recorded sha
        undo_logs = self.manager.undo_all()
        self.assertEqual(len(undo_logs), 1)
        self.assertEqual(undo_logs[0].status, "FAILED")
        self.assertFalse(src.exists(), "Original source must not be overwritten or recreated on corrupted hash!")
        self.assertTrue(dest.exists(), "Destination file must be preserved.")


if __name__ == "__main__":
    unittest.main()
