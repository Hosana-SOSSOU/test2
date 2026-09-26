"""
Rollback engine for PDF Organizer.
Safely reverses recorded move operations with cryptographic integrity checks.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from .hashing import compute_file_sha256
from .models import OperationLog


class RollbackManager:
    """Manages reversible filesystem restorations."""

    def __init__(self, log_path: Path | str = "operations.json") -> None:
        self.log_path = Path(log_path)

    def undo_all(self) -> List[OperationLog]:
        """
        Reverse all successful moves recorded in operations log in reverse chronological order.
        """
        if not self.log_path.exists():
            return []

        with open(self.log_path, "r", encoding="utf-8") as f:
            raw_entries = json.load(f)

        entries = [OperationLog.from_dict(d) for d in raw_entries]
        # Filter only successful MOVE operations
        successful_moves = [e for e in entries if e.operation == "MOVE" and e.status == "SUCCESS"]

        rollback_logs: List[OperationLog] = []

        # Process in reverse order
        for entry in reversed(successful_moves):
            current_path = Path(entry.destination).resolve()
            original_source = Path(entry.source).resolve()

            # 1. Verify current path exists
            if not current_path.exists():
                rollback_logs.append(
                    OperationLog(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        operation="UNDO",
                        source=str(current_path),
                        destination=str(original_source),
                        sha256=entry.sha256,
                        status="FAILED",
                        details="Destination file not found (cannot restore).",
                    )
                )
                continue

            # 2. Verify hash has not changed
            if entry.sha256:
                try:
                    current_hash = compute_file_sha256(current_path)
                    if current_hash != entry.sha256:
                        rollback_logs.append(
                            OperationLog(
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                operation="UNDO",
                                source=str(current_path),
                                destination=str(original_source),
                                sha256=current_hash,
                                status="FAILED",
                                details="File was modified at destination after move (hash mismatch).",
                            )
                        )
                        continue
                except OSError as e:
                    rollback_logs.append(
                        OperationLog(
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            operation="UNDO",
                            source=str(current_path),
                            destination=str(original_source),
                            sha256=entry.sha256,
                            status="FAILED",
                            details=f"Hashing error during rollback: {e}",
                        )
                    )
                    continue

            # 3. Verify original source is not occupied
            if original_source.exists():
                rollback_logs.append(
                    OperationLog(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        operation="UNDO",
                        source=str(current_path),
                        destination=str(original_source),
                        sha256=entry.sha256,
                        status="FAILED",
                        details="Original source path is already occupied. Will not overwrite.",
                    )
                )
                continue

            # 4. Revert file location
            try:
                original_source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(current_path, original_source)
                rollback_logs.append(
                    OperationLog(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        operation="UNDO",
                        source=str(current_path),
                        destination=str(original_source),
                        sha256=entry.sha256,
                        status="SUCCESS",
                        details="Restored to original location.",
                    )
                )
            except Exception as e:
                rollback_logs.append(
                    OperationLog(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        operation="UNDO",
                        source=str(current_path),
                        destination=str(original_source),
                        sha256=entry.sha256,
                        status="FAILED",
                        details=f"Error restoring file: {str(e)}",
                    )
                )

        # Append rollback logs to the journal
        raw_entries.extend([r.to_dict() for r in rollback_logs])
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(raw_entries, f, indent=2, ensure_ascii=False)

        return rollback_logs
