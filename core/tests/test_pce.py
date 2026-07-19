"""Red-hat (adversarial) + validation tests for polynomial chaos (`pce_fit`).

PCE is only honest if (a) the quadrature engine is exact where it claims to be,
(b) it recovers smooth findings and pins their Sobol structure, and - the one that
matters most - (c) it *tells you when it failed* on a non-smooth finding instead of
returning confident nonsense. These tests attack each:

- the Gauss nodes must integrate polynomials exactly to degree 2m-1;
- a polynomial finding must be recovered to machine precision, moments + Sobol;
- the Ishigami benchmark must match analytic Sobol, including x3's ZERO first-
  order but nonzero total-order (pure interaction - the case a first-order-only
  implementation gets wrong);
- PCE moments/indices must agree with the MC surfaces on a smooth finding;
- **the fit_residual must spike on a kink** so is_trustworthy() reads False - the
  honest-null guard;
- unsupported distributions and nonfinite returns must raise, not limp on;
- same inputs -> byte-identical (§7).
"""

from __future__ import annotations

import math

import pytest

from vn_core.uq import (
    Fixed,
    LogNormal,
    Normal,
    Uniform,
    monte_carlo,
    pce_fit,
    sobol_total_order,
)
from vn_core.uq.pce import _gauss_nodes_weights

PI = math.pi


# --- Gauss quadrature engine ---------------------------------------------------


def test_legendre_nodes_integrate_polynomials_exactly():
    """m-point Gauss-Legendre integrates x^k exactly to k = 2m-1. Reference
    measure is uniform on [-1, 1] (weight 1/2): E[x^k] = 0 (odd), 1/(k+1) (even)."""
    m = 5
    nodes, weights = _gauss_nodes_weights("legendre", m)
    assert sum(weights) == pytest.approx(1.0)  # probability measure
    for k in range(2 * m):
        quad = sum(w * x**k for x, w in zip(nodes, weights))
        exact = 0.0 if k % 2 == 1 else 1.0 / (k + 1)
        assert quad == pytest.approx(exact, abs=1e-12)


def test_hermite_nodes_integrate_standard_normal_moments_exactly():
    """m-point Gauss-Hermite integrates standard-normal moments: E[x^k] = 0 (odd),
    (k-1)!! (even)."""
    m = 5
    nodes, weights = _gauss_nodes_weights("hermite", m)
    assert sum(weights) == pytest.approx(1.0)

    def double_factorial(k):  # (k-1)!! for even k
        r = 1.0
        j = k - 1
        while j > 1:
            r *= j
            j -= 2
        return r

    for k in range(2 * m):
        quad = sum(w * x**k for x, w in zip(nodes, weights))
        exact = 0.0 if k % 2 == 1 else double_factorial(k)
        assert quad == pytest.approx(exact, abs=1e-9)


# --- Exact recovery of a polynomial finding ------------------------------------


def _poly(sample):
    # Degree-2 finding: recovered exactly by degree >= 2.
    a, b = sample["a"], sample["b"]
    return 2.0 + 3.0 * a + a * b - 0.5 * b * b


_POLY_INPUTS = {"a": Uniform(-1.0, 1.0), "b": Uniform(-1.0, 1.0)}


def test_polynomial_finding_recovered_to_machine_precision():
    r = pce_fit(_POLY_INPUTS, _poly, degree=2, seed=1)
    assert r.fit_residual < 1e-10  # the surrogate IS the finding
    assert r.is_trustworthy()
    # Closed forms for a,b ~ U(-1,1): E[a^2]=1/3, Var(a^2)=4/45.
    assert r.mean == pytest.approx(2.0 - 0.5 / 3.0, abs=1e-9)  # 11/6
    assert r.variance == pytest.approx(3.0 + 1.0 / 9.0 + 1.0 / 45.0, abs=1e-9)  # 47/15


def test_surrogate_predict_reproduces_a_polynomial_finding():
    """predict() must equal the finding at arbitrary points for a polynomial -
    an arithmetic-independent check of the whole basis/coefficient machinery."""
    r = pce_fit(_POLY_INPUTS, _poly, degree=2, seed=1)
    for a, b in [(-0.9, 0.4), (0.1, -0.7), (0.5, 0.5), (-0.3, -0.2)]:
        s = {"a": a, "b": b}
        assert r.predict(s) == pytest.approx(_poly(s), abs=1e-10)


def test_higher_degree_still_exact_no_spurious_high_terms():
    """Fitting at degree 5 a degree-2 finding must still be exact - the extra
    coefficients must come out ~0, not inject noise."""
    r = pce_fit(_POLY_INPUTS, _poly, degree=5, seed=1)
    assert r.fit_residual < 1e-9
    assert r.variance == pytest.approx(3.0 + 1.0 / 9.0 + 1.0 / 45.0, abs=1e-8)


# --- Ishigami benchmark (analytic Sobol, the interaction case) -----------------


def _ishigami(s):
    return math.sin(s["x1"]) + 7.0 * math.sin(s["x2"]) ** 2 + 0.1 * s["x3"] ** 4 * math.sin(s["x1"])


_ISHIGAMI_INPUTS = {n: Uniform(-PI, PI) for n in ("x1", "x2", "x3")}


def test_ishigami_matches_analytic_variance_and_total_order():
    a, b = 7.0, 0.1
    D = a**2 / 8 + b * PI**4 / 5 + b**2 * PI**8 / 18 + 0.5
    v1 = 0.5 * (1 + b * PI**4 / 5) ** 2
    v2 = a**2 / 8
    v13 = 8 * b**2 * PI**8 / 225
    st = {"x1": (v1 + v13) / D, "x2": v2 / D, "x3": v13 / D}

    r = pce_fit(_ISHIGAMI_INPUTS, _ishigami, degree=10, seed=1)
    assert r.variance == pytest.approx(D, rel=1e-3)
    for name in ("x1", "x2", "x3"):
        assert r.total_order[name] == pytest.approx(st[name], abs=5e-3)


