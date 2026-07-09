"""Tests for the seeded, dependency-free ensemble statistics (experiments/stats_util.py).

Assert real behaviour: the sign-test p-value matches the exact binomial tail, and the
bootstrap CI is deterministic (seeded) and brackets the point median.
"""

from __future__ import annotations

import pytest

from experiments.stats_util import bootstrap_median_ci, sign_test_positive


def test_sign_test_all_positive_is_two_over_2n() -> None:
    # 32 seeds all positive: p = 2 * C(32,32) / 2^32 = 2 / 2^32 - the strongest possible
    # paired statement, and the exact value the paper reports for both slingshot policies.
    k, n, p = sign_test_positive([1.0] * 32)
    assert (k, n) == (32, 32)
    assert p == pytest.approx(2.0 / 2**32, rel=1e-9)


def test_sign_test_drops_zeros_and_reports_null() -> None:
    # The powered policy: every penalty is 0, so all are dropped and the test is null.
    k, n, p = sign_test_positive([0.0] * 10)
    assert (k, n, p) == (0, 0, 1.0)


def test_sign_test_matches_exact_binomial_tail() -> None:
    # [1,1,1,-1]: n=4, k=3 -> two-sided p = 2*(C(4,3)+C(4,4))/2^4 = 2*5/16 = 0.625.
    k, n, p = sign_test_positive([1.0, 1.0, 1.0, -1.0])
    assert (k, n) == (3, 4)
    assert p == pytest.approx(0.625, rel=1e-9)


def test_bootstrap_is_deterministic_and_brackets_the_median() -> None:
    xs = [10.0, 20.0, 30.0, 40.0, 50.0, 22.0, 28.0, 33.0]
    med_a, lo_a, hi_a = bootstrap_median_ci(xs, seed=42)
    med_b, lo_b, hi_b = bootstrap_median_ci(xs, seed=42)
    assert (med_a, lo_a, hi_a) == (med_b, lo_b, hi_b)  # same seed -> identical CI
    assert lo_a <= med_a <= hi_a  # the point median lies inside its own CI


def test_bootstrap_ci_narrows_with_more_data() -> None:
    # A tight cluster gives a narrow CI; a wide spread gives a wider one (same n).
    tight, _, _ = (bootstrap_median_ci([50.0] * 16))
    _, lo_w, hi_w = bootstrap_median_ci([float(i) for i in range(16)])
    _, lo_t, hi_t = bootstrap_median_ci([50.0] * 16)
    assert hi_t - lo_t == 0.0  # identical values -> zero-width CI
    assert hi_w - lo_w > 0.0
