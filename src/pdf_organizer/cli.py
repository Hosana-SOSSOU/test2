"""
Command Line Interface for Local Intelligent PDF Organizer.
Provides subcommands: scan, ocr, classify, plan, review, simulate, apply, undo, duplicates, process.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .config import AppConfig
from .duplicates import DuplicateDetector
from .extractor import DocumentExtractor
from .hashing import compute_file_sha256
from .llm.llamacpp import LlamaCppLocalLLM
from .llm.ollama import OllamaLocalLLM
from .models import Classification, Document, MovePlan, OCRStatus, TextStatus
from .mover import FileMover
from .ocr.base import OCRCache
from .ocr.tesseract import TesseractOCRBackend
from .planner import MovePlanner
from .reports import ReportGenerator
from .review import PlanReviewer
from .scanner import PDFScanner
from .simulator import Simulator
from .taxonomy import Taxonomy
from .undo import RollbackManager


def create_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="pdf-organizer",
        description="Local Intelligent PDF Organizer for Linux. Safe, offline, explainable document organization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        "-c",
        default="config/config.yaml",
        help="Path to YAML configuration file (default: config/config.yaml)",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # 1. SCAN
    scan_parser = subparsers.add_parser("scan", help="Discover PDFs and inspect metadata & text without modifying files.")
    scan_parser.add_argument("paths", nargs="+", help="Directories or files to scan recursively.")
    scan_parser.add_argument("--output-dir", "-o", default="reports", help="Directory to save report.csv/.json/.md")

    # 2. OCR
    ocr_parser = subparsers.add_parser("ocr", help="Process OCR on documents flagged as OCR_REQUIRED.")
    ocr_parser.add_argument("report", help="Path to report.json containing OCR_REQUIRED documents.")
    ocr_parser.add_argument("--lang", default=None, help="Tesseract language string (e.g. fra+eng)")
    ocr_parser.add_argument("--output-dir", "-o", default="reports", help="Directory to save updated reports")

    # 3. CLASSIFY
    cls_parser = subparsers.add_parser("classify", help="Classify documents from an existing report or directory.")
    cls_parser.add_argument("report", help="Path to report.json or directory to classify.")
    cls_parser.add_argument("--backend", choices=["rule_based", "local_llm"], default=None, help="Override classifier backend")
    cls_parser.add_argument("--output-dir", "-o", default="reports", help="Directory to save classified reports")

    # 4. PLAN
    plan_parser = subparsers.add_parser("plan", help="Compute relocation plan based on classifications and target directory.")
    plan_parser.add_argument("report", help="Path to report.json containing classified documents.")
    plan_parser.add_argument("target_dir", help="Base target directory for organized documents (e.g. ~/Documents/Organized)")
    plan_parser.add_argument("--output-dir", "-o", default="reports", help="Directory to save updated plan")

    # 5. REVIEW
    rev_parser = subparsers.add_parser("review", help="Inspect generated reports, classifications, and potential collisions.")
    rev_parser.add_argument("report", help="Path to report.json to review.")
    rev_parser.add_argument("--filter-category", help="Filter moves by category name substring.")
    rev_parser.add_argument("--needs-review", action="store_true", help="Only show documents requiring human review.")
    rev_parser.add_argument("--show-duplicates", action="store_true", help="List identified duplicate clusters.")

    # 6. SIMULATE
    sim_parser = subparsers.add_parser("simulate", help="Perform comprehensive dry-run validation with zero filesystem changes.")
    sim_parser.add_argument("plan", help="Path to report.json or plan.json to simulate.")

    # 7. APPLY
    apply_parser = subparsers.add_parser("apply", help="Execute approved move operations (requires --yes or manual confirmation).")
    apply_parser.add_argument("plan", help="Path to report.json or plan.json to execute.")
    apply_parser.add_argument("--yes", "-y", action="store_true", help="Confirm execution without interactive prompt.")
    apply_parser.add_argument("--journal", default="operations.json", help="Path to write operation logs for rollback.")

    # 8. UNDO
    undo_parser = subparsers.add_parser("undo", help="Safely reverse operations recorded in operations.json.")
    undo_parser.add_argument("--journal", default="operations.json", help="Path to operations log journal.")

    # 9. DUPLICATES
    dup_parser = subparsers.add_parser("duplicates", help="Identify exact SHA-256 byte duplicates across paths.")
    dup_parser.add_argument("paths", nargs="+", help="Directories to scan for duplicate files.")

    # 10. PROCESS (all-in-one pipeline without applying changes)
    proc_parser = subparsers.add_parser(
        "process",
        help="Run discovery, OCR checks, classification, planning, and generate reports in one safe step without moving files.",
    )
    proc_parser.add_argument("paths", nargs="+", help="Source directories to process.")
    proc_parser.add_argument("--target-dir", required=True, help="Target base directory for organized documents.")
    proc_parser.add_argument("--output-dir", "-o", default="reports", help="Directory to save reports.")

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """CLI entrypoint."""
    parser = create_parser()
    parsed = parser.parse_args(args)

    if not parsed.subcommand:
        parser.print_help()
        return 0

    config = AppConfig.load(parsed.config)
    taxonomy = Taxonomy.load(config.classification.taxonomy_path)

    # Dispatch subcommand
    cmd = parsed.subcommand
    try:
        if cmd == "scan":
            return cmd_scan(parsed.paths, parsed.output_dir, config)
        elif cmd == "ocr":
            return cmd_ocr(parsed.report, parsed.output_dir, config, lang=parsed.lang)
        elif cmd == "classify":
            return cmd_classify(parsed.report, parsed.output_dir, config, taxonomy, parsed.backend)
        elif cmd == "plan":
            return cmd_plan(parsed.report, parsed.target_dir, parsed.output_dir, config)
        elif cmd == "review":
            return cmd_review(parsed.report, parsed.filter_category, parsed.needs_review, parsed.show_duplicates)
        elif cmd == "simulate":
            return cmd_simulate(parsed.plan, config)
        elif cmd == "apply":
            return cmd_apply(parsed.plan, parsed.journal, parsed.yes, config)
        elif cmd == "undo":
            return cmd_undo(parsed.journal)
        elif cmd == "duplicates":
            return cmd_duplicates(parsed.paths, config)
        elif cmd == "process":
            return cmd_process(parsed.paths, parsed.target_dir, parsed.output_dir, config, taxonomy)
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"\n[ERROR] Operation failed: {str(e)}", file=sys.stderr)
        return 1


# ---------------- SUBCOMMAND IMPLEMENTATIONS ----------------


def cmd_scan(paths: List[str], output_dir: str, config: AppConfig) -> int:
    """Discover files, inspect metadata and extract text."""
    print(f"Scanning {len(paths)} path(s) for PDF files...")
    scanner = PDFScanner(config.scanner)
    discovered = scanner.scan_many(paths)

    if not discovered:
        print("No PDF documents found in the specified path(s).")
        return 0

    print(f"Discovered {len(discovered)} PDF file(s). Inspecting metadata & text...")
    extractor = DocumentExtractor(config.ocr)
    documents = [extractor.process(p) for p in discovered]

    # Find duplicates
    detector = DuplicateDetector()
    duplicates = detector.find_duplicates_from_documents(documents)

    generator = ReportGenerator(
        documents=documents,
        classifications={},
        plans=[],
        duplicate_groups=duplicates,
    )
    paths_dict = generator.generate_all(output_dir)

    print("\nScan completed successfully.")
    print(f"  Total inspected: {len(documents)}")
    print(f"  Reports saved in: {output_dir}")
    print(f"    - JSON: {paths_dict['json']}")
    print(f"    - CSV:  {paths_dict['csv']}")
    print(f"    - MD:   {paths_dict['md']}")
    return 0


def cmd_ocr(report_path: str, output_dir: str, config: AppConfig, lang: Optional[str] = None) -> int:
    """Execute OCR on documents marked OCR_REQUIRED."""
    rep_p = Path(report_path)
    if not rep_p.exists():
        print(f"Error: Report file '{report_path}' not found.", file=sys.stderr)
        return 1

    with open(rep_p, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = [Document.from_dict(d) for d in data.get("documents", [])]
    ocr_targets = [d for d in docs if d.text_status == TextStatus.OCR_REQUIRED]

    if not ocr_targets:
        print("No documents requiring OCR in this report.")
        return 0

    print(f"Found {len(ocr_targets)} document(s) requiring OCR.")
    ocr_backend = TesseractOCRBackend(
        tesseract_cmd=config.ocr.tesseract_cmd,
        lang=lang or config.ocr.lang,
    )

    if not ocr_backend.is_available():
        print("[WARNING] Local Tesseract OCR is not installed or not in PATH.", file=sys.stderr)
        print("Install on Linux via: sudo apt install tesseract-ocr tesseract-ocr-fra", file=sys.stderr)
        return 1

    cache = OCRCache(config.ocr.cache_dir)
    processed = 0

    for doc in ocr_targets:
        print(f"Processing OCR for: {doc.filename}...")
        sha = doc.sha256 or compute_file_sha256(doc.path)

        cached_res = cache.get(sha, ocr_backend.engine_name, ocr_backend.engine_version)
        if cached_res:
            print("  -> Using cached OCR result.")
            res = cached_res
        else:
            res = ocr_backend.extract_text(doc.path)
            if res.success:
                cache.set(sha, ocr_backend.engine_name, ocr_backend.engine_version, res)

        if res.success:
            doc.text = res.text
            doc.text_length = len(res.text.strip())
            doc.text_status = TextStatus.TEXT_AVAILABLE
            doc.ocr_status = OCRStatus.COMPLETED
            processed += 1
        else:
            doc.ocr_status = OCRStatus.FAILED
            doc.error = res.error
            print(f"  -> OCR failed: {res.error}")

    # Re-save reports
    classifications = {k: Classification.from_dict(v) for k, v in data.get("classifications", {}).items()}
    plans = [MovePlan.from_dict(p) for p in data.get("plans", [])]
    duplicates = [DuplicateDetector().find_duplicates_from_documents(docs)]

    generator = ReportGenerator(docs, classifications, plans, duplicates[0])
    generator.generate_all(output_dir)
    print(f"\nOCR pass complete. {processed}/{len(ocr_targets)} documents processed successfully.")
    return 0


def cmd_classify(
    report_path: str,
    output_dir: str,
    config: AppConfig,
    taxonomy: Taxonomy,
    backend_override: Optional[str] = None,
) -> int:
    """Classify documents using rule-based or local LLM engine."""
    rep_p = Path(report_path)
    if not rep_p.exists():
        print(f"Error: Report file '{report_path}' not found.", file=sys.stderr)
        return 1

    with open(rep_p, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = [Document.from_dict(d) for d in data.get("documents", [])]
    backend = backend_override or config.classification.backend

    from .classification.rule_based import RuleBasedClassifier
    classifier = RuleBasedClassifier(
        taxonomy=taxonomy,
        manual_review_threshold=config.classification.manual_review_threshold,
        unclassified_category=config.classification.default_unclassified_category,
    )

    if backend == "local_llm":
        from .classification.local_llm import LocalLLMClassifier
        llm_engine = (
            OllamaLocalLLM(model=config.llm.model, endpoint=config.llm.endpoint)
            if config.llm.backend == "ollama"
            else LlamaCppLocalLLM(endpoint=config.llm.endpoint)
        )
        classifier = LocalLLMClassifier(
            llm=llm_engine,
            taxonomy=taxonomy,
            fallback_classifier=classifier,
            manual_review_threshold=config.classification.manual_review_threshold,
            unclassified_category=config.classification.default_unclassified_category,
        )

    print(f"Classifying {len(docs)} document(s) using backend: {classifier.name}...")
    classifications: Dict[str, Classification] = {}
    for doc in docs:
        cls_res = classifier.classify(doc)
        classifications[str(doc.path)] = cls_res

    # Save
    plans = [MovePlan.from_dict(p) for p in data.get("plans", [])]
    duplicates = DuplicateDetector().find_duplicates_from_documents(docs)
    generator = ReportGenerator(docs, classifications, plans, duplicates)
    generator.generate_all(output_dir)

    print(f"Classification completed. Reports updated in '{output_dir}'.")
    return 0


def cmd_plan(
    report_path: str,
    target_dir: str,
    output_dir: str,
    config: AppConfig,
) -> int:
    """Compute destinations and construct MovePlan objects."""
    rep_p = Path(report_path)
    if not rep_p.exists():
        print(f"Error: Report file '{report_path}' not found.", file=sys.stderr)
        return 1

    with open(rep_p, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = [Document.from_dict(d) for d in data.get("documents", [])]
    classifications = {k: Classification.from_dict(v) for k, v in data.get("classifications", {}).items()}

    pairs = []
    for doc in docs:
        cls_info = classifications.get(str(doc.path))
        if not cls_info:
            cls_info = Classification(
                category=config.classification.default_unclassified_category,
                score=0.0,
                evidence=[],
                reason="Document not yet classified.",
                classifier="unclassified",
            )
        pairs.append((doc, cls_info))

    planner = MovePlanner(target_base_dir=target_dir, safety_config=config.safety)
    plans = planner.plan_all(pairs)

    duplicates = DuplicateDetector().find_duplicates_from_documents(docs)
    generator = ReportGenerator(docs, classifications, plans, duplicates)
    generator.generate_all(output_dir)

    print(f"Plan constructed for {len(plans)} document(s) targeting: {target_dir}")
    print(f"Reports saved in '{output_dir}'. Run 'pdf-organizer simulate {output_dir}/report.json' to review.")
    return 0


def cmd_review(
    report_path: str,
    category_filter: Optional[str] = None,
    only_needs_review: bool = False,
    show_duplicates: bool = False,
) -> int:
    """Display review summaries and inspection tools."""
    reviewer = PlanReviewer(report_path)
    reviewer.print_summary()

    if show_duplicates:
        reviewer.list_duplicates()
    else:
        reviewer.list_plans(
            category_filter=category_filter,
            only_needs_review=only_needs_review,
        )
    return 0


def cmd_simulate(plan_path: str, config: AppConfig) -> int:
    """Execute complete dry-run validation without moving any files."""
    p_path = Path(plan_path)
    if not p_path.exists():
        print(f"Error: File '{plan_path}' not found.", file=sys.stderr)
        return 1

    with open(p_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Could be report.json or standalone plans json
    raw_plans = data.get("plans", data if isinstance(data, list) else [])
    plans = [MovePlan.from_dict(p) for p in raw_plans]

    if not plans:
        print("No relocation plans found in the specified file.")
        return 1

    simulator = Simulator(allowed_base_dir=config.safety.destination_base_dir)
    result = simulator.simulate(plans)

    print(result.format_report())
    return 0


def cmd_apply(plan_path: str, journal_path: str, auto_confirm: bool, config: AppConfig) -> int:
    """Apply approved moves to the filesystem with safety confirmation."""
    p_path = Path(plan_path)
    if not p_path.exists():
        print(f"Error: File '{plan_path}' not found.", file=sys.stderr)
        return 1

    with open(p_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_plans = data.get("plans", data if isinstance(data, list) else [])
    plans = [MovePlan.from_dict(p) for p in raw_plans]

    if not plans:
        print("No relocation plans found.")
        return 0

    # 1. Run simulator first to check safety
    simulator = Simulator(allowed_base_dir=config.safety.destination_base_dir)
    sim_result = simulator.simulate(plans)

    print(f"Prepared to move {sim_result.would_move} file(s).")
    print(f"Collisions: {sim_result.collisions}, Requiring review: {sim_result.manual_reviews}")

    if sim_result.would_move == 0:
        print("Nothing to move. Exiting safely.")
        return 0

    # 2. Require confirmation
    if not auto_confirm:
        print("\nWARNING: This command will modify the filesystem by moving files.")
        print(f"All operations will be recorded in '{journal_path}' for rollback.")
        choice = input("Are you sure you want to proceed? [y/N]: ").strip().lower()
        if choice not in ("y", "yes"):
            print("Operation aborted by user.")
            return 0

    # 3. Execute
    mover = FileMover(safety_config=config.safety, operations_log_path=journal_path)
    # Filter plans to those simulation approved
    approved_plans = [item.plan for item in sim_result.items if item.would_execute]

    print(f"\nMoving {len(approved_plans)} file(s)...")
    logs = mover.execute_plan(approved_plans)

    success_count = sum(1 for log in logs if log.status == "SUCCESS")
    failed_count = sum(1 for log in logs if log.status == "FAILED")
    skipped_count = sum(1 for log in logs if log.status == "SKIPPED")

    print("\nMove execution completed:")
    print(f"  Successfully moved: {success_count}")
    print(f"  Skipped (collision): {skipped_count}")
    print(f"  Failed:              {failed_count}")
    print(f"  Journal written to:  {journal_path}")
    print(f"To undo this operation at any time, run: pdf-organizer undo --journal {journal_path}")
    return 0


def cmd_undo(journal_path: str) -> int:
    """Reverse operations from the journal log."""
    j_path = Path(journal_path)
    if not j_path.exists():
        print(f"Error: Operations journal '{journal_path}' not found.", file=sys.stderr)
        return 1

    manager = RollbackManager(journal_path)
    rollback_logs = manager.undo_all()

    if not rollback_logs:
        print("No operations available for rollback.")
        return 0

    success = sum(1 for l in rollback_logs if l.status == "SUCCESS")
    failed = sum(1 for l in rollback_logs if l.status == "FAILED")

    print(f"Rollback completed: {success} restored, {failed} failed.")
    for l in rollback_logs:
        print(f"  [{l.status}] {Path(l.destination).name} -> {l.destination} ({l.details or ''})")
    return 0


def cmd_duplicates(paths: List[str], config: AppConfig) -> int:
    """Scan and list exact duplicate files."""
    scanner = PDFScanner(config.scanner)
    files = scanner.scan_many(paths)
    if not files:
        print("No PDF files discovered.")
        return 0

    print(f"Analyzing {len(files)} files for duplicate SHA-256 byte hashes...")
    detector = DuplicateDetector()
    groups = detector.find_duplicates_from_paths(files)

    if not groups:
        print("No duplicate files found.")
        return 0

    total_wasted = sum((len(g.files) - 1) * g.size_bytes for g in groups)
    print(f"\nFound {len(groups)} duplicate group(s) (Wasting {total_wasted / (1024 * 1024):.2f} MB):")
    for idx, g in enumerate(groups, 1):
        print(f"\nGroup #{idx} - Hash: {g.sha256[:16]}... ({g.size_bytes:,} bytes)")
        for f in g.files:
            print(f"  - {f}")
    return 0


def cmd_process(
    paths: List[str],
    target_dir: str,
    output_dir: str,
    config: AppConfig,
    taxonomy: Taxonomy,
) -> int:
    """Unified pipeline: Scan -> OCR analysis -> Classify -> Plan -> Generate Reports."""
    print("=== Step 1/4: Discovering & Extracting PDFs ===")
    scanner = PDFScanner(config.scanner)
    discovered = scanner.scan_many(paths)
    if not discovered:
        print("No PDF documents found.")
        return 0

    extractor = DocumentExtractor(config.ocr)
    documents = [extractor.process(p) for p in discovered]

    print("\n=== Step 2/4: Classifying Documents ===")
    from .classification.rule_based import RuleBasedClassifier
    classifier = RuleBasedClassifier(
        taxonomy=taxonomy,
        manual_review_threshold=config.classification.manual_review_threshold,
        unclassified_category=config.classification.default_unclassified_category,
    )
    classifications: Dict[str, Classification] = {}
    for doc in documents:
        classifications[str(doc.path)] = classifier.classify(doc)

    print(f"\n=== Step 3/4: Generating Relocation Plan targeting {target_dir} ===")
    planner = MovePlanner(target_base_dir=target_dir, safety_config=config.safety)
    pairs = [(d, classifications[str(d.path)]) for d in documents]
    plans = planner.plan_all(pairs)

    print("\n=== Step 4/4: Generating Reports & Identifying Duplicates ===")
    duplicates = DuplicateDetector().find_duplicates_from_documents(documents)
    generator = ReportGenerator(documents, classifications, plans, duplicates)
    rep_paths = generator.generate_all(output_dir)

    print(f"\nPipeline successfully completed! Reports generated in '{output_dir}':")
    print(f"  - Markdown: {rep_paths['md']}")
    print(f"  - JSON:     {rep_paths['json']}")
    print(f"  - CSV:      {rep_paths['csv']}")
    print("\nTo simulate changes without modifying files:")
    print(f"  pdf-organizer simulate {rep_paths['json']}")
    print("\nTo review classifications in detail:")
    print(f"  pdf-organizer review {rep_paths['json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
