"""Distributions: assert on the inverse-CDF math and edge cases, not execution.

Each Distribution's `quantile(u)` is the entire sampling surface - if the math is
right and the RNG stream is deterministic, MC and Sobol both inherit correctness.
So these tests pin the analytic properties on a few sourced-shape distributions,
plus the domain-guard edges.
"""

import math

import pytest

from vn_core.uq.distributions import (
    Fixed,
    LogNormal,
    Normal,
    Uniform,
    _erfinv,
)


def test_fixed_is_a_constant_map():
    d = Fixed(value=3.14)
    assert d.mean == 3.14
    assert d.quantile(0.0) == 3.14
    assert d.quantile(0.5) == 3.14
    assert d.quantile(0.999) == 3.14


def test_uniform_quantile_endpoints_and_median():
    d = Uniform(low=2.0, high=6.0)
    assert d.quantile(0.0) == pytest.approx(2.0)
    assert d.quantile(0.5) == pytest.approx(4.0)
    assert d.quantile(0.999) == pytest.approx(6.0 - 4.0 * 0.001)
    assert d.mean == 4.0


def test_uniform_is_monotonic():
    d = Uniform(low=-1.0, high=1.0)
    us = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.999]
    xs = [d.quantile(u) for u in us]
    assert all(a < b for a, b in zip(xs, xs[1:]))


def test_uniform_rejects_degenerate_range():
    with pytest.raises(ValueError):
        Uniform(low=1.0, high=1.0)
    with pytest.raises(ValueError):
        Uniform(low=2.0, high=1.0)


def test_normal_quantile_median_is_the_mean():
    d = Normal(mean=1360.8, std=0.5)
    assert d.quantile(0.5) == pytest.approx(1360.8, abs=1e-9)


def test_normal_quantile_symmetry():
    # Phi^-1(u) = -Phi^-1(1 - u): so quantile deviations from the mean should mirror.
    d = Normal(mean=0.0, std=1.0)
    for u in [0.1, 0.25, 0.4]:
        lo = d.quantile(u)
        hi = d.quantile(1.0 - u)
        assert lo == pytest.approx(-hi, abs=1e-6)


def test_normal_quantile_matches_known_z_scores():
    # Standard normal quantiles at commonly-cited probabilities.
    d = Normal(mean=0.0, std=1.0)
    # 1-sigma: ~0.8413 CDF, ~0.1587 = 1 - 0.8413
    assert d.quantile(0.8413) == pytest.approx(1.0, abs=1e-3)
    # 2-sigma: ~0.9772
    assert d.quantile(0.9772) == pytest.approx(2.0, abs=1e-3)
    # 95th percentile ~ 1.6449
    assert d.quantile(0.95) == pytest.approx(1.6449, abs=1e-3)


def test_normal_zero_std_is_a_point():
    d = Normal(mean=42.0, std=0.0)
    for u in [0.001, 0.5, 0.999]:
        assert d.quantile(u) == 42.0


def test_normal_rejects_negative_std():
    with pytest.raises(ValueError):
        Normal(mean=0.0, std=-0.1)


def test_lognormal_geometric_mean_at_median():
    d = LogNormal(gmean=0.30, gstd=1.05)
    # For a log-normal, the median equals the geometric mean.
    assert d.quantile(0.5) == pytest.approx(0.30, abs=1e-6)


def test_lognormal_stays_positive_over_the_whole_domain():
    d = LogNormal(gmean=0.30, gstd=1.5)
    for u in [1e-14, 0.001, 0.5, 0.999]:
        assert d.quantile(u) > 0


def test_lognormal_gstd_one_is_a_point():
    d = LogNormal(gmean=0.30, gstd=1.0)
    for u in [0.001, 0.5, 0.999]:
        assert d.quantile(u) == 0.30


def test_lognormal_rejects_invalid_params():
    with pytest.raises(ValueError):
        LogNormal(gmean=0.0, gstd=1.05)
    with pytest.raises(ValueError):
        LogNormal(gmean=-1.0, gstd=1.05)
    with pytest.raises(ValueError):
        LogNormal(gmean=0.30, gstd=0.5)


def test_quantile_rejects_u_outside_unit_interval():
    for d in [Fixed(1.0), Uniform(0.0, 1.0), Normal(0.0, 1.0), LogNormal(1.0, 1.5)]:
        with pytest.raises(ValueError):
            d.quantile(-0.01)
        with pytest.raises(ValueError):
            d.quantile(1.0)


def test_erfinv_round_trips_against_erf():
    # If erf(erfinv(x)) == x on the interior, the Winitzki + Halley refinement is honest.
    for x in [-0.9, -0.5, -0.1, 0.0, 0.1, 0.5, 0.9, 0.99]:
        y = _erfinv(x)
        assert math.erf(y) == pytest.approx(x, abs=1e-9)


def test_erfinv_rejects_domain_boundary():
    with pytest.raises(ValueError):
        _erfinv(1.0)
    with pytest.raises(ValueError):
        _erfinv(-1.0)
