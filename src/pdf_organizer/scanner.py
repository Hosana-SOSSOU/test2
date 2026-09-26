"""
Filesystem scanner for discovering PDF documents.
Handles recursion, symlinks, extensions, and error tolerance.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Set
from .config import ScannerConfig


class PDFScanner:
    """Recursively scans filesystem paths to discover PDF documents."""

    def __init__(self, config: ScannerConfig | None = None) -> None:
        self.config = config or ScannerConfig()

    def scan_path(self, target_path: Path | str) -> List[Path]:
        """Scan a single directory or file path for PDFs."""
        path = Path(target_path).expanduser().resolve()
        if not path.exists():
            return []

        if path.is_file():
            if self._is_candidate_pdf(path):
                return [path]
            return []

        discovered: List[Path] = []
        visited_dirs: Set[str] = set()

        for root, dirs, files in os.walk(
            str(path),
            followlinks=self.config.follow_symlinks,
            topdown=True,
            onerror=lambda err: None,  # Skip unreadable directories safely
        ):
            real_root = os.path.realpath(root)
            if real_root in visited_dirs:
                # Avoid cyclical symlink loops
                continue
            visited_dirs.add(real_root)

            for filename in files:
                file_path = Path(root) / filename
                if self._is_candidate_pdf(file_path):
                    discovered.append(file_path)

            if not self.config.recursive:
                break

        return sorted(discovered)

    def scan_many(self, paths: Iterable[Path | str]) -> List[Path]:
        """Scan multiple input paths and return deduplicated sorted list of PDF paths."""
        results: Set[Path] = set()
        for p in paths:
            for found in self.scan_path(p):
                results.add(found)
        return sorted(results)

    def _is_candidate_pdf(self, path: Path) -> bool:
        """Check if file matches criteria: regular file, .pdf/.PDF, size check."""
        try:
            if not self.config.follow_symlinks and path.is_symlink():
                return False

            if not path.is_file():
                return False

            suffix = path.suffix.lower()
            if suffix != ".pdf":
                return False

            stat = path.stat()
            if stat.st_size < self.config.min_file_size_bytes:
                return False

            return True
        except (OSError, PermissionError):
            return False
