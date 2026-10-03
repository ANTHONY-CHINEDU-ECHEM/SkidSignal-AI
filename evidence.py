"""Evidence pack: everything a brief is allowed to say, assembled before any text is written.

The pack separates two kinds of grounding. Facts are numbers computed by the signal
engine and rendered here as strings, so a language model never has to do arithmetic.
Items are retrieved records, each with a citation key. Retrieval is filtered to the as
of date, so a historical brief cannot quote a complaint or recall from its own future.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from skidsignal.analysis.failure_modes import failure_mode_profile, model_year_distribution, window_slice
from skidsignal.config import Settings
from skidsignal.index.store import HybridIndex
from skidsignal.processing.taxonomy import Taxonomy
from skidsignal.signals.detector import Panel, signals_as_of

LIMITS_NOTE = "K:surveillance_methods.known_limits_of_complaint_based_surveillance"


@dataclass
class EvidenceItem:
    cite: str
    source: str
    title: str
    text: str
    date: str | None = None
    role: str = "retrieved"


@dataclass
class EvidencePack:
    vehicle: str
    as_of: str
    tier: str
    facts: dict
    fact_lines: list[str]
    failure_modes: list[dict]
    model_years: list[tuple[int, int]]
    monthly: list[tuple[str, int]]
    items: list[EvidenceItem] = field(default_factory=list)

    def cites(self) -> set[str]:
        return {item.cite for item in self.items} | {"S"}

    def by_source(self, source: str) -> list[EvidenceItem]:
        return [item for item in self.items if item.source == source]

    def to_dict(self) -> dict:
        return asdict(self)


def snippet(text: str, limit: int = 420) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " ..."


def _f(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def build_evidence_pack(
    vehicle: str, panel: Panel, month_idx: int, brake: pd.DataFrame, campaigns: pd.DataFrame,
    recall_vehicles: pd.DataFrame, taxonomy: Taxonomy, index: HybridIndex, cfg: Settings,
) -> EvidencePack:
    vehicle = vehicle.upper()
    table = signals_as_of(panel, month_idx, cfg)
    row = table[table["vehicle"] == vehicle]
    if row.empty:
        raise KeyError(f"vehicle not in panel: {vehicle}")
    r = row.iloc[0]
    flagged = table[table["tier_code"] > 0].sort_values("score", ascending=False)["vehicle"].tolist()
    rank = flagged.index(vehicle) + 1 if vehicle in flagged else None
    as_of, start = str(r["as_of"]), str(r["window_start"])
    as_of_end = pd.Period(as_of, freq="M").end_time
    db_share = table.attrs["database_abs"] / table.attrs["database_total"]

    rows = window_slice(brake, vehicle, start, as_of)
    modes = failure_mode_profile(rows, taxonomy)
    modes = modes[modes["count"] > 0]
    years = model_year_distribution(rows)
    v = panel.index_of(vehicle)
    w0 = panel.month_index(start)
    monthly = [(str(m), int(n)) for m, n in zip(panel.months[w0: month_idx + 1], panel.abs[v, w0: month_idx + 1])]

    s = cfg.signals
    facts = {
        "vehicle": vehicle, "as_of": as_of, "window_start": start, "window_months": month_idx - w0 + 1,
        "recent_months": min(s.recent_months, month_idx - w0 + 1), "tier": r["tier"], "score": _f(r["score"], 1),
        "rank": rank, "flagged_total": len(flagged), "abs_complaints": int(r["abs_complaints"]),
        "all_complaints": int(r["all_complaints"]), "abs_share_pct": _f(100 * r["abs_share"], 1),
        "database_share_pct": _f(100 * db_share, 1), "expected": _f(r["expected"], 1), "prr": _f(r["prr"]),
        "prr_lo": _f(r["prr_lo"]), "prr_hi": _f(r["prr_hi"]), "ror": _f(r["ror"]), "ror_lo": _f(r["ror_lo"]),
        "ror_hi": _f(r["ror_hi"]), "chi2": _f(r["chi2"], 1), "ic": _f(r["ic"]), "ic025": _f(r["ic025"]),
        "ic975": _f(r["ic975"]), "recent_abs": int(r["recent_abs"]), "expected_recent": _f(r["expected_recent"], 1),
        "rate_ratio": _f(r["rate_ratio"]), "surge_q": f"{r['surge_q']:.4f}", "cusum_peak": _f(r["cusum_peak"], 1),
        "cusum_alarm": bool(r["cusum_alarm"]), "disproportionate": bool(r["disproportionate"]),
        "surging": bool(r["surging"]), "severe": int(r["severe"]), "crash": int(r["crash"]), "fire": int(r["fire"]),
        "injured": int(r["injured"]), "deaths": int(r["deaths"]), "severe_share_pct": _f(100 * r["severe_share"], 1),
    }
    fact_lines = [
        f"Vehicle family {vehicle}, as of {as_of}, window {start} to {as_of} ({facts['window_months']} months).",
        f"Tier {facts['tier']}, priority score {facts['score']}" + (f", rank {rank} of {len(flagged)} flagged families." if rank else "."),
        f"ABS related complaints in window: {facts['abs_complaints']:,} of {facts['all_complaints']:,} complaints ({facts['abs_share_pct']} percent). Database wide share: {facts['database_share_pct']} percent. Expected count: {facts['expected']}.",
        f"PRR {facts['prr']} (95 percent interval {facts['prr_lo']} to {facts['prr_hi']}); ROR {facts['ror']} ({facts['ror_lo']} to {facts['ror_hi']}); chi square {facts['chi2']}.",
        f"Information component {facts['ic']} (IC025 {facts['ic025']}, IC975 {facts['ic975']}).",
        f"Recent {facts['recent_months']} months: {facts['recent_abs']} ABS complaints against {facts['expected_recent']} expected (rate ratio {facts['rate_ratio']}, adjusted q {facts['surge_q']}). CUSUM peak {facts['cusum_peak']}, alarm {facts['cusum_alarm']}.",
        f"Severity among ABS complaints: {facts['severe']} with crash, fire, injury or death ({facts['severe_share_pct']} percent); {facts['crash']} crash, {facts['fire']} fire, {facts['injured']} injured, {facts['deaths']} deaths.",
        "Failure modes: " + "; ".join(f"{m.label} {m.count} ({100 * m.share:.1f} percent)" for m in modes.itertuples()) + ".",
        "Model years with most ABS complaints: " + ", ".join(f"{y} ({n})" for y, n in years) + ".",
    ]

    pack = EvidencePack(vehicle, as_of, facts["tier"], facts, fact_lines, modes.to_dict("records"), years, monthly)
    top_labels = " ".join(modes["label"].head(3))
    query = f"{vehicle} antilock brake ABS {top_labels}"
    make = vehicle.split(" ")[0]
    window_start = pd.Period(start, freq="M").start_time
    seen: set[str] = set()

    def add(cite, source, title, text, date, role):
        if cite not in seen:
            seen.add(cite)
            pack.items.append(EvidenceItem(cite, source, title, snippet(text), date, role))

    for hit in index.search(query, k=6, sources=["complaint"], vehicle=vehicle, date_from=window_start,
                            date_to=as_of_end, abs_only=True):
        add(hit.doc_id, "complaint", hit.title, hit.text, hit.date, "retrieved")
    for c in rows[rows["severe"]].sort_values("received", ascending=False).head(2).itertuples():
        year = "" if pd.isna(c.model_year) else int(c.model_year)
        add(f"C:{c.complaint_id}", "complaint", f"{year} {c.vehicle} | {c.components[:120]}".strip(), c.narrative,
            str(c.received.date()), "severe outcome")

    linked = recall_vehicles.loc[recall_vehicles["vehicle"] == vehicle, "campno"].unique()
    known = campaigns[campaigns["campno"].isin(linked) & campaigns["is_abs"] & (campaigns["date"] <= as_of_end)]
    for c in known.sort_values("date", ascending=False).head(3).itertuples():
        add(f"R:{c.campno}", "recall", f"Recall {c.campno} | {c.makes}", c.text, str(c.date.date()), "recall for this family")
    facts["known_abs_recalls"] = [f"{c.campno}" for c in known.sort_values("date").itertuples()]
    fact_lines.append(
        "ABS related recall campaigns on file for this family before the as of date: "
        + (", ".join(facts["known_abs_recalls"]) if len(known) else "none") + "."
    )
    for hit in index.search(query, k=3, sources=["recall"], make=make, brake_only=True, date_to=as_of_end):
        add(hit.doc_id, "recall", hit.title, hit.text, hit.date, "related recall, same make")
    for hit in index.search(top_labels or "antilock brake failure", k=2, sources=["reference"], diversify=False):
        add(hit.doc_id, "reference", hit.title, hit.text, None, "reference note")
    limits = index.get_document(LIMITS_NOTE)
    if limits:
        add(LIMITS_NOTE, "reference", limits["title"], limits["text"], None, "reference note")
    return pack
