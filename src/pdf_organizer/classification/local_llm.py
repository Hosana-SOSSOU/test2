"""
Local LLM-based document classifier.
Interacts with local inference runtimes (Ollama, llama.cpp) via the LocalLLM protocol.
Validates output strictly and falls back gracefully to rule-based classification.
"""

from __future__ import annotations

import json
import re
from typing import Optional
from ..llm.base import LLMError, LocalLLM
from ..models import Classification, Document, TextStatus
from ..taxonomy import Taxonomy
from .base import Classifier
from .rule_based import RuleBasedClassifier


class LocalLLMClassifier(Classifier):
    """
    Classifies documents using an offline, locally-hosted LLM.
    Strictly verifies JSON schema, taxonomy categories, and score ranges.
    """

    def __init__(
        self,
        llm: LocalLLM,
        taxonomy: Taxonomy,
        fallback_classifier: Optional[RuleBasedClassifier] = None,
        manual_review_threshold: float = 0.50,
        unclassified_category: str = "À_classer",
    ) -> None:
        self.llm = llm
        self.taxonomy = taxonomy
        self.fallback = fallback_classifier or RuleBasedClassifier(
            taxonomy=taxonomy,
            manual_review_threshold=manual_review_threshold,
            unclassified_category=unclassified_category,
        )
        self.manual_review_threshold = manual_review_threshold
        self.unclassified_category = unclassified_category

    @property
    def name(self) -> str:
        return "local_llm"

    def classify(self, document: Document) -> Classification:
        """Classify document via local LLM with robust fallback."""
        # 1. OCR check
        if document.text_status == TextStatus.OCR_REQUIRED and document.text_length < 20:
            return Classification(
                category=self.unclassified_category,
                score=0.0,
                evidence=[],
                reason="Document requires OCR: insufficient text for LLM inference.",
                classifier=self.name,
            )

        # 2. Build prompt
        categories = self.taxonomy.get_all_categories()
        prompt = self._build_prompt(document, categories)
        system_prompt = (
            "You are a local document classification assistant. "
            "Respond ONLY with a valid JSON object matching the requested schema. "
            "Do not add markdown formatting, preamble, or conversational commentary."
        )

        # 3. Call local LLM
        try:
            raw_response = self.llm.generate(prompt, system_prompt=system_prompt)
            classification = self._parse_and_validate(raw_response, document)
            return classification
        except (LLMError, Exception) as e:
            # Fallback to deterministic rule-based classifier
            fb_res = self.fallback.classify(document)
            return Classification(
                category=fb_res.category,
                score=fb_res.score,
                evidence=fb_res.evidence,
                reason=f"[LLM Fallback: {str(e)}] {fb_res.reason}",
                classifier=f"local_llm->fallback({fb_res.classifier})",
            )

    def _build_prompt(self, doc: Document, categories: list[str]) -> str:
        sample_text = (doc.text or "")[:1500].strip()
        category_list_str = "\n".join(f"- {c}" for c in categories)

        return (
            "Classify the following PDF document into exactly one of the allowed categories.\n\n"
            "ALLOWED CATEGORIES:\n"
            f"{category_list_str}\n\n"
            "DOCUMENT METADATA:\n"
            f"Filename: {doc.filename}\n"
            f"Title: {doc.title or 'Unknown'}\n"
            f"Author: {doc.author or 'Unknown'}\n\n"
            "TEXT EXCERPT:\n"
            f"{sample_text if sample_text else '[No text available]'}\n\n"
            "REQUIRED OUTPUT JSON SCHEMA:\n"
            "{\n"
            '  "category": "<Exact match from allowed categories>",\n'
            '  "score": <float between 0.0 and 1.0>,\n'
            '  "evidence": ["<keyword or clue 1>", "<keyword or clue 2>"],\n'
            '  "reason": "<One sentence explaining the choice>"\n'
            "}"
        )

    def _parse_and_validate(self, response: str, doc: Document) -> Classification:
        """Parse JSON from model output and validate all fields."""
        # Find JSON block inside potential backticks
        match = re.search(r"\{[\s\S]*\}", response)
        if not match:
            raise ValueError("No JSON object detected in model response")

        json_str = match.group(0)
        data = json.loads(json_str)

        category = str(data.get("category", "")).strip()
        score = float(data.get("score", 0.0))
        evidence = [str(x) for x in data.get("evidence", [])]
        reason = str(data.get("reason", "Classified by local LLM"))

        # Check category validity
        if not self.taxonomy.is_valid_category(category):
            raise ValueError(f"Model returned invalid category '{category}' not present in taxonomy")

        # Clamp score safely
        score = max(0.0, min(1.0, score))

        # Check threshold
        if score < self.manual_review_threshold:
            return Classification(
                category=self.unclassified_category,
                score=score,
                evidence=evidence,
                reason=f"LLM score ({score:.2f}) below threshold for '{category}'. Routed to {self.unclassified_category}.",
                classifier=self.name,
            )

        return Classification(
            category=category,
            score=score,
            evidence=evidence,
            reason=reason,
            classifier=self.name,
        )
