"""Settings loader. One YAML file drives every threshold in the pipeline."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("SKIDSIGNAL_HOME", Path(__file__).resolve().parents[2]))
DEFAULT_CONFIG = ROOT / "config" / "settings.yaml"


class Settings(dict):
    """Dictionary with attribute access, so `cfg.signals.min_cases` reads naturally."""

    def __getattr__(self, key: str) -> Any:
        try:
            value = self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc
        return Settings(value) if isinstance(value, dict) else value

    def path(self, name: str) -> Path:
        """Resolve a configured path against the project root and create directories."""
        p = Path(self["paths"][name])
        p = p if p.is_absolute() else ROOT / p
        if not p.suffix:
            p.mkdir(parents=True, exist_ok=True)
        return p


def load_settings(path: str | Path | None = None, overrides: dict | None = None) -> Settings:
    path = Path(path or os.environ.get("SKIDSIGNAL_CONFIG", DEFAULT_CONFIG))
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    for dotted, value in (overrides or {}).items():
        node = data
        *parents, leaf = dotted.split(".")
        for key in parents:
            node = node.setdefault(key, {})
        node[leaf] = value
    return Settings(data)


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=os.environ.get("SKIDSIGNAL_LOG", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)