def test_ishigami_x3_is_pure_interaction():
    """x3 has ZERO first-order effect but a real total-order one (only via its
    interaction with x1). This is the case a first-order-only estimator botches."""
    r = pce_fit(_ISHIGAMI_INPUTS, _ishigami, degree=10, seed=1)
    assert r.first_order["x3"] == pytest.approx(0.0, abs=5e-3)
    assert r.total_order["x3"] > 0.2  # analytic ~0.244


# --- Agreement with the Monte Carlo surfaces on a smooth finding ---------------


def _smooth(s):
    return math.exp(0.3 * s["a"]) + 2.0 * s["b"] ** 2


_SMOOTH_INPUTS = {"a": Normal(mean=0.0, std=1.0), "b": Uniform(-1.0, 1.0)}


def test_pce_moments_agree_with_monte_carlo():
    pce = pce_fit(_SMOOTH_INPUTS, _smooth, degree=8, seed=1)
    assert pce.is_trustworthy()
    mc = monte_carlo(_SMOOTH_INPUTS, _smooth, n=40000, seed=7)
    assert pce.mean == pytest.approx(mc.mean, rel=0.02)
    assert pce.std == pytest.approx(mc.std, rel=0.05)


def test_pce_total_order_agrees_with_saltelli_sobol():
    pce = pce_fit(_SMOOTH_INPUTS, _smooth, degree=8, seed=1)
    sob = sobol_total_order(_SMOOTH_INPUTS, _smooth, n=20000, seed=7)
    for name in ("a", "b"):
        assert pce.total_order[name] == pytest.approx(sob.total_order[name], abs=0.03)


# --- The honesty guard: fit_residual must catch non-smoothness -----------------


def test_fit_residual_flags_a_kink_as_untrustworthy():
    """A finding with a kink (a min()/threshold - the repo's regime-switch shape)
    breaks spectral convergence. PCE must report an elevated fit_residual and
    is_trustworthy() == False rather than emit confident-but-wrong moments."""

    def kink(s):
        return max(0.0, s["a"] - 0.5) + 0.3 * s["b"]

    r = pce_fit({"a": Uniform(-1, 1), "b": Uniform(-1, 1)}, kink, degree=8, seed=1)
    assert r.fit_residual > 1e-2
    assert not r.is_trustworthy()


def test_fit_residual_near_zero_for_a_smooth_polynomial():
    r = pce_fit(_POLY_INPUTS, _poly, degree=3, seed=1)
    assert r.fit_residual < 1e-10
    assert r.is_trustworthy()


# --- Fixed inputs, unsupported inputs, bad returns -----------------------------


def test_fixed_input_is_held_and_excluded_from_the_basis():
    inputs = {"a": Uniform(-1, 1), "gap": Fixed(10.0)}
    r = pce_fit(inputs, lambda s: s["a"] + s["gap"], degree=3, seed=1)
    assert r.input_names == ("a",)  # gap is not an active dimension
    assert "gap" not in r.total_order
    assert r.mean == pytest.approx(10.0, abs=1e-9)  # E[a]=0, gap held at 10
    assert r.total_order["a"] == pytest.approx(1.0, abs=1e-9)


def test_all_fixed_inputs_is_a_constant():
    r = pce_fit({"x": Fixed(3.0), "y": Fixed(4.0)}, lambda s: s["x"] * s["y"], degree=3)
    assert r.mean == pytest.approx(12.0)
    assert r.variance == 0.0
    assert r.total_order == {}
    assert r.n_evaluations == 1


def test_unsupported_distribution_raises():
    with pytest.raises(NotImplementedError, match="Uniform and Normal"):
        pce_fit({"a": LogNormal(gmean=1.0, gstd=1.5)}, lambda s: s["a"], degree=3)


def test_nonfinite_finding_raises():
    with pytest.raises(ValueError, match="nan/inf"):
        pce_fit({"a": Uniform(0, 1)}, lambda s: float("inf"), degree=3)


def test_degree_must_be_at_least_one():
    with pytest.raises(ValueError, match="degree must be >= 1"):
        pce_fit({"a": Uniform(0, 1)}, lambda s: s["a"], degree=0)


# --- Cost + determinism (§7) ---------------------------------------------------


def test_evaluation_count_is_the_tensor_grid_plus_validation():
    calls = {"n": 0}

    def counted(s):
        calls["n"] += 1
        return _poly(s)

    r = pce_fit(_POLY_INPUTS, counted, degree=3, seed=1, validation=100)
    assert r.n_evaluations == (3 + 1) ** 2  # tensor grid, 2 active inputs
    assert r.n_validation == 100
    assert calls["n"] == (3 + 1) ** 2 + 100


def test_same_inputs_are_byte_identical():
    a = pce_fit(_SMOOTH_INPUTS, _smooth, degree=6, seed=42)
    b = pce_fit(_SMOOTH_INPUTS, _smooth, degree=6, seed=42)
    assert a.coefficients == b.coefficients
    assert (a.mean, a.variance, a.fit_residual) == (b.mean, b.variance, b.fit_residual)
    assert a.total_order == b.total_order


def test_quadrature_fit_is_seed_independent():
    """Only the validation sample uses the seed; the fitted coefficients (and thus
    the moments/indices) come from deterministic quadrature nodes."""
    a = pce_fit(_SMOOTH_INPUTS, _smooth, degree=6, seed=1, validation=0)
    b = pce_fit(_SMOOTH_INPUTS, _smooth, degree=6, seed=999, validation=0)
    assert a.coefficients == b.coefficients
