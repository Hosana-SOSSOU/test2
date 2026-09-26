"""
File hashing and integrity verification.
Streaming SHA-256 implementation and ContentHasher protocol.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ContentHasher(Protocol):
    """Protocol for document content hashing algorithms."""

    def compute_hash(self, path: Path) -> str:
        """Compute string representation of hash for a given file."""
        ...


class SHA256Hasher:
    """Computes exact SHA-256 byte digest for a file."""

    def __init__(self, block_size: int = 65536) -> None:
        self.block_size = block_size

    def compute_hash(self, path: Path) -> str:
        """Stream file bytes and compute SHA-256 hex digest."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(self.block_size):
                hasher.update(chunk)
        return hasher.hexdigest()


def compute_file_sha256(path: Path | str, block_size: int = 65536) -> str:
    """Convenience helper to compute SHA-256 for a file."""
    return SHA256Hasher(block_size=block_size).compute_hash(Path(path))
