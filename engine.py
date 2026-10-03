"""One object that loads every artefact once and serves the CLI, the API and the dashboard."""
from __future__ import annotations

from functools import cached_property

import pandas as pd

from skidsignal.config import Settings, load_settings
from skidsignal.index.store import HybridIndex, load_index
from skidsignal.processing.taxonomy import Taxonomy
from skidsignal.rag.brief import Brief, generate_brief
from skidsignal.rag.evidence import build_evidence_pack
from skidsignal.rag.llm import make_writer
from skidsignal.rag.qa import answer_question
from skidsignal.signals.detector import Panel, build_panel, signals_as_of


class Engine:
    def __init__(self, cfg: Settings | None = None):
        self.cfg = cfg or load_settings()
        self._dir = self.cfg.path("processed")

    @cached_property
    def taxonomy(self) -> Taxonomy:
        return Taxonomy(self.cfg.path("taxonomy"))

    @cached_property
    def complaints(self) -> pd.DataFrame:
        return pd.read_parquet(self._dir / "complaints.parquet")

    @cached_property
    def brake(self) -> pd.DataFrame:
        return pd.read_parquet(self._dir / "brake_complaints.parquet")

    @cached_property
    def campaigns(self) -> pd.DataFrame:
        path = self._dir / "recall_campaigns.parquet"
        if path.exists():
            return pd.read_parquet(path)
        return pd.DataFrame(columns=["campno", "is_abs", "is_brake_domain", "date", "makes", "text", "rtype", "date_is_exact"])

    @cached_property
    def recall_vehicles(self) -> pd.DataFrame:
        path = self._dir / "recall_vehicles.parquet"
        return pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=["campno", "make", "model", "model_year", "vehicle"])

    @cached_property
    def panel(self) -> Panel:
        return build_panel(self.complaints)

    @cached_property
    def index(self) -> HybridIndex:
        return load_index(self.cfg)

    @cached_property
    def llm(self):
        return make_writer(self.cfg)

    def month_index(self, as_of: str | None) -> int:
        return self.panel.last_complete if as_of is None else self.panel.month_index(as_of)

    def signals(self, as_of: str | None = None, flagged_only: bool = True) -> pd.DataFrame:
        table = signals_as_of(self.panel, self.month_index(as_of), self.cfg)
        if flagged_only:
            table = table[table["tier_code"] > 0]
        table = table.sort_values("score", ascending=False).reset_index(drop=True)
        table.insert(0, "rank", range(1, len(table) + 1))
        return table

    def brief(self, vehicle: str, as_of: str | None = None, use_llm: bool = True) -> Brief:
        pack = build_evidence_pack(vehicle, self.panel, self.month_index(as_of), self.brake, self.campaigns,
                                   self.recall_vehicles, self.taxonomy, self.index, self.cfg)
        return generate_brief(pack, self.cfg, self.llm if use_llm else None)

    def ask(self, question: str, **filters) -> dict:
        return answer_question(self.index, question, self.cfg, self.llm, **filters)
