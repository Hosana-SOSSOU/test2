"""
Deterministic rule-based document classifier.
Matches hierarchical taxonomy keywords against document title, metadata, and extracted text.
Calculates an explainable heuristic confidence score.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from ..models import Classification, Document, TextStatus
from ..taxonomy import Taxonomy
from .base import Classifier


class RuleBasedClassifier(Classifier):
    """
    Classifies documents using keyword frequency and positional weighting
    derived from the dynamic taxonomy definition.
    """

    def __init__(
        self,
        taxonomy: Taxonomy,
        manual_review_threshold: float = 0.50,
        unclassified_category: str = "À_classer",
    ) -> None:
        self.taxonomy = taxonomy
        self.manual_review_threshold = manual_review_threshold
        self.unclassified_category = unclassified_category

    @property
    def name(self) -> str:
        return "rule_based"

    def classify(self, document: Document) -> Classification:
        """Classify a document based on extracted text and metadata."""
        # 1. Check OCR status / text availability
        if document.text_status == TextStatus.OCR_REQUIRED and document.text_length < 20:
            return Classification(
                category=self.unclassified_category,
                score=0.0,
                evidence=[],
                reason="Document requires local OCR processing before text classification.",
                classifier=self.name,
            )

        if document.text_status in (TextStatus.EMPTY, TextStatus.ERROR) and not document.title:
            return Classification(
                category=self.unclassified_category,
                score=0.0,
                evidence=[],
                reason="Empty or unreadable document without title metadata.",
                classifier=self.name,
            )

        # 2. Prepare text streams
        title_norm = (document.title or "").lower()
        filename_norm = document.filename.lower()
        text_norm = (document.text or "").lower()

        # 3. Evaluate each category in taxonomy
        category_scores: Dict[str, Tuple[float, List[str]]] = {}

        for category in self.taxonomy.get_all_categories():
            if category == self.unclassified_category:
                continue

            keywords = self.taxonomy.get_keywords_for_category(category)
            if not keywords:
                # Infer keywords from leaf name if empty
                leaf_name = category.split("/")[-1].replace("-", " ").lower()
                keywords = [leaf_name]

            score, matched_keywords = self._evaluate_category(
                keywords=keywords,
                title=title_norm,
                filename=filename_norm,
                text=text_norm,
            )

            if score > 0:
                category_scores[category] = (score, matched_keywords)

        # 4. Determine best category
        if not category_scores:
            return Classification(
                category=self.unclassified_category,
                score=0.10,
                evidence=[],
                reason="No matching taxonomy keywords identified in document.",
                classifier=self.name,
            )

        best_category = max(category_scores.keys(), key=lambda c: category_scores[c][0])
        best_score, best_evidence = category_scores[best_category]

        # 5. Check ambiguity with runner-up
        sorted_cats = sorted(category_scores.items(), key=lambda x: x[1][0], reverse=True)
        if len(sorted_cats) > 1:
            second_cat, (second_score, second_evidence) = sorted_cats[1]
            if (best_score - second_score) < 0.08 and best_score < 0.70:
                # Ambiguous classification
                return Classification(
                    category=self.unclassified_category,
                    score=round(best_score * 0.75, 4),
                    evidence=best_evidence + [f"ambiguous_with:{second_cat}"],
                    reason=f"Ambiguous match between '{best_category}' ({best_score:.2f}) and '{second_cat}' ({second_score:.2f}).",
                    classifier=self.name,
                )

        # 6. Apply manual review threshold
        if best_score < self.manual_review_threshold:
            return Classification(
                category=self.unclassified_category,
                score=round(best_score, 4),
                evidence=best_evidence,
                reason=f"Weak match for '{best_category}' below threshold ({best_score:.2f} < {self.manual_review_threshold:.2f}). Routed to {self.unclassified_category}.",
                classifier=self.name,
            )

        # 7. High confidence match
        reason_desc = (
            f"Strong match for '{best_category}' with {len(best_evidence)} distinctive keywords "
            f"found across metadata and content."
        )

        return Classification(
            category=best_category,
            score=round(min(best_score, 0.98), 4),
            evidence=best_evidence,
            reason=reason_desc,
            classifier=self.name,
        )

    def _evaluate_category(
        self,
        keywords: List[str],
        title: str,
        filename: str,
        text: str,
    ) -> Tuple[float, List[str]]:
        """
        Calculates heuristic score:
        - Title match: 0.40
        - Filename match: 0.35
        - Text match: 0.25 for first, 0.15 for additional
        - Multiple keyword diversity bonus
        """
        matched: List[str] = []
        raw_score = 0.0

        for kw in keywords:
            pattern = r"(?:\b|_)" + re.escape(kw) + r"(?:\b|_)"

            in_title = bool(re.search(pattern, title))
            in_filename = bool(re.search(pattern, filename))
            in_text = bool(re.search(pattern, text[:25000]))

            if in_title or in_filename or in_text:
                matched.append(kw)

                if in_title:
                    raw_score += 0.45
                if in_filename:
                    raw_score += 0.35
                if in_text:
                    raw_score += 0.30 if len(matched) == 1 else 0.20

        if matched:
            # Multi-evidence diversity scaling
            diversity_multiplier = 1.0 + min(0.40, (len(matched) - 1) * 0.15)
            composite = raw_score * diversity_multiplier
            # Bound and scale smoothly between 0.30 and 0.98
            scaled_score = min(0.98, max(0.20, composite))
            return round(scaled_score, 4), matched

        return 0.0, []
