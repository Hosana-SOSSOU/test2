"""
Base interface and contract for document classifiers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from ..models import Classification, Document


@runtime_checkable
class Classifier(Protocol):
    """Protocol for document classification engines."""

    @property
    def name(self) -> str:
        """Identifier for the classifier implementation."""
        ...

    def classify(self, document: Document) -> Classification:
        """Analyze a document and determine its category with confidence and evidence."""
        ...
