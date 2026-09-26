"""
Relocation planner for PDF Organizer.
Translates document classifications into concrete, verifiable MovePlan proposals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
from .config import SafetyConfig
from .hashing import compute_file_sha256
from .models import Classification, Document, MovePlan


class MovePlanner:
    """Computes destinations and generates execution plans."""

    def __init__(
        self,
        target_base_dir: Path | str,
        safety_config: Optional[SafetyConfig] = None,
    ) -> None:
        self.target_base_dir = Path(target_base_dir).expanduser().resolve()
        self.safety_config = safety_config or SafetyConfig()

    def plan_document(
        self,
        document: Document,
        classification: Classification,
    ) -> MovePlan:
        """Create a MovePlan for a single document."""
        # Clean category for directory path
        clean_category = classification.category.strip("/").strip()
        if not clean_category:
            clean_category = "À_classer"

        target_dir = self.target_base_dir / Path(clean_category)
        destination = target_dir / document.filename

        # Source normalization
        source_path = document.path.resolve()

        # Check identical path
        if source_path == destination.resolve():
            return MovePlan(
                source=source_path,
                destination=destination,
                category=classification.category,
                score=classification.score,
                reason="File is already in the proposed destination directory.",
                sha256=document.sha256,
                status="SAME_LOCATION",
            )

        # Check if destination exists
        status = "PROPOSED"
        reason = classification.reason

        if destination.exists():
            try:
                dest_hash = compute_file_sha256(destination)
                if document.sha256 and dest_hash == document.sha256:
                    status = "IDENTICAL_EXISTS"
                    reason = f"Identical file already exists at destination ({destination.name})."
                else:
                    status = "COLLISION"
                    reason = f"Collision: Different file with same name exists at {destination}."
            except OSError as e:
                status = "COLLISION"
                reason = f"Collision check failed on destination: {e}"

        elif classification.category == "À_classer" or classification.score < 0.50:
            status = "NEEDS_REVIEW"

        return MovePlan(
            source=source_path,
            destination=destination,
            category=classification.category,
            score=classification.score,
            reason=reason,
            sha256=document.sha256,
            status=status,
        )

    def plan_all(
        self,
        pairs: List[tuple[Document, Classification]],
    ) -> List[MovePlan]:
        """Generate a complete plan for all documents, accounting for destination conflicts."""
        plans: List[MovePlan] = []
        claimed_destinations: Dict[Path, Path] = {}  # dest_path -> source_path

        for doc, classification in pairs:
            plan = self.plan_document(doc, classification)

            # Check if another document in this same batch claims this destination
            if plan.destination in claimed_destinations and plan.status == "PROPOSED":
                plan.status = "BATCH_COLLISION"
                prev_source = claimed_destinations[plan.destination]
                plan.reason = f"Destination conflict with another file in this batch ({prev_source.name})."
            else:
                if plan.status == "PROPOSED":
                    claimed_destinations[plan.destination] = plan.source

            plans.append(plan)

        return plans
