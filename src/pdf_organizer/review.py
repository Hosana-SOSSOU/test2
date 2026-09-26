"""
Interactive and non-interactive plan and report review helper.
Allows users to scrutinize classifications, evidence, collisions, and duplicates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class PlanReviewer:
    """Provides tools to inspect and display generated reports."""

    def __init__(self, report_json_path: Path | str) -> None:
        self.report_path = Path(report_json_path)
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not self.report_path.exists():
            raise FileNotFoundError(f"Report file not found: {self.report_path}")
        with open(self.report_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def print_summary(self) -> None:
        """Print summary dashboard to stdout."""
        summary = self.data.get("summary", {})
        print("===========================================================")
        print("                   PDF INVENTORY SUMMARY                   ")
        print("===========================================================")
        print(f"Generated at:      {self.data.get('generated_at', 'N/A')}")
        print(f"Total PDFs:        {summary.get('total_pdfs', 0)}")
        print(f"Text PDFs:         {summary.get('text_pdfs', 0)}")
        print(f"OCR Required:      {summary.get('ocr_required', 0)}")
        print(f"Unreadable/Errors: {summary.get('unreadable', 0)}")
        print(f"Duplicate Groups:  {summary.get('duplicate_groups', 0)} ({summary.get('total_duplicate_files', 0)} files)")
        print(f"High Confidence:   {summary.get('high_confidence', 0)}")
        print(f"Needs Review:      {summary.get('needs_review', 0)}")
        print("===========================================================")

    def list_plans(
        self,
        category_filter: Optional[str] = None,
        only_needs_review: bool = False,
        limit: int = 50,
    ) -> None:
        """Display list of relocation plans with criteria."""
        plans = self.data.get("plans", [])
        classifications = self.data.get("classifications", {})

        displayed = 0
        for p in plans:
            cat = p.get("category", "")
            score = p.get("score", 0.0)
            status = p.get("status", "")

            if category_filter and category_filter.lower() not in cat.lower():
                continue

            if only_needs_review and status not in ("NEEDS_REVIEW", "COLLISION", "BATCH_COLLISION") and cat != "À_classer":
                continue

            src = p.get("source", "")
            dst = p.get("destination", "")
            cls_info = classifications.get(src, {})
            evidence = cls_info.get("evidence", [])

            print(f"\n[Status: {status}] {Path(src).name}")
            print(f"  Source:      {src}")
            print(f"  Destination: {dst}")
            print(f"  Category:    {cat} (Score: {score:.2f})")
            if evidence:
                print(f"  Evidence:    {', '.join(evidence)}")
            print(f"  Reason:      {p.get('reason', '')}")

            displayed += 1
            if displayed >= limit:
                print(f"\n... and {len(plans) - displayed} more plans. (Use specific filters to view).")
                break

    def list_duplicates(self) -> None:
        """Display exact duplicate clusters."""
        groups = self.data.get("duplicate_groups", [])
        if not groups:
            print("No duplicate files identified.")
            return

        print(f"Identified {len(groups)} exact duplicate groups (SHA-256):")
        for idx, g in enumerate(groups, 1):
            print(f"\nDuplicate Group #{idx} (Hash: {g.get('sha256', '')[:16]}..., Size: {g.get('size_bytes', 0):,} bytes)")
            for f in g.get("files", []):
                print(f"  - {f}")
