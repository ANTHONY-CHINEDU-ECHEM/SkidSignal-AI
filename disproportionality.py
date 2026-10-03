"""Disproportionality statistics for a vehicle by event contingency table.

                     ABS complaint   other complaint
    this vehicle           a                b            n = a + b
    all other vehicles     c                d
    column total           A                               N

All functions are vectorised over vehicles.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import gamma

Z95 = 1.959964


def disproportionality(a, n, A: float, N: float) -> dict[str, np.ndarray]:
    a, n = np.asarray(a, dtype=float), np.asarray(n, dtype=float)
    b, c = n - a, A - a
    d = N - n - c
    with np.errstate(divide="ignore", invalid="ignore"):
        prr = (a / n) / (c / (N - n))
        se_prr = np.sqrt(1 / a - 1 / n + 1 / c - 1 / (N - n))
        prr_lo, prr_hi = prr * np.exp(-Z95 * se_prr), prr * np.exp(Z95 * se_prr)

        chi2 = N * np.maximum(np.abs(a * d - b * c) - N / 2, 0) ** 2 / ((a + b) * (c + d) * (a + c) * (b + d))

        h = 0.5 * ((a == 0) | (b == 0) | (c == 0) | (d == 0))  # Haldane correction only when a cell is empty
        ror = ((a + h) * (d + h)) / ((b + h) * (c + h))
        se_ror = np.sqrt(1 / (a + h) + 1 / (b + h) + 1 / (c + h) + 1 / (d + h))
        ror_lo, ror_hi = ror * np.exp(-Z95 * se_ror), ror * np.exp(Z95 * se_ror)

        expected = n * A / N
        ic = np.log2((a + 0.5) / (expected + 0.5))
        ic025 = np.log2(gamma.ppf(0.025, a + 0.5) / (expected + 0.5))
        ic975 = np.log2(gamma.ppf(0.975, a + 0.5) / (expected + 0.5))
    return {
        "prr": prr, "prr_lo": prr_lo, "prr_hi": prr_hi, "chi2": chi2, "ror": ror, "ror_lo": ror_lo,
        "ror_hi": ror_hi, "expected": expected, "ic": ic, "ic025": ic025, "ic975": ic975,
    }
