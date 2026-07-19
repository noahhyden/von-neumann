"""Red-hat + validation for the honest-sensitivity additions to Sobol.

Two additions, one PR: first-order indices (free - they reuse the total-order
evaluations) and confidence intervals on every index (asymptotic by default,
bootstrap opt-in). The claims under attack:

- first-order is *correct* (matches Ishigami analytic and PCE) and *free* (no
  extra model evaluations, even with bootstrap);
- the total-order point estimate is **unchanged** by all of this;
- the CIs are honest: they bracket the estimate, shrink with N, are deterministic,
  and - the headline - an unresolved index reads as "CI straddles 0" rather than a
  confident number (Ishigami x3's main effect);
- S_i <= S_Ti always (a first/total swap would trip this);
- bootstrap agrees with the cheap asymptotic default but never moves the estimate.
"""

from __future__ import annotations

import math

import pytest

from vn_core.uq import Uniform, pce_fit, sobol_total_order, uq_and_gsa

PI = math.pi
_A, _B = 7.0, 0.1
_ISH = {n: Uniform(-PI, PI) for n in ("x1", "x2", "x3")}


def _ishigami(s):
    return math.sin(s["x1"]) + _A * math.sin(s["x2"]) ** 2 + _B * s["x3"] ** 4 * math.sin(s["x1"])


# Analytic Ishigami indices.
_D = _A**2 / 8 + _B * PI**4 / 5 + _B**2 * PI**8 / 18 + 0.5
_S1 = 0.5 * (1 + _B * PI**4 / 5) ** 2 / _D  # ~0.314
_S2 = (_A**2 / 8) / _D  # ~0.442


# --- First-order correctness (and it is free) ----------------------------------


def test_first_order_matches_ishigami_analytic():
    r = sobol_total_order(_ISH, _ishigami, n=8000, seed=1)
    assert r.first_order["x1"] == pytest.approx(_S1, abs=0.03)
    assert r.first_order["x2"] == pytest.approx(_S2, abs=0.03)
    assert r.first_order["x3"] == pytest.approx(0.0, abs=0.03)  # pure interaction


def test_first_order_agrees_with_pce():
    """The MC first-order estimator and PCE's closed-form first-order must agree
    on a smooth finding - two independent routes to the same quantity."""
    sob = sobol_total_order(_ISH, _ishigami, n=8000, seed=1)
    pce = pce_fit(_ISH, _ishigami, degree=10, seed=1)
    for name in ("x1", "x2", "x3"):
        assert sob.first_order[name] == pytest.approx(pce.first_order[name], abs=0.03)


def test_first_order_and_bootstrap_add_no_model_evaluations():
    """First-order reuses the total-order evaluations, and bootstrap resamples
    cached values - so the model is still called exactly N*(K+2) times even with
    bootstrap on. This is the 'free' claim."""
    n, k = 2000, len(_ISH)
    calls = {"n": 0}

    def counted(s):
        calls["n"] += 1
        return _ishigami(s)

    sobol_total_order(_ISH, counted, n=n, seed=1, bootstrap=300)
    assert calls["n"] == n * (k + 2)


# --- The total-order estimate must not move ------------------------------------


def test_total_order_still_matches_analytic():
    r = sobol_total_order(_ISH, _ishigami, n=8000, seed=1)
    # Analytic total-order: x2 = S2 (no interactions), x1 ~ 0.557, x3 ~ 0.244.
    assert r.total_order["x2"] == pytest.approx(_S2, abs=0.03)
    assert r.total_order["x1"] > 0.50
    assert r.total_order["x3"] > 0.20


def test_bootstrap_does_not_change_the_point_estimates():
    """Bootstrap only fills the CI fields; the indices themselves come from the
    (deterministic) design and must be byte-identical with or without it."""
    a = sobol_total_order(_ISH, _ishigami, n=1500, seed=1)
    b = sobol_total_order(_ISH, _ishigami, n=1500, seed=1, bootstrap=300)
    assert a.total_order == b.total_order
    assert a.first_order == b.first_order


