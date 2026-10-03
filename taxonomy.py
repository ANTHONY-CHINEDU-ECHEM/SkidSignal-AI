"""ABS lexicon and failure mode tagger driven by config/abs_taxonomy.yaml."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import yaml


def _non_capturing(pattern: str) -> str:
    return re.sub(r"\((?!\?)", "(?:", pattern)


def _union(patterns: list[str]) -> str:
    return "|".join(f"(?:{_non_capturing(p)})" for p in patterns)


class Taxonomy:
    def __init__(self, path: str | Path):
        spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        self.abs_core = _union(spec["abs_core_patterns"])
        self.abs_component = _union(spec["abs_component_patterns"])
        self.brake_component = _union(spec["brake_domain_component_patterns"])
        self.failure_modes = {name: _union(fm["patterns"]) for name, fm in spec["failure_modes"].items()}
        self.labels = {name: fm["label"] for name, fm in spec["failure_modes"].items()}
        self._abs_re = re.compile(self.abs_core, re.IGNORECASE)

    @staticmethod
    def _contains(series: pd.Series, pattern: str) -> pd.Series:
        return series.fillna("").astype(str).str.contains(pattern, case=False, regex=True, na=False).astype(bool)

    def is_abs_text(self, text: pd.Series) -> pd.Series:
        return self._contains(text, self.abs_core)

    def is_abs_component(self, components: pd.Series) -> pd.Series:
        return self._contains(components, self.abs_component)

    def is_brake_component(self, components: pd.Series) -> pd.Series:
        return self._contains(components, self.brake_component)

    def tag_failure_modes(self, text: pd.Series) -> pd.DataFrame:
        return pd.DataFrame({f"fm_{name}": self._contains(text, pat) for name, pat in self.failure_modes.items()})

    def mentions_abs(self, text: str) -> bool:
        return bool(self._abs_re.search(text or ""))

    @property
    def fm_columns(self) -> list[str]:
        return [f"fm_{name}" for name in self.failure_modes]
