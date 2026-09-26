"""Unit tests for RuleBasedClassifier and LocalLLMClassifier."""

from datetime import datetime
from pathlib import Path
import unittest

from src.pdf_organizer.classification.local_llm import LocalLLMClassifier
from src.pdf_organizer.classification.rule_based import RuleBasedClassifier
from src.pdf_organizer.llm.base import LLMUnavailableError
from src.pdf_organizer.models import Document, TextStatus
from src.pdf_organizer.taxonomy import Taxonomy


class MockFailingLLM:
    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        raise LLMUnavailableError("Local daemon unreachable on port 11434")


class MockMalformedLLM:
    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return "I think this document is great! Not a json."


class MockValidLLM:
    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return '{"category": "Physique", "score": 0.94, "evidence": ["entropy"], "reason": "Mentions heat engines."}'


class TestClassification(unittest.TestCase):
    def setUp(self):
        self.taxonomy = Taxonomy({
            "Maths": {
                "Algèbre": {
                    "keywords": ["matrix", "eigenvalue", "vector space", "linear algebra"],
                },
                "Analyse": {
                    "keywords": ["integral", "derivative", "calculus"],
                },
            },
            "Informatique": {
                "Intelligence-Artificielle": {
                    "keywords": ["neural network", "cnn", "backpropagation", "transformer"],
                },
            },
            "Physique": {
                "keywords": ["thermodynamics", "entropy", "heat engine"],
            },
            "À_classer": {},
        })
        self.classifier = RuleBasedClassifier(self.taxonomy, manual_review_threshold=0.50)

    def test_keywords_match_math(self):
        doc = Document(
            path=Path("/tmp/algebre.pdf"),
            filename="algebre.pdf",
            size_bytes=5000,
            modified_at=datetime.now(),
            title="Introduction to Linear Algebra",
            text="In this chapter we study matrix multiplication, vector space bases, and eigenvalue decomposition.",
            text_length=150,
            text_status=TextStatus.TEXT_AVAILABLE,
        )
        res = self.classifier.classify(doc)
        self.assertEqual(res.category, "Maths/Algèbre")
        self.assertGreaterEqual(res.score, 0.50)
        self.assertLessEqual(res.score, 1.0)
        self.assertIn("matrix", res.evidence)

    def test_keywords_match_ai(self):
        doc = Document(
            path=Path("/tmp/deep_learning.pdf"),
            filename="deep_learning.pdf",
            size_bytes=8000,
            modified_at=datetime.now(),
            title="Deep Learning Architectures",
            text="A convolutional neural network (CNN) trained with backpropagation optimizes weights using gradient descent.",
            text_length=150,
            text_status=TextStatus.TEXT_AVAILABLE,
        )
        res = self.classifier.classify(doc)
        self.assertEqual(res.category, "Informatique/Intelligence-Artificielle")
        self.assertGreater(res.score, 0.70)
        self.assertIn("neural network", res.evidence)

    def test_ambiguous_and_low_score_routes_to_a_classer(self):
        doc = Document(
            path=Path("/tmp/unclear.pdf"),
            filename="recipe_for_pie.pdf",
            size_bytes=1000,
            modified_at=datetime.now(),
            title="Grandma Apple Pie",
            text="Ingredients: apples, flour, sugar, cinnamon. Bake at 180 degrees.",
            text_length=100,
            text_status=TextStatus.TEXT_AVAILABLE,
        )
        res = self.classifier.classify(doc)
        self.assertEqual(res.category, "À_classer")
        self.assertLess(res.score, 0.50)

    def test_score_bounds_validation(self):
        # Directly test Classification dataclass enforcement
        from src.pdf_organizer.models import Classification
        c1 = Classification(category="Test", score=1.5, evidence=[], reason="test", classifier="c")
        self.assertEqual(c1.score, 1.0)
        c2 = Classification(category="Test", score=-0.2, evidence=[], reason="test", classifier="c")
        self.assertEqual(c2.score, 0.0)

    def test_llm_fallback_on_daemon_error(self):
        llm = MockFailingLLM()
        llm_classifier = LocalLLMClassifier(
            llm=llm,
            taxonomy=self.taxonomy,
            fallback_classifier=self.classifier,
        )
        doc = Document(
            path=Path("/tmp/ai_paper.pdf"),
            filename="ai_paper.pdf",
            size_bytes=5000,
            modified_at=datetime.now(),
            text="Training a neural network with backpropagation",
            text_length=100,
            text_status=TextStatus.TEXT_AVAILABLE,
        )
        res = llm_classifier.classify(doc)
        self.assertEqual(res.category, "Informatique/Intelligence-Artificielle")
        self.assertIn("fallback", res.classifier)

    def test_llm_valid_json_response(self):
        llm = MockValidLLM()
        llm_classifier = LocalLLMClassifier(
            llm=llm,
            taxonomy=self.taxonomy,
            fallback_classifier=self.classifier,
        )
        doc = Document(
            path=Path("/tmp/physics.pdf"),
            filename="physics.pdf",
            size_bytes=3000,
            modified_at=datetime.now(),
            text="Carnot cycle thermodynamics",
            text_length=80,
            text_status=TextStatus.TEXT_AVAILABLE,
        )
        res = llm_classifier.classify(doc)
        self.assertEqual(res.category, "Physique")
        self.assertEqual(res.score, 0.94)
        self.assertEqual(res.classifier, "local_llm")


if __name__ == "__main__":
    unittest.main()
