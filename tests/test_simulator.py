"""Unit tests for Simulator dry-run engine."""

import tempfile
import unittest
from pathlib import Path
from src.pdf_organizer.hashing import compute_file_sha256
from src.pdf_organizer.models import MovePlan
from src.pdf_organizer.simulator import Simulator


class TestSimulator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.target_dir = self.base_path / "Organized"
        self.simulator = Simulator(allowed_base_dir=self.base_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_simulation_never_mutates_filesystem(self):
        src = self.base_path / "important_paper.pdf"
        src.write_bytes(b"%PDF-1.4 original source content")
        sha = compute_file_sha256(src)

        dest = self.target_dir / "Informatique" / "important_paper.pdf"

        plan = MovePlan(
            source=src,
            destination=dest,
            category="Informatique",
            score=0.95,
            reason="Clear match",
            sha256=sha,
            status="PROPOSED",
        )

        result = self.simulator.simulate([plan])

        # Assertions on simulation outcomes
        self.assertEqual(result.total_plans, 1)
        self.assertEqual(result.would_move, 1)
        self.assertEqual(result.collisions, 0)
        self.assertEqual(result.errors, 0)

        # STRICT VERIFICATION: Filesystem was not modified
        self.assertTrue(src.exists(), "Source file must remain intact during simulation!")
        self.assertFalse(dest.exists(), "Destination must NOT be created during simulation!")

    def test_missing_source_detected(self):
        missing_src = self.base_path / "ghost.pdf"
        dest = self.target_dir / "ghost.pdf"

        plan = MovePlan(
            source=missing_src,
            destination=dest,
            category="Livres",
            score=0.80,
            reason="Test",
            sha256="fakehash",
            status="PROPOSED",
        )

        result = self.simulator.simulate([plan])
        self.assertEqual(result.would_move, 0)
        self.assertEqual(result.errors, 1)
        self.assertEqual(result.items[0].status, "SOURCE_MISSING")


if __name__ == "__main__":
    unittest.main()
