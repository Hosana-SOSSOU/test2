"""
Configuration loading and dataclasses for PDF Organizer.
Supports PyYAML when available, with a resilient fallback parser.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


def load_yaml_file(path: Path | str) -> Dict[str, Any]:
    """
    Safely load a YAML or JSON file.
    Prefers PyYAML if available; falls back to a clean line-based YAML parser.
    """
    file_path = Path(path)
    if not file_path.exists():
        return {}

    content = file_path.read_text(encoding="utf-8")

    # Attempt standard PyYAML
    try:
        import yaml  # type: ignore
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except ImportError:
        pass

    # Simple fallback parser for key: value and indented blocks
    return _simple_yaml_parse(content)


def _simple_yaml_parse(content: str) -> Dict[str, Any]:
    """Lightweight fallback parser for basic YAML structures."""
    root: Dict[str, Any] = {}
    lines = content.splitlines()
    stack: list[tuple[int, dict]] = [(-1, root)]
    current_list_key: Optional[str] = None
    current_list_owner: Optional[dict] = None

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))

        # Check list item
        if stripped.startswith("- "):
            val = stripped[2:].strip().strip("\"'")
            if current_list_owner is not None and current_list_key is not None:
                current_list_owner.setdefault(current_list_key, []).append(val)
            continue

        current_list_key = None
        current_list_owner = None

        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip().strip("\"'")
            val = val.strip()

            # Discard inline comments
            if " #" in val:
                val = val.split(" #")[0].strip()

            parsed_val: Any = val
            if val == "" or val == "{}":
                parsed_val = {}
            elif val.lower() == "true":
                parsed_val = True
            elif val.lower() == "false":
                parsed_val = False
            elif val.lower() in ("null", "none"):
                parsed_val = None
            elif val.isdigit():
                parsed_val = int(val)
            else:
                try:
                    parsed_val = float(val)
                except ValueError:
                    parsed_val = val.strip("\"'")

            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()

            parent = stack[-1][1]
            if isinstance(parsed_val, dict):
                parent[key] = {}
                stack.append((indent, parent[key]))
            elif val == "":
                # Could be parent of dict or list
                parent[key] = {}
                stack.append((indent, parent[key]))
                current_list_key = key
                current_list_owner = parent
            else:
                parent[key] = parsed_val

    return root


@dataclass(slots=True)
class ScannerConfig:
    follow_symlinks: bool = False
    min_file_size_bytes: int = 100
    recursive: bool = True


@dataclass(slots=True)
class OCRConfig:
    enabled: bool = True
    backend: str = "tesseract"
    min_text_len_per_page: int = 30
    lang: str = "fra+eng"
    tesseract_cmd: str = "tesseract"
    cache_dir: str = ".pdf_organizer_cache/ocr"


@dataclass(slots=True)
class LLMConfig:
    enabled: bool = False
    backend: str = "ollama"
    model: str = "llama3.2"
    endpoint: str = "http://127.0.0.1:11434"
    timeout_seconds: int = 30
    fallback_to_rule_based: bool = True


@dataclass(slots=True)
class ClassificationConfig:
    backend: str = "rule_based"
    manual_review_threshold: float = 0.50
    default_unclassified_category: str = "À_classer"
    taxonomy_path: str = "config/taxonomy.yaml"


@dataclass(slots=True)
class SafetyConfig:
    overwrite: bool = False
    require_confirmation: bool = True
    collision_strategy: str = "RENAME"  # "RENAME", "SKIP", "REVIEW"
    destination_base_dir: Optional[str] = None


@dataclass(slots=True)
class AppConfig:
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)

    @classmethod
    def load(cls, config_path: Optional[Path | str] = None) -> AppConfig:
        """Load configuration from YAML file or return defaults."""
        data: Dict[str, Any] = {}
        if config_path:
            p = Path(config_path)
            if p.exists():
                data = load_yaml_file(p)
        else:
            default_p = Path("config/config.yaml")
            if default_p.exists():
                data = load_yaml_file(default_p)

        c_data = data.get("classification", {})
        o_data = data.get("ocr", {})
        l_data = data.get("llm", {})
        s_data = data.get("scanner", {})
        safe_data = data.get("safety", {})

        return cls(
            classification=ClassificationConfig(
                backend=c_data.get("backend", "rule_based"),
                manual_review_threshold=float(c_data.get("manual_review_threshold", 0.50)),
                default_unclassified_category=c_data.get("default_unclassified_category", "À_classer"),
                taxonomy_path=c_data.get("taxonomy_path", "config/taxonomy.yaml"),
            ),
            ocr=OCRConfig(
                enabled=bool(o_data.get("enabled", True)),
                backend=o_data.get("backend", "tesseract"),
                min_text_len_per_page=int(o_data.get("min_text_len_per_page", 30)),
                lang=o_data.get("lang", "fra+eng"),
                tesseract_cmd=o_data.get("tesseract_cmd", "tesseract"),
                cache_dir=o_data.get("cache_dir", ".pdf_organizer_cache/ocr"),
            ),
            llm=LLMConfig(
                enabled=bool(l_data.get("enabled", False)),
                backend=l_data.get("backend", "ollama"),
                model=l_data.get("model", "llama3.2"),
                endpoint=l_data.get("endpoint", "http://127.0.0.1:11434"),
                timeout_seconds=int(l_data.get("timeout_seconds", 30)),
                fallback_to_rule_based=bool(l_data.get("fallback_to_rule_based", True)),
            ),
            scanner=ScannerConfig(
                follow_symlinks=bool(s_data.get("follow_symlinks", False)),
                min_file_size_bytes=int(s_data.get("min_file_size_bytes", 100)),
                recursive=bool(s_data.get("recursive", True)),
            ),
            safety=SafetyConfig(
                overwrite=bool(safe_data.get("overwrite", False)),
                require_confirmation=bool(safe_data.get("require_confirmation", True)),
                collision_strategy=safe_data.get("collision_strategy", "RENAME"),
                destination_base_dir=safe_data.get("destination_base_dir"),
            ),
        )
