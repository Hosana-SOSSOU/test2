"""
Simulation engine for PDF Organizer.
Performs thorough dry-run validation without modifying the filesystem.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from .hashing import compute_file_sha256
from .models import MovePlan


@dataclass(slots=True)
class SimulationItem:
    """Detailed dry-run inspection for a planned relocation."""
    plan: MovePlan
    would_execute: bool
    status: str  # "WOULD_MOVE", "COLLISION", "SOURCE_MISSING", "HASH_MISMATCH", "PERMISSION_DENIED", "SAME_LOCATION", "OUTSIDE_BASE_DIR"
    is_cross_filesystem: bool
    notes: List[str] = field(default_factory=list)


@dataclass(slots=True)
class SimulationResult:
    """Summary of a full plan simulation."""
    total_plans: int
    would_move: int
    collisions: int
    manual_reviews: int
    same_location: int
    errors: int
    items: List[SimulationItem]

    def format_report(self) -> str:
        """Format an explanatory human-readable report."""
        lines = [
            "===========================================================",
            "                 SIMULATION REPORT (DRY RUN)               ",
            "===========================================================",
            f"Total evaluated files:   {self.total_plans}",
            f"Ready to move:           {self.would_move}",
            f"Potential collisions:    {self.collisions}",
            f"Requires manual review:  {self.manual_reviews}",
            f"Already in position:     {self.same_location}",
            f"Permission / I/O errors: {self.errors}",
            "-----------------------------------------------------------",
            "Details:",
        ]

        for idx, item in enumerate(self.items, 1):
            lines.append(f"\n{idx}. [{item.status}] {item.plan.source.name}")
            lines.append(f"   FROM:     {item.plan.source}")
            lines.append(f"   TO:       {item.plan.destination}")
            lines.append(f"   CATEGORY: {item.plan.category} (Score: {item.plan.score:.2f})")
            if item.is_cross_filesystem:
                lines.append("   FILESYSTEM: Cross-filesystem move (copy + verify hash + unlink)")
            if item.notes:
                for note in item.notes:
                    lines.append(f"   NOTE:     {note}")

        lines.append("\n===========================================================")
        lines.append("STATUS: SAFE. No filesystem modifications were performed.")
        lines.append("===========================================================")
        return "\n".join(lines)


class Simulator:
    """Simulates filesystem move operations safely."""

    def __init__(self, allowed_base_dir: Optional[Path | str] = None) -> None:
        self.allowed_base_dir = (
            Path(allowed_base_dir).expanduser().resolve()
            if allowed_base_dir
            else None
        )

    def simulate(self, plans: List[MovePlan]) -> SimulationResult:
        """Execute comprehensive dry-run checks on a list of MovePlans."""
        items: List[SimulationItem] = []
        would_move_count = 0
        collision_count = 0
        review_count = 0
        same_loc_count = 0
        error_count = 0

        for plan in plans:
            source = plan.source.resolve()
            dest = plan.destination.resolve()
            notes: List[str] = []
            would_execute = False
            status = plan.status

            # Check 1: Base directory jail
            if self.allowed_base_dir is not None:
                try:
                    dest.relative_to(self.allowed_base_dir)
                except ValueError:
                    status = "OUTSIDE_BASE_DIR"
                    notes.append(f"Security: Destination outside allowed base dir {self.allowed_base_dir}")
                    error_count += 1
                    items.append(SimulationItem(plan=plan, would_execute=False, status=status, is_cross_filesystem=False, notes=notes))
                    continue

            # Check 2: Source existence and accessibility
            if not source.exists():
                status = "SOURCE_MISSING"
                notes.append("Source file no longer exists.")
                error_count += 1
                items.append(SimulationItem(plan=plan, would_execute=False, status=status, is_cross_filesystem=False, notes=notes))
                continue

            if not source.is_file():
                status = "SOURCE_NOT_FILE"
                notes.append("Source is not a regular file.")
                error_count += 1
                items.append(SimulationItem(plan=plan, would_execute=False, status=status, is_cross_filesystem=False, notes=notes))
                continue

            if not os.access(source, os.R_OK):
                status = "PERMISSION_DENIED"
                notes.append("Source file is not readable.")
                error_count += 1
                items.append(SimulationItem(plan=plan, would_execute=False, status=status, is_cross_filesystem=False, notes=notes))
                continue

            # Check 3: Integrity check against planned hash
            if plan.sha256:
                try:
                    current_hash = compute_file_sha256(source)
                    if current_hash != plan.sha256:
                        status = "HASH_MISMATCH"
                        notes.append(f"Source file was modified since plan creation (SHA changed: {current_hash[:8]} vs {plan.sha256[:8]}).")
                        error_count += 1
                        items.append(SimulationItem(plan=plan, would_execute=False, status=status, is_cross_filesystem=False, notes=notes))
                        continue
                except OSError as e:
                    status = "HASH_ERROR"
                    notes.append(f"Could not verify source hash: {e}")
                    error_count += 1
                    items.append(SimulationItem(plan=plan, would_execute=False, status=status, is_cross_filesystem=False, notes=notes))
                    continue

            # Check 4: Destination collision
            if source == dest:
                status = "SAME_LOCATION"
                notes.append("Source and destination paths are identical.")
                same_loc_count += 1
                items.append(SimulationItem(plan=plan, would_execute=False, status=status, is_cross_filesystem=False, notes=notes))
                continue

            if dest.exists():
                status = "COLLISION"
                collision_count += 1
                notes.append("A file already exists at the destination path.")
                items.append(SimulationItem(plan=plan, would_execute=False, status=status, is_cross_filesystem=False, notes=notes))
                continue

            # Check 5: Destination parent writability
            dest_parent = dest.parent
            parent_to_check = dest_parent
            while not parent_to_check.exists() and parent_to_check != parent_to_check.parent:
                parent_to_check = parent_to_check.parent

            if not os.access(parent_to_check, os.W_OK):
                status = "PERMISSION_DENIED"
                notes.append(f"Cannot write to directory tree: {parent_to_check}")
                error_count += 1
                items.append(SimulationItem(plan=plan, would_execute=False, status=status, is_cross_filesystem=False, notes=notes))
                continue

            # Check 6: Cross filesystem determination
            is_cross_fs = False
            try:
                source_dev = source.stat().st_dev
                target_dev = parent_to_check.stat().st_dev
                is_cross_fs = (source_dev != target_dev)
            except OSError:
                pass

            # Check 7: Manual review status
            if plan.status in ("NEEDS_REVIEW", "BATCH_COLLISION") or plan.category == "À_classer":
                status = plan.status
                review_count += 1
                notes.append(f"Requires human confirmation ({plan.reason})")
            else:
                status = "WOULD_MOVE"
                would_execute = True
                would_move_count += 1

            items.append(
                SimulationItem(
                    plan=plan,
                    would_execute=would_execute,
                    status=status,
                    is_cross_filesystem=is_cross_fs,
                    notes=notes,
                )
            )

        return SimulationResult(
            total_plans=len(plans),
            would_move=would_move_count,
            collisions=collision_count,
            manual_reviews=review_count,
            same_location=same_loc_count,
            errors=error_count,
            items=items,
        )
