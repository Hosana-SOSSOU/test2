"""
Taxonomy parsing and category resolution.
Dynamically handles nested taxonomy hierarchies and associated keywords.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from .config import load_yaml_file


class Taxonomy:
    """Manages hierarchical document categories and keywords."""

    def __init__(self, raw_data: Dict[str, Any]) -> None:
        self.raw_data = raw_data
        self.categories: List[str] = []
        self.category_keywords: Dict[str, List[str]] = {}
        self._build_tree("", self.raw_data)

        # Always ensure 'À_classer' exists
        if "À_classer" not in self.categories:
            self.categories.append("À_classer")
            self.category_keywords["À_classer"] = []

    def _build_tree(self, prefix: str, current: Any) -> None:
        if not isinstance(current, dict):
            return

        # If current has a 'keywords' key, it's a leaf node with keywords
        keywords: List[str] = []
        if "keywords" in current and isinstance(current["keywords"], list):
            keywords = [str(k).lower().strip() for k in current["keywords"] if k]

        # Check subcategories (keys that are not "keywords")
        subkeys = [k for k in current.keys() if k != "keywords"]

        if not subkeys and prefix:
            # Leaf category
            self.categories.append(prefix)
            self.category_keywords[prefix] = keywords
            return

        for k, v in current.items():
            if k == "keywords":
                continue
            child_prefix = f"{prefix}/{k}" if prefix else k
            if isinstance(v, dict):
                has_nested_cats = any(sk != "keywords" for sk in v.keys())
                if has_nested_cats:
                    self._build_tree(child_prefix, v)
                else:
                    leaf_kws = []
                    if "keywords" in v and isinstance(v["keywords"], list):
                        leaf_kws = [str(kw).lower().strip() for kw in v["keywords"] if kw]
                    self.categories.append(child_prefix)
                    self.category_keywords[child_prefix] = leaf_kws
            else:
                self.categories.append(child_prefix)
                self.category_keywords[child_prefix] = []

    @classmethod
    def load(cls, path: Path | str = "config/taxonomy.yaml") -> Taxonomy:
        """Load taxonomy from YAML file."""
        data = load_yaml_file(path)
        return cls(data)

    def is_valid_category(self, category: str) -> bool:
        """Check if category exists in taxonomy."""
        return category in self.categories

    def get_all_categories(self) -> List[str]:
        """Return all flattened category paths."""
        return list(self.categories)

    def get_keywords_for_category(self, category: str) -> List[str]:
        """Return keyword list for a category."""
        return self.category_keywords.get(category, [])
