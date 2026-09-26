"""Unit tests for MovePlanner."""

from datetime import datetime
import tempfile
import unittest
from pathlib import Path
from src.pdf_organizer.hashing import compute_file_sha256
from src.pdf_organizer.models import Classification, Document, TextStatus
from src.pdf_organizer.planner import MovePlanner


class TestPlanner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.target_dir = self.base_path / "Organized"
        self.planner = MovePlanner(target_base_dir=self.target_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_correct_destination(self):
        src = self.base_path / "deep_learning.pdf"
        src.write_bytes(b"%PDF-1.4 dummy deep learning")
        doc = Document(
            path=src,
            filename=src.name,
            size_bytes=len(src.read_bytes()),
            modified_at=datetime.now(),
            sha256=compute_file_sha256(src),
            text_status=TextStatus.TEXT_AVAILABLE,
        )
        cls_info = Classification(
            category="Informatique/Intelligence-Artificielle",
            score=0.92,
            evidence=["deep learning"],
            reason="Clear match",
            classifier="rule_based",
        )

        plan = self.planner.plan_document(doc, cls_info)
        expected_dest = self.target_dir / "Informatique" / "Intelligence-Artificielle" / "deep_learning.pdf"
        self.assertEqual(plan.destination, expected_dest)
        self.assertEqual(plan.status, "PROPOSED")

    def test_same_location(self):
        # File is already at the target path
        cat_dir = self.target_dir / "Maths" / "Algèbre"
        cat_dir.mkdir(parents=True)
        already_there = cat_dir / "matrix.pdf"
        already_there.write_bytes(b"%PDF-1.4 matrix")

        doc = Document(
            path=already_there,
            filename=already_there.name,
            size_bytes=len(already_there.read_bytes()),
            modified_at=datetime.now(),
            sha256=compute_file_sha256(already_there),
            text_status=TextStatus.TEXT_AVAILABLE,
        )
        cls_info = Classification(category="Maths/Algèbre", score=0.88, evidence=[], reason="", classifier="rule")
        plan = self.planner.plan_document(doc, cls_info)
        self.assertEqual(plan.status, "SAME_LOCATION")

    def test_collision_detection(self):
        # Destination already has an existing file with different content
        cat_dir = self.target_dir / "Maths" / "Algèbre"
        cat_dir.mkdir(parents=True)
        existing_dest = cat_dir / "matrix.pdf"
        existing_dest.write_bytes(b"%PDF-1.4 existing file")

        src = self.base_path / "matrix.pdf"
        src.write_bytes(b"%PDF-1.4 completely different incoming file")

        doc = Document(
            path=src,
            filename=src.name,
            size_bytes=len(src.read_bytes()),
            modified_at=datetime.now(),
            sha256=compute_file_sha256(src),
            text_status=TextStatus.TEXT_AVAILABLE,
        )
        cls_info = Classification(category="Maths/Algèbre", score=0.88, evidence=[], reason="", classifier="rule")
        plan = self.planner.plan_document(doc, cls_info)
        self.assertEqual(plan.status, "COLLISION")


if __name__ == "__main__":
    unittest.main()
