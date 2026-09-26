"""
Base abstractions, results, and local caching for OCR backends.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@dataclass(slots=True)
class OCRResult:
    """Result of an OCR operation on a document."""
    text: str
    confidence: float
    engine: str
    version: str
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OCRResult:
        return cls(
            text=str(data.get("text", "")),
            confidence=float(data.get("confidence", 0.0)),
            engine=str(data.get("engine", "unknown")),
            version=str(data.get("version", "unknown")),
            success=bool(data.get("success", False)),
            error=data.get("error"),
        )


@runtime_checkable
class OCRBackend(Protocol):
    """Protocol for local OCR engines."""

    @property
    def engine_name(self) -> str:
        """Name of the OCR engine."""
        ...

    @property
    def engine_version(self) -> str:
        """Installed version of the OCR engine."""
        ...

    def is_available(self) -> bool:
        """Verify if the local OCR engine binary/libraries are available."""
        ...

    def extract_text(self, pdf_path: Path) -> OCRResult:
        """Extract text from the specified PDF path."""
        ...


class OCRCache:
    """Persistent local cache for OCR extraction results indexed by file hash."""

    def __init__(self, cache_dir: Path | str = ".pdf_organizer_cache/ocr") -> None:
        self.cache_dir = Path(cache_dir)

    def _get_cache_path(self, document_hash: str, engine: str, version: str) -> Path:
        sanitized_engine = engine.replace("/", "_")
        sanitized_version = version.replace("/", "_")
        key = f"{document_hash}_{sanitized_engine}_{sanitized_version}.json"
        return self.cache_dir / key

    def get(self, document_hash: str, engine: str, version: str) -> Optional[OCRResult]:
        """Retrieve cached OCR result if available."""
        cache_file = self._get_cache_path(document_hash, engine, version)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return OCRResult.from_dict(data["result"])
        except Exception:
            return None

    def set(
        self,
        document_hash: str,
        engine: str,
        version: str,
        result: OCRResult,
    ) -> None:
        """Store OCR result in local disk cache."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self._get_cache_path(document_hash, engine, version)
            payload = {
                "document_hash": document_hash,
                "engine": engine,
                "version": version,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "result": result.to_dict(),
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except OSError:
            # Failing to write cache should not break processing
            pass
