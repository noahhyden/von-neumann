"""Red-hat + validation for arbitrary polynomial chaos (aPCE).

`pce_fit` now handles LogNormal / LogUniform inputs by building the orthonormal
basis from the distribution's own moments (the Stieltjes recurrence) instead of a
fixed Askey family. The claims under attack:

- the moment-built basis is genuinely **orthonormal under the distribution**, so
  the recovered mean/variance match closed forms (LogUniform f=x);
- it agrees with plain Monte Carlo on a nonlinear finding of a LogNormal input;
- the general machinery **subsumes the Askey cases** - Stieltjes-on-Uniform gives
  the same nodes as analytic Legendre, and mixing a LogUniform with a Uniform
  works;
- both fit methods (quadrature and regression) work for arbitrary inputs;
- it is deterministic (§7), and the fit_residual honesty guard still fires.
"""

from __future__ import annotations

import math

import pytest

from vn_core.uq import (
    LogNormal,
    LogUniform,
    Normal,
    Uniform,
    monte_carlo,
    pce_fit,
)
from vn_core.uq.pce import _gauss_nodes_weights, _stieltjes


# --- The recurrence is correct: orthonormal + reproduces Askey ----------------


def test_stieltjes_on_uniform_reproduces_analytic_legendre_nodes():
    """Stieltjes on a Uniform must recover the exact Legendre Gauss nodes (the
    general machinery subsuming the known Askey case)."""
    from vn_core.uq.pce import _gauss_from_recurrence

    _mu, sigma, alpha, beta = _stieltjes(Uniform(-1.0, 1.0), 5)
    nodes_std, _w = _gauss_from_recurrence(alpha, beta, 4)
    # standardized (unit-variance) nodes -> physical: multiply by sigma = std of U(-1,1)
    got = sorted(z * sigma for z in nodes_std)
    leg_nodes, _ = _gauss_nodes_weights("legendre", 4)
    for a, b in zip(got, sorted(leg_nodes)):
        assert a == pytest.approx(b, abs=1e-4)


def test_loguniform_moments_match_closed_form():
    """f(x)=x over LogUniform(a,b): mean=(b-a)/ln(b/a), var from E[X^2]-mean^2.
    aPCE must recover both, by quadrature and by regression."""
    a, b = 2.5, 355.0
    ln = math.log(b / a)
    mean_an = (b - a) / ln
    var_an = (b * b - a * a) / (2 * ln) - mean_an**2
    for method in ("quadrature", "regression"):
        r = pce_fit({"x": LogUniform(a, b)}, lambda s: s["x"], degree=4, method=method, seed=1)
        assert r.mean == pytest.approx(mean_an, rel=1e-4)
        assert r.variance == pytest.approx(var_an, rel=1e-3)
        assert r.fit_residual < 1e-3  # f=x is degree 1, well within the basis


def test_apce_agrees_with_monte_carlo_on_a_lognormal_finding():
    inputs = {"e": LogNormal(gmean=6000.0, gstd=1.6), "k": Uniform(0.5, 1.0)}

    def finding(s):
        return s["e"] * s["k"]

    r = pce_fit(inputs, finding, degree=6, method="regression", seed=1)
    mc = monte_carlo(inputs, finding, n=60000, seed=2)
    assert r.mean == pytest.approx(mc.mean, rel=0.02)
    assert r.std == pytest.approx(mc.std, rel=0.05)


def test_mixed_loguniform_and_uniform():
    """A LogUniform (arbitrary) mixed with a Uniform (Askey) in one fit, on a
    finding that IS low-degree in the physical variable."""
    inputs = {"strength": LogUniform(2.5, 355.0), "load": Uniform(10.0, 50.0)}

    def finding(s):
        return s["load"] + 0.5 * s["strength"]  # linear, smooth in physical x

    r = pce_fit(inputs, finding, degree=4, method="regression", seed=1)
    mc = monte_carlo(inputs, finding, n=60000, seed=3)
    assert r.is_trustworthy()
    assert r.mean == pytest.approx(mc.mean, rel=0.02)
    assert set(r.total_order) == {"strength", "load"}


# --- Sobol from aPCE + honesty guard ------------------------------------------


def test_apce_sobol_ranks_the_driver():
    """The wide LogUniform strength (huge variance) dominates a linear finding."""
    inputs = {"strength": LogUniform(2.5, 355.0), "load": Uniform(40.0, 60.0)}
    r = pce_fit(inputs, lambda s: s["strength"] + s["load"], degree=4, method="regression", seed=1)
    assert r.is_trustworthy()
    assert r.total_order["strength"] > r.total_order["load"]


def test_apce_fit_residual_flags_a_kink():
    """A kink in a LogUniform input still trips the honesty guard through the
    arbitrary-basis path."""

    def kink(s):
        return max(0.0, s["x"] - 100.0)

    r = pce_fit({"x": LogUniform(2.5, 355.0)}, kink, degree=8, method="regression", seed=1)
    assert not r.is_trustworthy()


def test_apce_flags_findings_not_polynomial_in_the_physical_variable():
    """aPCE's real limitation, honestly caught: 1/x over a 2-orders-of-magnitude
    LogUniform is smooth in *log* space but not low-degree in physical x, so the
    polynomial fit is poor - and fit_residual must say so (never a silent wrong
    mean). This is why the guard matters more, not less, for arbitrary inputs."""
    inputs = {"x": LogUniform(2.5, 355.0)}
    r = pce_fit(inputs, lambda s: 1.0 / s["x"], degree=6, method="regression", seed=1)
    assert not r.is_trustworthy()


# --- Determinism + contract ----------------------------------------------------


def test_apce_is_deterministic():
    inputs = {"x": LogNormal(gmean=100.0, gstd=1.4)}
    a = pce_fit(inputs, lambda s: s["x"] ** 0.5, degree=5, method="quadrature")
    b = pce_fit(inputs, lambda s: s["x"] ** 0.5, degree=5, method="quadrature")
    assert a.coefficients == b.coefficients
    assert a.variance == b.variance


def test_apce_normal_still_uses_hermite_not_arbitrary():
    """A Normal input must still take the exact Hermite path (byte-level), not the
    moment-based arbitrary one - regression check on the fast/exact case."""
    from vn_core.uq.pce import _adapt

    assert _adapt(Normal(mean=1.0, std=2.0), 5).kind == "hermite"
    assert _adapt(Uniform(0.0, 1.0), 5).kind == "legendre"
    assert _adapt(LogUniform(1.0, 10.0), 5).kind == "arbitrary"
