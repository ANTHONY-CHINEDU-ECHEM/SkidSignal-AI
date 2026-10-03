"""Monthly complaint panel and as of signal computation.

Everything is computed from a (vehicle x month) panel so that any historical date can
be replayed using only the complaints NHTSA had received by then. That property is
what makes the backtest honest.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from skidsignal.config import Settings
from skidsignal.signals.disproportionality import disproportionality
from skidsignal.signals.temporal import benjamini_hochberg, cusum, surge_test

TIERS = {0: "none", 1: "persistent", 2: "emerging"}


@dataclass
class Panel:
    vehicles: np.ndarray
    months: np.ndarray            # 'YYYY-MM' strings, contiguous
    total: np.ndarray             # all complaints, shape (vehicles, months)
    abs: np.ndarray               # ABS related complaints
    severe: np.ndarray            # ABS complaints with crash, fire, injury or death
    crash: np.ndarray
    fire: np.ndarray
    injured: np.ndarray
    deaths: np.ndarray
    last_complete: int            # index of the last fully observed month

    def index_of(self, vehicle: str) -> int:
        hits = np.flatnonzero(self.vehicles == vehicle.upper())
        if not len(hits):
            raise KeyError(f"vehicle not in panel: {vehicle}")
        return int(hits[0])

    def month_index(self, month: str) -> int:
        return int(np.flatnonzero(self.months == month)[0])


def build_panel(complaints: pd.DataFrame) -> Panel:
    df = complaints[complaints["prod_type"] == "V"]
    months = pd.period_range(df["received"].min(), df["received"].max(), freq="M").astype(str).to_numpy()
    month_pos = {m: i for i, m in enumerate(months)}
    vehicles, v_idx = np.unique(df["vehicle"].to_numpy(dtype=str), return_inverse=True)
    m_idx = df["month"].map(month_pos).to_numpy()
    shape = (len(vehicles), len(months))

    def grid(weights) -> np.ndarray:
        out = np.zeros(shape, dtype=np.int32)
        np.add.at(out, (v_idx, m_idx), np.asarray(weights, dtype=np.int32))
        return out

    is_abs = df["is_abs"].to_numpy(dtype=bool)
    last_day = df["received"].max()
    complete = len(months) - 1 if last_day.is_month_end else len(months) - 2
    return Panel(
        vehicles=vehicles, months=months, total=grid(np.ones(len(df))), abs=grid(is_abs),
        severe=grid(is_abs & df["severe"].to_numpy(dtype=bool)), crash=grid(is_abs & df["crash"].to_numpy(dtype=bool)),
        fire=grid(is_abs & df["fire"].to_numpy(dtype=bool)), injured=grid(is_abs * df["injured"].to_numpy()),
        deaths=grid(is_abs * df["deaths"].to_numpy()), last_complete=complete,
    )


def signals_as_of(panel: Panel, month_idx: int, cfg: Settings) -> pd.DataFrame:
    """Signal table for every vehicle using only data up to and including month_idx."""
    s = cfg.signals
    w0 = max(0, month_idx - s.window_months + 1)
    r0 = max(w0, month_idx - s.recent_months + 1)
    win = slice(w0, month_idx + 1)
    a, n = panel.abs[:, win].sum(axis=1), panel.total[:, win].sum(axis=1)
    A, N = float(a.sum()), float(n.sum())
    stats = disproportionality(a, n, A, N)

    recent = panel.abs[:, r0: month_idx + 1].sum(axis=1)
    baseline = panel.abs[:, w0:r0].sum(axis=1)
    base_months, recent_months = r0 - w0, month_idx + 1 - r0
    trend = 1.0
    if base_months > 0 and baseline.sum() > 0:
        trend = (recent.sum() / recent_months) / (baseline.sum() / base_months)
    surge = surge_test(recent, baseline, recent_months, base_months, trend)

    candidate = a >= s.min_cases
    q = np.ones(len(a))
    if candidate.any():
        q[candidate] = benjamini_hochberg(surge["p"][candidate])
    path = cusum(panel.abs[:, win], base_months, s.cusum_k)
    cusum_peak = path[:, base_months:].max(axis=1) if base_months < path.shape[1] else np.zeros(len(a))

    with np.errstate(invalid="ignore"):
        disproportionate = (
            candidate & (stats["prr"] >= s.prr_threshold) & (stats["chi2"] >= s.chi2_threshold)
            & (stats["ic025"] > s.ic025_threshold)
        )
    # Two independent channels. Requiring both would hide families whose ABS problem is
    # masked by a larger unrelated problem (see docs/EVALUATION.md, design iteration log).
    emerging = (recent >= s.min_recent_cases) & (q < s.surge_fdr)
    tier = np.where(emerging, 2, np.where(disproportionate, 1, 0))

    severe = panel.severe[:, win].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        severe_share = np.where(a > 0, severe / a, 0.0)
    w = s.score_weights
    score = 100 * (
        w.disproportionality * np.clip(np.nan_to_num(stats["ic025"], nan=0.0, neginf=0.0) / 3.0, 0, 1)
        + w.surge * np.clip(-np.log10(np.maximum(q, 1e-12)) / 6.0, 0, 1)
        + w.severity * np.clip(severe_share / 0.25, 0, 1)
        + w.volume * np.clip(np.log1p(a) / np.log1p(500), 0, 1)
    )
    table = pd.DataFrame(
        {
            "vehicle": panel.vehicles, "as_of": panel.months[month_idx], "window_start": panel.months[w0],
            "abs_complaints": a, "all_complaints": n, "abs_share": np.where(n > 0, a / np.maximum(n, 1), 0.0),
            "expected": stats["expected"], "prr": stats["prr"], "prr_lo": stats["prr_lo"], "prr_hi": stats["prr_hi"],
            "chi2": stats["chi2"], "ror": stats["ror"], "ror_lo": stats["ror_lo"], "ror_hi": stats["ror_hi"],
            "ic": stats["ic"], "ic025": stats["ic025"], "ic975": stats["ic975"],
            "recent_abs": recent, "expected_recent": surge["expected_recent"], "rate_ratio": surge["rate_ratio"],
            "surge_p": surge["p"], "surge_q": q, "cusum_peak": cusum_peak, "cusum_alarm": cusum_peak > s.cusum_h,
            "severe": severe, "crash": panel.crash[:, win].sum(axis=1), "fire": panel.fire[:, win].sum(axis=1),
            "injured": panel.injured[:, win].sum(axis=1), "deaths": panel.deaths[:, win].sum(axis=1),
            "severe_share": severe_share, "disproportionate": disproportionate, "surging": emerging,
            "tier_code": tier, "tier": [TIERS[t] for t in tier], "score": np.where(candidate, score, 0.0),
        }
    )
    table.attrs.update({"database_abs": A, "database_total": N, "trend": trend})
    return table


def latest_signals(panel: Panel, cfg: Settings) -> pd.DataFrame:
    table = signals_as_of(panel, panel.last_complete, cfg)
    flagged = table[table["tier_code"] > 0].sort_values("score", ascending=False).reset_index(drop=True)
    flagged.insert(0, "rank", np.arange(1, len(flagged) + 1))
    return flagged
