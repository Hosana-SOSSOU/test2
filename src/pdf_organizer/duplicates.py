"""
Duplicate detection engine based on cryptographic byte hashes.
Identifies identical content across disparate paths without automated deletion.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List
from .hashing import compute_file_sha256
from .models import Document, DuplicateGroup


class DuplicateDetector:
    """Detects exact byte duplicates using SHA-256."""

    def find_duplicates_from_documents(self, documents: Iterable[Document]) -> List[DuplicateGroup]:
        """Group documents sharing identical SHA-256 digests."""
        hash_map: Dict[str, List[Document]] = defaultdict(list)

        for doc in documents:
            if doc.sha256:
                hash_map[doc.sha256].append(doc)

        duplicate_groups: List[DuplicateGroup] = []
        for digest, docs in hash_map.items():
            if len(docs) > 1:
                duplicate_groups.append(
                    DuplicateGroup(
                        sha256=digest,
                        size_bytes=docs[0].size_bytes,
                        files=[d.path for d in docs],
                    )
                )

        return sorted(duplicate_groups, key=lambda g: len(g.files), reverse=True)

    def find_duplicates_from_paths(self, paths: Iterable[Path]) -> List[DuplicateGroup]:
        """Compute SHA-256 for a collection of files and return duplicates."""
        # Preliminary filter by file size to avoid unnecessary hashing
        size_map: Dict[int, List[Path]] = defaultdict(list)
        for p in paths:
            try:
                size_map[p.stat().st_size].append(p)
            except OSError:
                continue

        # Hash only files where size collision exists
        hash_map: Dict[str, List[Path]] = defaultdict(list)
        for size, candidate_paths in size_map.items():
            if len(candidate_paths) > 1:
                for cp in candidate_paths:
                    try:
                        h = compute_file_sha256(cp)
                        hash_map[h].append(cp)
                    except OSError:
                        continue

        groups: List[DuplicateGroup] = []
        for digest, files in hash_map.items():
            if len(files) > 1:
                size = files[0].stat().st_size
                groups.append(DuplicateGroup(sha256=digest, size_bytes=size, files=files))

        return sorted(groups, key=lambda g: len(g.files), reverse=True)
