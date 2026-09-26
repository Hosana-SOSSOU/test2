"""
Filesystem execution engine for PDF Organizer.
Enforces the NEVER OVERWRITE policy, safe cross-filesystem moves, and operation logging.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from .config import SafetyConfig
from .hashing import compute_file_sha256
from .models import MovePlan, OperationLog


class FileMover:
    """Safely executes MovePlans with atomic or verified cross-fs copy-delete."""

    def __init__(
        self,
        safety_config: Optional[SafetyConfig] = None,
        operations_log_path: Path | str = "operations.json",
    ) -> None:
        self.safety_config = safety_config or SafetyConfig()
        self.operations_log_path = Path(operations_log_path)

    def execute_plan(
        self,
        plans: List[MovePlan],
        dry_run: bool = False,
    ) -> List[OperationLog]:
        """
        Execute relocation plans.
        Never overwrites existing files.
        Logs each operation for potential rollback.
        """
        if dry_run:
            raise ValueError("Use Simulator for dry_run mode.")

        logs: List[OperationLog] = []

        for plan in plans:
            source = plan.source.resolve()
            target = plan.destination.resolve()

            # Skip review or identical items
            if plan.status in ("SAME_LOCATION", "IDENTICAL_EXISTS"):
                continue

            # 1. Source existence check
            if not source.exists():
                logs.append(
                    OperationLog(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        operation="MOVE",
                        source=str(source),
                        destination=str(target),
                        sha256=plan.sha256,
                        status="FAILED",
                        details="Source file does not exist.",
                    )
                )
                continue

            # 2. Source hash verification (integrity protection)
            try:
                current_sha = compute_file_sha256(source)
                if plan.sha256 and current_sha != plan.sha256:
                    logs.append(
                        OperationLog(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            operation="MOVE",
                            source=str(source),
                            destination=str(target),
                            sha256=current_sha,
                            status="FAILED",
                            details="Source file was modified after planning (hash mismatch).",
                        )
                    )
                    continue
            except OSError as e:
                logs.append(
                    OperationLog(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        operation="MOVE",
                        source=str(source),
                        destination=str(target),
                        sha256=plan.sha256,
                        status="FAILED",
                        details=f"Hash computation error: {e}",
                    )
                )
                continue

            # 3. Collision handling (NEVER OVERWRITE)
            actual_destination = target
            if actual_destination.exists():
                strategy = self.safety_config.collision_strategy.upper()
                if strategy == "SKIP":
                    logs.append(
                        OperationLog(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            operation="MOVE",
                            source=str(source),
                            destination=str(actual_destination),
                            sha256=current_sha,
                            status="SKIPPED",
                            details="Destination exists and collision strategy is SKIP.",
                        )
                    )
                    continue
                elif strategy == "RENAME":
                    actual_destination = self._find_non_colliding_path(actual_destination)
                else:  # REVIEW or unknown
                    logs.append(
                        OperationLog(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            operation="MOVE",
                            source=str(source),
                            destination=str(actual_destination),
                            sha256=current_sha,
                            status="FAILED",
                            details="Destination collision detected. Action aborted under REVIEW strategy.",
                        )
                    )
                    continue

            # 4. Perform move (same-device or cross-filesystem)
            success, error_msg = self._move_file_safely(source, actual_destination, current_sha)

            log_entry = OperationLog(
                timestamp=datetime.now(timezone.utc).isoformat(),
                operation="MOVE",
                source=str(source),
                destination=str(actual_destination),
                sha256=current_sha,
                status="SUCCESS" if success else "FAILED",
                details=error_msg,
            )
            logs.append(log_entry)
            self._append_to_journal(log_entry)

        return logs

    def _find_non_colliding_path(self, target: Path) -> Path:
        """Generate filename_1.pdf, filename_2.pdf if target already exists."""
        stem = target.stem
        suffix = target.suffix
        parent = target.parent
        counter = 1
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _move_file_safely(
        self,
        source: Path,
        destination: Path,
        expected_sha: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Executes file move:
        - If same filesystem: atomic os.replace
        - If cross-filesystem: copy -> fsync -> verify sha256 -> delete source.
        """
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)

            source_dev = source.stat().st_dev
            target_parent_dev = destination.parent.stat().st_dev

            if source_dev == target_parent_dev:
                # Same filesystem: atomic replace
                os.replace(source, destination)
                return True, None
            else:
                # Cross-filesystem: Copy, sync, verify, unlink
                shutil.copy2(source, destination)

                # Ensure written to disk
                with open(destination, "rb") as df:
                    os.fsync(df.fileno())

                # Verify SHA256 of target
                dest_sha = compute_file_sha256(destination)
                if dest_sha != expected_sha:
                    # Incomplete copy! Remove destination and abort
                    try:
                        destination.unlink()
                    except OSError:
                        pass
                    return False, "Cross-filesystem copy failed SHA-256 verification. Source preserved."

                # Only unlink source after destination is fully confirmed
                source.unlink()
                return True, None

        except Exception as e:
            return False, f"Filesystem move error: {str(e)}"

    def _append_to_journal(self, log_entry: OperationLog) -> None:
        """Append log entry to JSON journal file."""
        entries: List[dict] = []
        if self.operations_log_path.exists():
            try:
                with open(self.operations_log_path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except Exception:
                entries = []

        entries.append(log_entry.to_dict())

        try:
            with open(self.operations_log_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
        except OSError:
            pass
