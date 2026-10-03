"""Figures for the documentation. Every chart is drawn from pipeline outputs on disk."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from skidsignal.analysis.failure_modes import failure_mode_matrix
from skidsignal.config import Settings, get_logger
from skidsignal.engine import Engine
from skidsignal.signals.detector import signals_as_of

log = get_logger(__name__)
INK, GRID, BLUE, AMBER, RED, TEAL, GREY = "#1f2933", "#d9dee4", "#2f6f9f", "#d98e04", "#c0392b", "#1b8a7a", "#8a94a0"
TIER_COLOUR = {"emerging": RED, "persistent": BLUE, "none": GREY}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK,
    "xtick.color": INK, "ytick.color": INK, "axes.titleweight": "bold", "axes.titlesize": 12,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "figure.dpi": 150, "savefig.bbox": "tight", "savefig.facecolor": "white",
})


SHORT_MODE = {
    "warning_lamp": "Warning\nlamp", "module_or_hydraulic_unit": "Module or\nhydraulic unit", "wheel_speed_sensor": "Wheel speed\nsensor",
    "unintended_activation": "Unintended\nactivation", "loss_of_braking": "Loss of\nbraking", "thermal_event": "Fire or\noverheating",
    "electrical_or_software": "Electrical or\nsoftware", "stability_traction_coupling": "Stability or\ntraction", "remedy_unavailable": "Part\nunavailable",
}


def _save(fig, cfg: Settings, name: str) -> None:
    path = cfg.path("figures") / name
    fig.savefig(path)
    plt.close(fig)
    log.info("wrote %s", path)


def fig_architecture(cfg: Settings) -> None:
    fig, ax = plt.subplots(figsize=(12, 6.6))
    ax.set_xlim(0, 12); ax.set_ylim(0, 6.6); ax.axis("off")

    def box(x, y, w, h, title, body, colour):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.08", fc=colour, ec=INK, lw=1))
        ax.text(x + w / 2, y + h - 0.24, title, ha="center", va="top", fontsize=9.5, fontweight="bold", color=INK)
        ax.text(x + w / 2, y + h - 0.56, body, ha="center", va="top", fontsize=8, color=INK, linespacing=1.35)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12, color=INK, lw=1))

    sources = [("Owner complaints", "NHTSA ODI flat files\n545k component rows"), ("Recall documents", "216k rows\n3,574 campaigns"),
               ("Investigations and\nbulletins", "optional sources"), ("Reference notes", "ABS engineering,\nregulation, methods")]
    for i, (title, body) in enumerate(sources):
        box(0.2 + i * 2.95, 5.35, 2.7, 1.05, title, body if "\n" not in title else "\n" + body, "#eef3f8")
    box(0.2, 3.85, 11.55, 0.95, "Ingestion and normalisation",
        "positional parsers, one row per complaint, duplicate removal, ABS lexicon and failure mode tagging, campaign roll up", "#f6f1e6")
    box(0.2, 2.25, 5.6, 1.1, "Signal engine", "vehicle by month panel, PRR, ROR, information component,\nPoisson surge test with FDR control, CUSUM, priority score", "#e9f5f2")
    box(6.15, 2.25, 5.6, 1.1, "Retrieval index", "51k chunks, BM25 plus dense vectors, rank fusion,\nfilters by source, make, family and date, MMR diversity", "#e9f5f2")
    stages = [("Evidence pack", "facts as strings,\nrecords filtered\nto the as of date"), ("Writer", "extractive, or a\nlanguage model\nwith strict prompt"),
              ("Guardrails", "citations, coverage,\nnumbers, calibrated\nlanguage"), ("Outputs", "analyst brief,\nAPI, command line")]
    for i, (title, body) in enumerate(stages):
        box(0.2 + i * 2.95, 0.55, 2.7, 1.2, title, body, "#fbeeee" if i == 2 else "#eef3f8")
        if i:
            arrow(0.2 + i * 2.95 - 0.25, 1.15, 0.2 + i * 2.95, 1.15)
    for x in (1.55, 4.5, 7.45, 10.4):
        arrow(x, 5.35, x, 4.8)
    arrow(3.0, 3.85, 3.0, 3.35); arrow(8.95, 3.85, 8.95, 3.35)
    arrow(3.0, 2.25, 1.9, 1.75); arrow(8.95, 2.25, 2.3, 1.75)
    ax.text(6, 0.18, "Evaluation: monthly replay against ABS recalls, recall linkage retrieval benchmark, guardrail mutation tests",
            ha="center", fontsize=9, style="italic", color=INK)
    _save(fig, cfg, "architecture.png")


def fig_corpus(e: Engine) -> None:
    p = e.panel
    last = p.last_complete + 1
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [1.25, 1]})
    months = pd.PeriodIndex(p.months[:last], freq="M").to_timestamp()
    a.bar(months, p.abs[:, :last].sum(axis=0), width=24, color=BLUE)
    a.set_title("ABS related complaints received per month"); a.set_ylabel("complaints")
    top = pd.Series(p.abs.sum(axis=1), index=p.vehicles).sort_values().tail(12)
    b.barh(top.index, top.to_numpy(), color=TEAL)
    b.set_title("Vehicle families with most ABS complaints"); b.set_xlabel("complaints, all months"); b.grid(axis="y", visible=False)
    _save(fig, e.cfg, "corpus_overview.png")


def fig_leaderboard(e: Engine) -> pd.DataFrame:
    table = e.signals().head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    ax.barh(table["vehicle"], table["score"], color=[TIER_COLOUR[t] for t in table["tier"]])
    for y, row in enumerate(table.itertuples()):
        ax.text(row.score + 0.6, y, f"PRR {row.prr:.1f} | {row.abs_complaints} ABS | last 6 months {row.recent_abs}", va="center", fontsize=8, color=INK)
    ax.set_xlim(0, table["score"].max() * 1.55); ax.set_xlabel("priority score (0 to 100)"); ax.grid(axis="y", visible=False)
    ax.set_title(f"Signal leaderboard as of {table['as_of'].iloc[0]}")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=RED), plt.Rectangle((0, 0), 1, 1, color=BLUE)],
              labels=["emerging (surge channel)", "persistent (disproportionality only)"], loc="upper right",
              bbox_to_anchor=(1.0, -0.1), ncol=2, frameon=False)
    _save(fig, e.cfg, "signal_leaderboard.png")
    return table


def fig_disproportionality(e: Engine) -> None:
    t = signals_as_of(e.panel, e.panel.last_complete, e.cfg)
    t = t[t["abs_complaints"] >= 1]
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    quiet = t[t["tier_code"] == 0]
    ax.scatter(quiet["abs_complaints"], quiet["ic"], s=10, color=GREY, alpha=0.45, label="not flagged")
    for tier in ("persistent", "emerging"):
        part = t[t["tier"] == tier]
        ax.errorbar(part["abs_complaints"], part["ic"], yerr=[part["ic"] - part["ic025"], part["ic975"] - part["ic"]],
                    fmt="o", ms=5, color=TIER_COLOUR[tier], ecolor=TIER_COLOUR[tier], elinewidth=0.8, label=tier)
    for row in t[t["tier_code"] > 0].nlargest(8, "score").itertuples():
        ax.annotate(row.vehicle.title(), (row.abs_complaints, row.ic), xytext=(5, 5), textcoords="offset points", fontsize=8)
    ax.axhline(0, color=INK, lw=0.8); ax.set_xscale("log")
    ax.set_xlabel("ABS related complaints in the 24 month window (log scale)")
    ax.set_ylabel("information component (bars: 95% credibility interval)")
    ax.set_title("Disproportionality map: which families report ABS more than expected"); ax.legend(frameon=False)
    _save(fig, e.cfg, "disproportionality_map.png")


def fig_timelines(e: Engine) -> None:
    replay = np.load(e.cfg.path("processed") / "replay.npz", allow_pickle=True)
    recalls = pd.read_csv(e.cfg.path("reports") / "backtest_recalls.csv")
    caught = recalls[recalls["skidsignal_detected"]].nlargest(2, "abs_complaints_before")["campno"].tolist()
    families = e.signals()["vehicle"].head(2).tolist()
    link, abs_campaigns = e.recall_vehicles, e.campaigns[e.campaigns["is_abs"]]
    for campno in caught:
        candidates = [v for v in link.loc[link["campno"] == campno, "vehicle"].unique() if v in set(e.panel.vehicles) and v not in families]
        if candidates:
            families.append(max(candidates, key=lambda v: e.panel.abs[e.panel.index_of(v)].sum()))
    fig, axes = plt.subplots(2, 2, figsize=(12, 6.6), sharex=True)
    last = e.panel.last_complete + 1
    months = pd.PeriodIndex(e.panel.months[:last], freq="M").to_timestamp()
    for ax, vehicle in zip(axes.ravel(), families[:4]):
        v = e.panel.index_of(vehicle)
        tiers = replay["tiers"][v, :last]
        colours = [RED if t == 2 else BLUE if t == 1 else GREY for t in tiers]
        ax.bar(months, e.panel.abs[v, :last], width=24, color=colours)
        own = abs_campaigns[abs_campaigns["campno"].isin(link.loc[link["vehicle"] == vehicle, "campno"])]
        for c in own.itertuples():
            ax.axvline(c.date, color=INK, ls="--", lw=1)
            ax.text(c.date, ax.get_ylim()[1] * 0.97, f" {c.campno}", rotation=90, va="top", fontsize=7.5, color=INK)
        ax.set_title(vehicle.title()); ax.set_ylabel("ABS complaints")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (GREY, BLUE, RED)] + [plt.Line2D([0], [0], color=INK, ls="--")]
    fig.legend(handles, ["no alert", "persistent alert", "emerging alert", "ABS recall filed (estimated date)"],
               loc="lower center", ncol=4, frameon=False)
    fig.suptitle("Monthly ABS complaints coloured by the alert state the detector held at that time", fontweight="bold")
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    _save(fig, e.cfg, "signal_timelines.png")


def fig_failure_heatmap(e: Engine) -> None:
    table = e.signals()
    table = table[table["abs_complaints"] >= 15].head(12)
    matrix = failure_mode_matrix(e.brake, e.taxonomy, table["vehicle"].tolist(), table["window_start"].iloc[0], table["as_of"].iloc[0])
    fig, ax = plt.subplots(figsize=(11, 5.4))
    image = ax.imshow(matrix.to_numpy() * 100, cmap="YlOrRd", aspect="auto", vmin=0, vmax=80)
    ax.set_xticks(range(matrix.shape[1])); ax.set_yticks(range(matrix.shape[0]))
    ax.set_xticklabels([SHORT_MODE.get(m, m) for m in e.taxonomy.failure_modes], fontsize=8.5)
    ax.set_yticklabels([v.title() for v in matrix.index])
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix.iat[i, j] * 100
            ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=8, color="white" if value > 50 else INK)
    ax.grid(False); ax.set_title("Share of ABS narratives mentioning each failure mode (%), flagged families")
    fig.colorbar(image, ax=ax, shrink=0.8, label="% of narratives")
    _save(fig, e.cfg, "failure_mode_heatmap.png")


def fig_backtest(cfg: Settings) -> None:
    report = json.loads((cfg.path("reports") / "backtest_summary.json").read_text())
    recalls = pd.read_csv(cfg.path("reports") / "backtest_recalls.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.6))
    labels = {"skidsignal": "SkidSignal (both channels)", "surge_channel": "surge channel", "disproportionality_channel": "disproportionality channel"}
    for name, rule in report["rules"].items():
        x, y = rule["mean_active_alerts_per_month"], rule["detectable_abs_recalls"]["sensitivity"]
        ours = name in labels
        a.scatter(x, y, s=90 if ours else 60, color=RED if ours else GREY, zorder=3, marker="o" if ours else "s")
        text = labels.get(name, name.replace("volume_rule_", "volume rule "))
        offset = (8, -12) if ours else {"volume_rule_10": (-52, 8), "volume_rule_8": (-18, 20), "volume_rule_5": (6, 8)}.get(name, (-30, 9))
        a.annotate(text, (x, y), xytext=offset, textcoords="offset points", fontsize=7.5)
    n = report["abs_vehicle_recalls_detectable"]
    a.set_xlabel("mean active alerts per month (analyst workload)"); a.set_ylabel(f"share of {n} detectable ABS recalls alerted before filing")
    a.set_ylim(0, 1.05); a.set_xlim(0, 70); a.set_title("Sensitivity against workload, by rule")
    a.text(0.98, 0.04, "volume rule N: at least N ABS complaints in six months", transform=a.transAxes, ha="right", fontsize=7.5, color=INK)
    hit = recalls[recalls["skidsignal_detected"]].sort_values("skidsignal_lead_months")
    b.barh(hit["campno"] + "  " + hit["makes"].str.title().str.slice(0, 18), hit["skidsignal_lead_months"], color=TEAL)
    b.set_xlabel("months between first alert and recall filing"); b.grid(axis="y", visible=False)
    b.set_title("Lead time for recalls that were alerted in advance")
    fig.tight_layout()
    _save(fig, cfg, "backtest.png")


def fig_retrieval(cfg: Settings) -> None:
    report = json.loads((cfg.path("reports") / "retrieval_benchmark.json").read_text())
    methods = {"bm25": "BM25", "dense": f"dense ({report['embedding_backend']})", "hybrid_equal": "hybrid, equal weights",
               "selected_with_make_filter": "selected + make filter"}
    metrics = ["recall@1", "recall@5", "recall@10", "mrr@10"]
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    width = 0.2
    for i, (key, label) in enumerate(methods.items()):
        means = np.array([report["test"][key][m]["mean"] for m in metrics])
        lo = means - np.array([report["test"][key][m]["ci95"][0] for m in metrics])
        hi = np.array([report["test"][key][m]["ci95"][1] for m in metrics]) - means
        ax.bar(np.arange(len(metrics)) + (i - 1.5) * width, means, width, yerr=[lo, hi], capsize=2, label=label,
               color=[BLUE, GREY, AMBER, TEAL][i], error_kw={"elinewidth": 0.8, "ecolor": INK})
    ax.set_xticks(range(len(metrics))); ax.set_xticklabels([m.replace("@", " at ").replace("mrr", "MRR").replace("recall", "Recall") for m in metrics])
    ax.set_ylim(0, 1); ax.set_ylabel("score (bars: 95% bootstrap interval)"); ax.grid(axis="x", visible=False)
    q = report["queries"]["test"]
    ax.set_title(f"Recall linkage benchmark: {q} held out owner narratives, pool of {report['pool_size']:,} campaigns"); ax.legend(frameon=False)
    _save(fig, cfg, "retrieval_benchmark.png")


def make_all(cfg: Settings) -> None:
    e = Engine(cfg)
    fig_architecture(cfg); fig_corpus(e); fig_leaderboard(e); fig_disproportionality(e)
    fig_failure_heatmap(e)
    for name, fn in (("backtest", fig_backtest), ("retrieval", fig_retrieval)):
        try:
            fn(cfg)
        except FileNotFoundError:
            log.warning("skipping %s figure: run the matching pipeline step first", name)
    try:
        fig_timelines(e)
    except FileNotFoundError:
        log.warning("skipping timelines: run the backtest first")
