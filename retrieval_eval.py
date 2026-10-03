"""Recall linkage benchmark: an organic, label free test of cross source retrieval.

Owners sometimes cite an NHTSA campaign number in their complaint ("this is recall
23V651 and the dealer has no parts"). Each citation is a free relevance label supplied
by the person who wrote the narrative. The task mirrors a daily analyst question: given
an owner narrative, which recall campaign does it relate to?

Query: vehicle line plus narrative, with every campaign number masked.
Pool: every recall campaign in the knowledge base (all components, not only brakes).
Relevant: the single campaign the owner cited, kept only when the campaign covers the
complainant's make so that passing mentions of another brand's recall are excluded.

Campaigns are split into a development half (used to choose fusion weights) and a test
half (reported) by a deterministic hash, so no campaign appears on both sides.
"""
from __future__ import annotations

import hashlib
import json
import re

import numpy as np
import pandas as pd

from skidsignal.config import Settings, get_logger
from skidsignal.index.store import HybridIndex

log = get_logger(__name__)
CAMPAIGN_RE = re.compile(r"\b(\d{2})\s?([VETC])[\s-]?(\d{3})\b", re.IGNORECASE)
METRICS = ["recall@1", "recall@5", "recall@10", "mrr@10", "ndcg@10"]
GRID = [(1.0, 0.0), (10.0, 1.0), (5.0, 1.0), (3.0, 1.0), (1.0, 1.0), (1.0, 3.0)]  # (bm25, dense)


def build_benchmark(index: HybridIndex) -> pd.DataFrame:
    meta = index.meta
    complaints = meta[meta["source"] == "complaint"].drop_duplicates("doc_id")
    recalls = meta[meta["source"] == "recall"].drop_duplicates("doc_id").set_index("doc_id")
    cited = complaints["text"].str.extractall(CAMPAIGN_RE.pattern, flags=re.IGNORECASE)
    cited["target"] = "R:" + cited[0] + cited[1].str.upper() + cited[2]
    cited = cited.join(complaints[["doc_id", "title", "text", "makes"]], on=cited.index.get_level_values(0))
    cited = cited.drop_duplicates(["doc_id", "target"])
    cited = cited[cited["target"].isin(recalls.index)]
    same_make = [make in recalls.at[target, "makes"] for make, target in zip(cited["makes"], cited["target"])]
    cited = cited[same_make]
    cited = cited[cited.groupby("doc_id")["target"].transform("size") == 1]  # one unambiguous label per query

    vehicle_line = cited["title"].str.split("|").str[0].str.strip()
    query = vehicle_line + ". " + cited["text"].map(lambda t: CAMPAIGN_RE.sub(" ", t))
    split = cited["target"].map(lambda t: "dev" if int(hashlib.md5(t.encode()).hexdigest(), 16) % 2 == 0 else "test")
    return pd.DataFrame(
        {"doc_id": cited["doc_id"], "query": query, "target": cited["target"], "split": split,
         "make": cited["makes"].str.strip("|")}
    ).reset_index(drop=True)


def _metrics(ranked: list[str], target: str) -> dict:
    rank = ranked.index(target) + 1 if target in ranked else None
    return {
        "recall@1": float(rank == 1), "recall@5": float(rank is not None and rank <= 5),
        "recall@10": float(rank is not None and rank <= 10),
        "mrr@10": 1.0 / rank if rank and rank <= 10 else 0.0,
        "ndcg@10": 1.0 / np.log2(rank + 1) if rank and rank <= 10 else 0.0,
    }


def run_method(index: HybridIndex, bench: pd.DataFrame, mode: str, weights=None, make_filter: bool = False) -> pd.DataFrame:
    rows = []
    for q in bench.itertuples():
        hits = index.search(q.query, k=10, mode=mode, sources=["recall"], diversify=False, weights=weights,
                            make=q.make if make_filter else None)
        rows.append(_metrics([h.doc_id for h in hits], q.target))
    return pd.DataFrame(rows, columns=METRICS)


def _bootstrap_ci(values: np.ndarray, n: int = 2000, seed: int = 7) -> list[float]:
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n, len(values)), replace=True).mean(axis=1)
    return [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]


def evaluate_retrieval(index: HybridIndex, cfg: Settings) -> dict:
    bench = build_benchmark(index)
    dev, test = bench[bench["split"] == "dev"], bench[bench["split"] == "test"]
    log.info("benchmark: %d queries (%d dev, %d test)", len(bench), len(dev), len(test))

    dev_scores = {w: float(run_method(index, dev, "hybrid", w)["mrr@10"].mean()) for w in GRID}
    best = max(dev_scores, key=dev_scores.get)
    methods = {
        "bm25": ("bm25", None, False), "dense": ("dense", None, False), "hybrid_equal": ("hybrid", (1.0, 1.0), False),
        "selected": ("hybrid", best, False), "selected_with_make_filter": ("hybrid", best, True),
    }
    per_query = {name: run_method(index, test, mode, weights, flt) for name, (mode, weights, flt) in methods.items()}
    summary = {
        name: {m: {"mean": round(float(res[m].mean()), 4), "ci95": _bootstrap_ci(res[m].to_numpy())} for m in METRICS}
        for name, res in per_query.items()
    }
    paired = {}
    for a, b in (("bm25", "dense"), ("bm25", "hybrid_equal"), ("selected_with_make_filter", "selected")):
        diff = per_query[a]["mrr@10"].to_numpy() - per_query[b]["mrr@10"].to_numpy()
        paired[f"{a}_minus_{b}"] = {"mean": round(float(diff.mean()), 4), "ci95": _bootstrap_ci(diff)}

    report = {
        "task": "owner narrative to cited recall campaign",
        "pool_size": int(index.meta.loc[index.meta["source"] == "recall", "doc_id"].nunique()),
        "queries": {"total": len(bench), "dev": len(dev), "test": len(test)},
        "campaigns": {"dev": int(dev["target"].nunique()), "test": int(test["target"].nunique())},
        "dev_grid_mrr@10": {f"bm25={w[0]},dense={w[1]}": round(s, 4) for w, s in dev_scores.items()},
        "selected_weights": {"bm25": best[0], "dense": best[1]},
        "test": summary,
        "paired_mrr@10_difference": paired,
        "embedding_backend": index.embedder.name,
    }
    (cfg.path("reports") / "retrieval_benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
