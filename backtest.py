"""Retrospective backtest: replay every month and compare alerts with ABS recalls.

For each month the detector sees only complaints received up to that month. An alert
is the first month a vehicle family reaches the persistent or emerging tier. Alerts are
then compared with ABS related vehicle recall campaigns:

  * sensitivity and lead time: for each recall, was any affected vehicle family already
    on alert before the recall was filed, and how many months earlier?
  * alert outcomes: of the alerts raised, how many were followed by an ABS recall inside
    the horizon, how many concern a vehicle that already had an ABS recall, and how many
    have no ABS recall on file. The last group is not a false alarm count. It is the
    analyst work queue, and it includes vehicles with real problems and no recall.

Each detector channel is scored separately, and a naive volume rule (N or more ABS
complaints in the recent window) is replayed at several thresholds as a comparator.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from skidsignal.config import Settings, get_logger
from skidsignal.signals.detector import Panel, signals_as_of

log = get_logger(__name__)


def replay(panel: Panel, cfg: Settings) -> dict[str, np.ndarray]:
    """Tier, channel flags, score and recent count for every vehicle and month."""
    shape = panel.abs.shape
    tiers, scores = np.zeros(shape, np.int8), np.zeros(shape, np.float32)
    disp, surge, recent = np.zeros(shape, bool), np.zeros(shape, bool), np.zeros(shape, np.int32)
    start = cfg.signals.min_history_months - 1
    for m in range(start, panel.last_complete + 1):
        table = signals_as_of(panel, m, cfg)
        tiers[:, m] = table["tier_code"].to_numpy()
        scores[:, m] = table["score"].to_numpy()
        disp[:, m] = table["disproportionate"].to_numpy()
        surge[:, m] = table["surging"].to_numpy()
        recent[:, m] = table["recent_abs"].to_numpy()
    return {"tiers": tiers, "scores": scores, "disproportionate": disp, "surging": surge, "recent": recent, "start": start}


def _first_true(state: np.ndarray) -> np.ndarray:
    """Index of the first True per row, or a large sentinel when there is none."""
    first = state.argmax(axis=1)
    return np.where(state.any(axis=1), first, 10**6)


def run_backtest(panel: Panel, campaigns: pd.DataFrame, vehicles: pd.DataFrame, cfg: Settings) -> dict:
    history = replay(panel, cfg)
    live = np.zeros(panel.abs.shape[1], bool)
    live[history["start"]: panel.last_complete + 1] = True
    rules = {
        "skidsignal": history["tiers"] > 0,
        "surge_channel": history["surging"],
        "disproportionality_channel": history["disproportionate"],
    }
    for threshold in cfg.signals.baseline_volume_thresholds:
        rules[f"volume_rule_{threshold}"] = (history["recent"] >= threshold) & live
    first_alert = {name: _first_true(state) for name, state in rules.items()}
    v_pos = {v: i for i, v in enumerate(panel.vehicles)}
    month_pos = {m: i for i, m in enumerate(panel.months)}
    horizon = cfg.backtest.recall_horizon_months

    recalls = campaigns[campaigns["is_abs"] & (campaigns["rtype"] == "V")].copy()
    recalls["month"] = recalls["date"].dt.to_period("M").astype(str)
    link = vehicles[vehicles["campno"].isin(recalls["campno"])]
    families = link.groupby("campno")["vehicle"].agg(lambda s: sorted(set(s)))

    # recall months per vehicle, for alert outcome classification
    recall_months: dict[int, list[int]] = {}
    rows = []
    for c in recalls.itertuples():
        idx = [v_pos[v] for v in families.get(c.campno, []) if v in v_pos]
        r_month = month_pos.get(c.month)
        if r_month is None:
            continue
        for i in idx:
            recall_months.setdefault(i, []).append(r_month)
        row = {
            "campno": c.campno, "recall_month": c.month, "date_is_exact": bool(c.date_is_exact), "makes": c.makes,
            "families_in_panel": len(idx), "abs_complaints_before": int(panel.abs[idx, :r_month].sum()) if idx else 0,
        }
        for name in rules:
            alerts = [first_alert[name][i] for i in idx if first_alert[name][i] < r_month]
            row[f"{name}_detected"] = bool(alerts)
            row[f"{name}_lead_months"] = int(r_month - min(alerts)) if alerts else np.nan
        rows.append(row)
    recall_table = pd.DataFrame(rows)

    evaluated = recall_table[
        (recall_table["recall_month"] >= cfg.backtest.evaluate_recalls_from[:7]) & (recall_table["families_in_panel"] > 0)
    ]
    detectable = evaluated[evaluated["abs_complaints_before"] >= cfg.signals.min_cases]

    def sensitivity(frame: pd.DataFrame, name: str) -> dict:
        if frame.empty:
            return {"recalls": 0, "detected": 0, "sensitivity": None, "median_lead_months": None}
        lead = frame.loc[frame[f"{name}_detected"], f"{name}_lead_months"]
        return {
            "recalls": int(len(frame)), "detected": int(frame[f"{name}_detected"].sum()),
            "sensitivity": round(float(frame[f"{name}_detected"].mean()), 3),
            "median_lead_months": float(lead.median()) if len(lead) else None,
        }

    last_recall_month = month_pos[recalls["month"].max()] if len(recalls) else 0
    alert_rows, summary = [], {}
    for name, state in rules.items():
        outcomes = {"recall_followed": 0, "prior_recall": 0, "no_abs_recall_on_file": 0}
        observable = dict(outcomes)
        for i in np.flatnonzero(first_alert[name] < 10**6):
            t = int(first_alert[name][i])
            months = recall_months.get(i, [])
            if any(t < r <= t + horizon for r in months):
                outcome = "recall_followed"
            elif any(r <= t for r in months):
                outcome = "prior_recall"
            else:
                outcome = "no_abs_recall_on_file"
            outcomes[outcome] += 1
            full_horizon = t + horizon <= last_recall_month
            if full_horizon:
                observable[outcome] += 1
            alert_rows.append({"rule": name, "vehicle": panel.vehicles[i], "first_alert_month": panel.months[t],
                               "outcome": outcome, "full_horizon_observed": full_horizon})
        active = state[:, history["start"]: panel.last_complete + 1]
        months_replayed = active.shape[1]
        summary[name] = {
            "all_abs_recalls": sensitivity(evaluated, name),
            "detectable_abs_recalls": sensitivity(detectable, name),
            "vehicles_ever_alerted": int((first_alert[name] < 10**6).sum()),
            "new_alerts_per_month": round(float((first_alert[name] < 10**6).sum() / months_replayed), 2),
            "mean_active_alerts_per_month": round(float(active.sum(axis=0).mean()), 1),
            "alert_outcomes_all": outcomes,
            "alert_outcomes_full_horizon": observable,
        }

    report = {
        "months_replayed": [str(panel.months[history["start"]]), str(panel.months[panel.last_complete])],
        "recall_file_ends": str(recalls["month"].max()) if len(recalls) else None,
        "recall_dates_exact": bool(recalls["date_is_exact"].all()) if len(recalls) else None,
        "abs_vehicle_recalls_total": int(len(recall_table)),
        "abs_vehicle_recalls_evaluated": int(len(evaluated)),
        "abs_vehicle_recalls_detectable": int(len(detectable)),
        "horizon_months": horizon,
        "rules": summary,
    }
    reports = cfg.path("reports")
    recall_table.to_csv(reports / "backtest_recalls.csv", index=False)
    pd.DataFrame(alert_rows).to_csv(reports / "backtest_alerts.csv", index=False)
    (reports / "backtest_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    np.savez_compressed(cfg.path("processed") / "replay.npz", tiers=history["tiers"], scores=history["scores"],
                        vehicles=panel.vehicles, months=panel.months)
    return report
