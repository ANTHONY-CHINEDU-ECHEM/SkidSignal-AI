"""Failure mode profiling: taxonomy shares per vehicle and unsupervised narrative clusters."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

from skidsignal.config import Settings, get_logger
from skidsignal.index.store import HybridIndex
from skidsignal.index.text import STOP_WORDS
from skidsignal.processing.taxonomy import Taxonomy

log = get_logger(__name__)


def window_slice(brake: pd.DataFrame, vehicle: str | None, start: str, end: str) -> pd.DataFrame:
    """ABS complaints for a vehicle family received between two 'YYYY-MM' months inclusive."""
    mask = brake["is_abs"] & (brake["prod_type"] == "V") & (brake["month"] >= start) & (brake["month"] <= end)
    if vehicle:
        mask &= brake["vehicle"] == vehicle.upper()
    return brake[mask]


def failure_mode_profile(rows: pd.DataFrame, taxonomy: Taxonomy) -> pd.DataFrame:
    counts = rows[taxonomy.fm_columns].sum().astype(int)
    out = pd.DataFrame(
        {"mode": [c[3:] for c in taxonomy.fm_columns], "label": [taxonomy.labels[c[3:]] for c in taxonomy.fm_columns],
         "count": counts.to_numpy(), "share": counts.to_numpy() / max(len(rows), 1)}
    )
    return out.sort_values("count", ascending=False).reset_index(drop=True)


def failure_mode_matrix(brake: pd.DataFrame, taxonomy: Taxonomy, vehicles: list[str], start: str, end: str) -> pd.DataFrame:
    rows = window_slice(brake, None, start, end)
    rows = rows[rows["vehicle"].isin(vehicles)]
    matrix = rows.groupby("vehicle")[taxonomy.fm_columns].mean().reindex(vehicles)
    matrix.columns = [taxonomy.labels[c[3:]] for c in matrix.columns]
    return matrix


def model_year_distribution(rows: pd.DataFrame, top: int = 5) -> list[tuple[int, int]]:
    counts = rows["model_year"].dropna().astype(int).value_counts().head(top)
    return [(int(year), int(n)) for year, n in counts.items()]


def cluster_narratives(index: HybridIndex, brake: pd.DataFrame, cfg: Settings) -> tuple[pd.DataFrame, dict]:
    """K means on the dense vectors of ABS complaint narratives, k chosen by silhouette."""
    c = cfg.clustering
    meta = index.meta
    first_chunk = meta[(meta["source"] == "complaint") & meta["is_abs"]].drop_duplicates("doc_id")
    vectors = index.vectors[first_chunk.index.to_numpy()]
    rng = np.random.default_rng(c.random_state)
    sample = rng.choice(len(vectors), size=min(c.sample_for_silhouette, len(vectors)), replace=False)

    scores, models = {}, {}
    for k in c.k_candidates:
        if k >= len(vectors):
            continue
        model = KMeans(n_clusters=k, n_init=4, random_state=c.random_state).fit(vectors)
        scores[k] = float(silhouette_score(vectors[sample], model.labels_[sample], metric="cosine"))
        models[k] = model
    best_k = max(scores, key=scores.get)
    labels = models[best_k].labels_

    tfidf = TfidfVectorizer(stop_words=STOP_WORDS, min_df=5, max_df=0.7, ngram_range=(1, 2), sublinear_tf=True)
    weights = tfidf.fit_transform(first_chunk["text"])
    terms = np.asarray(tfidf.get_feature_names_out())
    overall = np.asarray(weights.mean(axis=0)).ravel()

    facts = brake.assign(doc_id="C:" + brake["complaint_id"].astype(str)).set_index("doc_id")
    facts = facts.reindex(first_chunk["doc_id"])
    rows = []
    for cluster in range(best_k):
        member = labels == cluster
        lift = np.asarray(weights[member].mean(axis=0)).ravel() - overall
        top_terms = terms[np.argsort(-lift)[:8]]
        members = facts[member]
        centre = models[best_k].cluster_centers_[cluster]
        nearest = np.argsort(-(vectors[member] @ centre))[:3]
        rows.append(
            {
                "cluster": cluster, "size": int(member.sum()), "share": round(float(member.mean()), 4),
                "top_terms": ", ".join(top_terms), "severe_share": round(float(members["severe"].mean()), 4),
                "fire_share": round(float(members["fire"].mean()), 4),
                "top_vehicles": ", ".join(members["vehicle"].value_counts().head(3).index),
                "examples": ", ".join(first_chunk["doc_id"].to_numpy()[member][nearest]),
            }
        )
    table = pd.DataFrame(rows).sort_values("size", ascending=False).reset_index(drop=True)
    info = {"narratives": int(len(vectors)), "silhouette_by_k": {str(k): round(s, 4) for k, s in scores.items()}, "selected_k": int(best_k)}
    table.to_csv(cfg.path("reports") / "failure_clusters.csv", index=False)
    return table, info
