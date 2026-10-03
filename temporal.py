"""Temporal emergence tests: Poisson surge test, false discovery control, and CUSUM."""
from __future__ import annotations

import numpy as np
from scipy.stats import poisson


def surge_test(recent: np.ndarray, baseline: np.ndarray, recent_months: int, baseline_months: int,
               trend: float = 1.0) -> dict[str, np.ndarray]:
    """Is the recent count higher than the vehicle's own earlier rate predicts?

    `trend` rescales the expectation by the change in ABS complaint volume across the
    whole database, so a reporting wave that lifts every vehicle is not read as a surge.
    A floor of half a complaint on the baseline keeps new models from dividing by zero.
    """
    recent, baseline = np.asarray(recent, dtype=float), np.asarray(baseline, dtype=float)
    if baseline_months <= 0:
        ones = np.ones_like(recent)
        return {"expected_recent": np.full_like(recent, np.nan), "rate_ratio": np.full_like(recent, np.nan), "p": ones}
    expected = np.maximum(baseline, 0.5) / baseline_months * recent_months * trend
    return {"expected_recent": expected, "rate_ratio": recent / expected, "p": poisson.sf(recent - 1, expected)}


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    """Adjusted p values (q values) controlling the false discovery rate."""
    p = np.asarray(p, dtype=float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out


def cusum(counts: np.ndarray, baseline_months: int, k: float = 0.5) -> np.ndarray:
    """One sided standardised CUSUM along the last axis; returns the path S_t.

    The mean comes from the first `baseline_months` columns and the scale is the
    Poisson standard deviation, floored so sparse series do not explode.
    """
    counts = np.atleast_2d(np.asarray(counts, dtype=float))
    mu = counts[:, :baseline_months].mean(axis=1) if baseline_months > 0 else np.zeros(len(counts))
    sigma = np.sqrt(np.maximum(mu, 0.25))
    path = np.zeros_like(counts)
    s = np.zeros(len(counts))
    for t in range(counts.shape[1]):
        s = np.maximum(0.0, s + (counts[:, t] - mu) / sigma - k)
        path[:, t] = s
    return path
