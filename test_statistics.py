import numpy as np
import pytest

from skidsignal.signals.disproportionality import disproportionality
from skidsignal.signals.temporal import benjamini_hochberg, cusum, surge_test


def test_prr_ror_and_ic_match_hand_calculation():
    # a=20, n=100, A=120, N=10100  ->  b=80, c=100, d=9900
    s = disproportionality([20], [100], 120, 10100)
    assert s["prr"][0] == pytest.approx((20 / 100) / (100 / 10000))            # 20.0
    assert s["ror"][0] == pytest.approx((20 * 9900) / (80 * 100))              # 24.75
    expected = 100 * 120 / 10100
    assert s["expected"][0] == pytest.approx(expected)
    assert s["ic"][0] == pytest.approx(np.log2(20.5 / (expected + 0.5)))
    assert s["ic025"][0] < s["ic"][0] < s["ic975"][0]
    assert s["prr_lo"][0] < s["prr"][0] < s["prr_hi"][0]
    assert s["chi2"][0] > 4


def test_no_excess_gives_prr_near_one_and_negative_lower_bound():
    s = disproportionality([10], [1000], 100, 10000)
    assert s["prr"][0] == pytest.approx(1.0)
    assert s["ic025"][0] < 0


def test_shrinkage_keeps_tiny_counts_from_signalling():
    # one ABS complaint out of one is a 100 percent share but must not look like a signal
    s = disproportionality([1], [1], 300, 10000)
    assert s["ic025"][0] < 0


def test_empty_cells_do_not_produce_infinite_odds_ratio():
    s = disproportionality([5], [5], 50, 1000)
    assert np.isfinite(s["ror"][0])


def test_benjamini_hochberg_known_values():
    q = benjamini_hochberg(np.array([0.01, 0.04, 0.03, 0.005]))
    assert q == pytest.approx([0.02, 0.04, 0.04, 0.02])
    assert benjamini_hochberg(np.array([])).size == 0


def test_surge_test_flags_a_jump_and_respects_database_trend():
    quiet = surge_test(np.array([6]), np.array([18]), recent_months=6, baseline_months=18)
    jump = surge_test(np.array([30]), np.array([18]), recent_months=6, baseline_months=18)
    assert quiet["p"][0] > 0.4 and jump["p"][0] < 1e-6
    assert jump["rate_ratio"][0] == pytest.approx(5.0)
    adjusted = surge_test(np.array([30]), np.array([18]), 6, 18, trend=5.0)
    assert adjusted["p"][0] > 0.4          # the whole database rose fivefold, so this is not a surge


def test_surge_test_without_baseline_is_neutral():
    assert surge_test(np.array([9]), np.array([0]), 6, 0)["p"][0] == 1.0


def test_cusum_accumulates_on_sustained_shift_and_resets():
    flat = cusum(np.array([[2, 2, 2, 2, 2, 2, 2, 2]]), baseline_months=4)
    shift = cusum(np.array([[2, 2, 2, 2, 6, 6, 6, 6]]), baseline_months=4)
    assert flat.max() == 0
    assert np.all(np.diff(shift[0, 3:]) > 0) and shift[0, -1] > 4
