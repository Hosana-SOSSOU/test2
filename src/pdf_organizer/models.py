"""
Data models for Local Intelligent PDF Organizer.
Strict dataclasses, Enums, and serialization helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TextStatus(str, Enum):
    """Status of extracted text from a PDF."""
    TEXT_AVAILABLE = "TEXT_AVAILABLE"
    EMPTY = "EMPTY"
    OCR_REQUIRED = "OCR_REQUIRED"
    ERROR = "ERROR"


class OCRStatus(str, Enum):
    """Status of OCR processing for a PDF."""
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(slots=True)
class Document:
    """Represents a discovered and inspected PDF document."""
    path: Path
    filename: str
    size_bytes: int
    modified_at: datetime

    page_count: Optional[int] = None

    title: Optional[str] = None
    author: Optional[str] = None
    pdf_metadata: Dict[str, Optional[str]] = field(default_factory=dict)

    text: str = ""
    text_length: int = 0

    text_status: TextStatus = TextStatus.EMPTY

    sha256: Optional[str] = None

    ocr_status: OCRStatus = OCRStatus.NOT_REQUIRED

    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize document to dictionary."""
        return {
            "path": str(self.path),
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at.isoformat(),
            "page_count": self.page_count,
            "title": self.title,
            "author": self.author,
            "pdf_metadata": self.pdf_metadata,
            "text": self.text,
            "text_length": self.text_length,
            "text_status": self.text_status.value,
            "sha256": self.sha256,
            "ocr_status": self.ocr_status.value,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Document:
        """Construct document from dictionary."""
        mod_at = data.get("modified_at")
        if isinstance(mod_at, str):
            try:
                mod_dt = datetime.fromisoformat(mod_at)
            except ValueError:
                mod_dt = datetime.now()
        elif isinstance(mod_at, datetime):
            mod_dt = mod_at
        else:
            mod_dt = datetime.now()

        text_status_val = data.get("text_status", TextStatus.EMPTY.value)
        ocr_status_val = data.get("ocr_status", OCRStatus.NOT_REQUIRED.value)

        return cls(
            path=Path(data["path"]),
            filename=data.get("filename", Path(data["path"]).name),
            size_bytes=int(data.get("size_bytes", 0)),
            modified_at=mod_dt,
            page_count=data.get("page_count"),
            title=data.get("title"),
            author=data.get("author"),
            pdf_metadata=data.get("pdf_metadata", {}),
            text=data.get("text", ""),
            text_length=int(data.get("text_length", len(data.get("text", "")))),
            text_status=TextStatus(text_status_val) if text_status_val in TextStatus.__members__.values() else TextStatus.EMPTY,
            sha256=data.get("sha256"),
            ocr_status=OCRStatus(ocr_status_val) if ocr_status_val in OCRStatus.__members__.values() else OCRStatus.NOT_REQUIRED,
            error=data.get("error"),
        )


@dataclass(slots=True)
class Classification:
    """Classification assessment of a document."""
    category: str
    score: float
    evidence: List[str]
    reason: str
    classifier: str

    def __post_init__(self) -> None:
        # Guarantee score remains bounded between 0.0 and 1.0
        if not (0.0 <= self.score <= 1.0):
            # Clamp safely and log warning if required
            clamped = max(0.0, min(1.0, float(self.score)))
            object.__setattr__(self, "score", round(clamped, 4))
        else:
            object.__setattr__(self, "score", round(self.score, 4))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "score": self.score,
            "evidence": list(self.evidence),
            "reason": self.reason,
            "classifier": self.classifier,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Classification:
        return cls(
            category=str(data.get("category", "À_classer")),
            score=float(data.get("score", 0.0)),
            evidence=list(data.get("evidence", [])),
            reason=str(data.get("reason", "")),
            classifier=str(data.get("classifier", "rule_based")),
        )


@dataclass(slots=True)
class MovePlan:
    """Concrete filesystem relocation proposal."""
    source: Path
    destination: Path
    category: str
    score: float
    reason: str
    sha256: Optional[str]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": str(self.source),
            "destination": str(self.destination),
            "category": self.category,
            "score": self.score,
            "reason": self.reason,
            "sha256": self.sha256,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MovePlan:
        return cls(
            source=Path(data["source"]),
            destination=Path(data["destination"]),
            category=str(data.get("category", "")),
            score=float(data.get("score", 0.0)),
            reason=str(data.get("reason", "")),
            sha256=data.get("sha256"),
            status=str(data.get("status", "PROPOSED")),
        )


@dataclass(slots=True)
class OperationLog:
    """Record of a filesystem operation for logging and rollback."""
    timestamp: str
    operation: str  # "MOVE" or "UNDO"
    source: str
    destination: str
    sha256: Optional[str]
    status: str  # "SUCCESS", "FAILED", "SKIPPED"
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OperationLog:
        return cls(
            timestamp=data["timestamp"],
            operation=data["operation"],
            source=data["source"],
            destination=data["destination"],
            sha256=data.get("sha256"),
            status=data["status"],
            details=data.get("details"),
        )


@dataclass(slots=True)
class DuplicateGroup:
    """Group of files having identical SHA-256 byte hashes."""
    sha256: str
    size_bytes: int
    files: List[Path]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "files": [str(f) for f in self.files],
        }
