"""
Multi-format reporting engine: CSV, JSON, and Markdown.
Outputs detailed analytics and human-readable organization plans.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from .models import Classification, Document, DuplicateGroup, MovePlan, TextStatus


class ReportGenerator:
    """Generates structured CSV, JSON, and Markdown reports."""

    def __init__(
        self,
        documents: List[Document],
        classifications: Dict[str, Classification],
        plans: List[MovePlan],
        duplicate_groups: Optional[List[DuplicateGroup]] = None,
    ) -> None:
        self.documents = documents
        self.classifications = classifications
        self.plans = plans
        self.duplicate_groups = duplicate_groups or []
        self.plan_map: Dict[str, MovePlan] = {str(p.source): p for p in plans}

    def generate_all(self, output_dir: Path | str = "reports") -> Dict[str, Path]:
        """Generate CSV, JSON, and Markdown in the target directory."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        csv_file = out_path / "report.csv"
        json_file = out_path / "report.json"
        md_file = out_path / "report.md"

        self.write_csv(csv_file)
        self.write_json(json_file)
        self.write_markdown(md_file)

        return {
            "csv": csv_file,
            "json": json_file,
            "md": md_file,
        }

    def write_csv(self, file_path: Path) -> None:
        """Export tabular summary to CSV."""
        headers = [
            "source_path",
            "filename",
            "size_bytes",
            "modified_at",
            "page_count",
            "title",
            "author",
            "text_length",
            "text_status",
            "ocr_status",
            "sha256",
            "category",
            "destination",
            "score",
            "classifier",
            "evidence",
            "reason",
            "status",
            "error",
        ]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for doc in self.documents:
                key = str(doc.path)
                cls_info = self.classifications.get(key)
                plan_info = self.plan_map.get(key)

                category = cls_info.category if cls_info else ""
                dest = str(plan_info.destination) if plan_info else ""
                score = cls_info.score if cls_info else 0.0
                classifier = cls_info.classifier if cls_info else ""
                evidence_str = "; ".join(cls_info.evidence) if cls_info else ""
                reason = cls_info.reason if cls_info else ""
                status = plan_info.status if plan_info else ""
                error = doc.error or ""

                writer.writerow([
                    str(doc.path),
                    doc.filename,
                    doc.size_bytes,
                    doc.modified_at.isoformat() if doc.modified_at else "",
                    doc.page_count if doc.page_count is not None else "",
                    doc.title or "",
                    doc.author or "",
                    doc.text_length,
                    doc.text_status.value,
                    doc.ocr_status.value,
                    doc.sha256 or "",
                    category,
                    dest,
                    score,
                    classifier,
                    evidence_str,
                    reason,
                    status,
                    error,
                ])

    def write_json(self, file_path: Path) -> None:
        """Export complete structured dataset to JSON."""
        data: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self._compute_summary(),
            "documents": [doc.to_dict() for doc in self.documents],
            "classifications": {k: v.to_dict() for k, v in self.classifications.items()},
            "plans": [p.to_dict() for p in self.plans],
            "duplicate_groups": [g.to_dict() for g in self.duplicate_groups],
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def write_markdown(self, file_path: Path) -> None:
        """Export human-readable Markdown summary."""
        summary = self._compute_summary()
        lines = [
            "# PDF Organization Report",
            "",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "## Summary Metrics",
            "",
            f"- **Total PDFs**: {summary['total_pdfs']}",
            f"- **Text PDFs**: {summary['text_pdfs']}",
            f"- **OCR Required**: {summary['ocr_required']}",
            f"- **Unreadable / Error**: {summary['unreadable']}",
            f"- **Duplicate Groups**: {summary['duplicate_groups']} ({summary['total_duplicate_files']} files)",
            f"- **High Confidence Classifications**: {summary['high_confidence']}",
            f"- **Needs Review**: {summary['needs_review']}",
            "",
            "## Proposed Moves",
            "",
        ]

        if not self.plans:
            lines.append("*No move plans generated.*")
        else:
            for idx, plan in enumerate(self.plans, 1):
                cls_info = self.classifications.get(str(plan.source))
                evidence_items = cls_info.evidence if cls_info else []

                lines.append(f"### {idx}. {plan.source.name}")
                lines.append(f"- **Source**: `{plan.source}`")
                lines.append(f"- **Destination**: `{plan.destination}`")
                lines.append(f"- **Category**: `{plan.category}`")
                lines.append(f"- **Score**: `{plan.score:.2f}`")
                if cls_info:
                    lines.append(f"- **Classifier**: `{cls_info.classifier}`")
                if evidence_items:
                    lines.append("- **Evidence**:")
                    for ev in evidence_items:
                        lines.append(f"  - {ev}")
                lines.append(f"- **Status**: `{plan.status}`")
                lines.append(f"- **Reason**: {plan.reason}")
                lines.append("")

        if self.duplicate_groups:
            lines.append("## Exact Duplicate Groups (SHA-256)")
            lines.append("")
            for idx, group in enumerate(self.duplicate_groups, 1):
                lines.append(f"### Group #{idx} ({group.size_bytes:,} bytes)")
                lines.append(f"SHA-256: `{group.sha256}`")
                lines.append("Files:")
                for fp in group.files:
                    lines.append(f"- `{fp}`")
                lines.append("")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _compute_summary(self) -> Dict[str, int]:
        total = len(self.documents)
        text_count = sum(1 for d in self.documents if d.text_status == TextStatus.TEXT_AVAILABLE)
        ocr_count = sum(1 for d in self.documents if d.text_status == TextStatus.OCR_REQUIRED)
        error_count = sum(1 for d in self.documents if d.text_status in (TextStatus.ERROR, TextStatus.EMPTY))

        high_conf = sum(1 for c in self.classifications.values() if c.score >= 0.75 and c.category != "À_classer")
        needs_rev = sum(1 for c in self.classifications.values() if c.score < 0.75 or c.category == "À_classer")

        dup_files = sum(len(g.files) for g in self.duplicate_groups)

        return {
            "total_pdfs": total,
            "text_pdfs": text_count,
            "ocr_required": ocr_count,
            "unreadable": error_count,
            "duplicate_groups": len(self.duplicate_groups),
            "total_duplicate_files": dup_files,
            "high_confidence": high_conf,
            "needs_review": needs_rev,
        }