# --- S_i <= S_Ti (fundamental) -------------------------------------------------


def test_first_order_never_exceeds_total_order():
    r = sobol_total_order(_ISH, _ishigami, n=8000, seed=1)
    for name in ("x1", "x2", "x3"):
        # main effect <= total effect, up to estimator noise
        assert r.first_order[name] <= r.total_order[name] + 0.02


# --- The honest CI: unresolved index straddles zero ----------------------------


def test_x3_main_effect_ci_contains_zero_but_total_effect_does_not():
    """Ishigami x3 has NO main effect but a real interaction effect. The honest
    reading: its first-order CI straddles 0 (unresolved / consistent with zero),
    while its total-order CI sits strictly above 0."""
    r = sobol_total_order(_ISH, _ishigami, n=4000, seed=1)
    lo_f, hi_f = r.first_order_ci["x3"]
    assert lo_f <= 0.0 <= hi_f  # main effect indistinguishable from zero
    lo_t, hi_t = r.total_order_ci["x3"]
    assert lo_t > 0.0  # total effect resolved as positive


def test_ci_brackets_the_point_estimate():
    r = sobol_total_order(_ISH, _ishigami, n=4000, seed=1)
    for name in ("x1", "x2", "x3"):
        lo, hi = r.total_order_ci[name]
        assert lo <= r.total_order[name] <= hi
        lo, hi = r.first_order_ci[name]
        assert lo <= r.first_order[name] <= hi


def test_ci_width_shrinks_with_n():
    """More samples must resolve the index better: a 4x larger design gives a
    narrower CI."""
    small = sobol_total_order(_ISH, _ishigami, n=1000, seed=1)
    big = sobol_total_order(_ISH, _ishigami, n=8000, seed=1)

    def width(r, name):
        lo, hi = r.total_order_ci[name]
        return hi - lo

    for name in ("x1", "x2"):
        assert width(big, name) < width(small, name)


def test_bootstrap_ci_agrees_with_asymptotic():
    """The cheap default (asymptotic) must track the resampling CI - this is why
    asymptotic can be the always-on default."""
    asy = sobol_total_order(_ISH, _ishigami, n=4000, seed=1)
    boot = sobol_total_order(_ISH, _ishigami, n=4000, seed=1, bootstrap=500)
    for name in ("x1", "x2"):
        for k in (0, 1):  # both CI ends
            assert boot.first_order_ci[name][k] == pytest.approx(
                asy.first_order_ci[name][k], abs=0.03
            )


# --- Determinism, labelling, degenerate cases ----------------------------------


def test_ci_is_deterministic():
    a = sobol_total_order(_ISH, _ishigami, n=1500, seed=7, bootstrap=200)
    b = sobol_total_order(_ISH, _ishigami, n=1500, seed=7, bootstrap=200)
    assert a.first_order_ci == b.first_order_ci
    assert a.total_order_ci == b.total_order_ci


def test_ci_method_label():
    assert sobol_total_order(_ISH, _ishigami, n=500, seed=1).ci_method == "asymptotic"
    assert sobol_total_order(_ISH, _ishigami, n=500, seed=1, bootstrap=100).ci_method == "bootstrap"


def test_constant_finding_zero_indices_and_ci():
    r = sobol_total_order(_ISH, lambda s: 3.0, n=200, seed=1)
    assert all(v == 0.0 for v in r.total_order.values())
    assert all(v == 0.0 for v in r.first_order.values())
    assert all(ci == (0.0, 0.0) for ci in r.total_order_ci.values())
    assert r.ci_method == "none"


def test_uq_and_gsa_gsa_carries_first_order_and_cis():
    ana = uq_and_gsa(_ISH, _ishigami, n=2000, seed=1)
    assert set(ana.gsa.first_order) == {"x1", "x2", "x3"}
    assert set(ana.gsa.first_order_ci) == {"x1", "x2", "x3"}
    assert ana.gsa.ci_method == "asymptotic"
