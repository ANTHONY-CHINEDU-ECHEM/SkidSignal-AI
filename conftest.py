"""Shared fixtures. The end to end fixtures run the real pipeline on the bundled sample."""
from pathlib import Path

import pytest

from skidsignal.config import ROOT, load_settings
from skidsignal.engine import Engine
from skidsignal.index.store import build_index
from skidsignal.processing.pipeline import prepare
from skidsignal.processing.taxonomy import Taxonomy


@pytest.fixture(scope="session")
def taxonomy() -> Taxonomy:
    return Taxonomy(ROOT / "config" / "abs_taxonomy.yaml")


@pytest.fixture(scope="session")
def cfg(tmp_path_factory):
    work = tmp_path_factory.mktemp("skidsignal")
    return load_settings(overrides={
        "paths.raw": str(ROOT / "data" / "sample"), "paths.processed": str(work / "processed"),
        "paths.index": str(work / "index"), "paths.reports": str(work / "reports"),
        "paths.figures": str(work / "figures"), "retrieval.lsa_dim": 64, "llm.provider": "extractive",
    })


@pytest.fixture(scope="session")
def engine(cfg) -> Engine:
    prepare(cfg)
    build_index(cfg)
    return Engine(cfg)
