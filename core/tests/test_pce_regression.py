"""Red-hat + validation for regression PCE (the higher-dimension fit method).

`pce_fit(..., method="regression")` fits the same orthonormal PCE by least squares
over sampled points instead of tensor Gauss quadrature, so it scales polynomially
(not exponentially) in the number of inputs. The claims under attack:

- it **recovers the same answer** as quadrature where both are feasible, and a
  polynomial finding exactly (to machine precision - proving the orthonormal-basis
  normal equations are well-conditioned);
- it **scales**: on a high-dimensional finding it fits from ~oversampling*n_terms
  runs where quadrature would need (degree+1)^d;
- it stays **honest** - the fit_residual (measured on an *independent* sample, not
  the fit sample) still flags a non-smooth finding;
- eval count is exactly as advertised, it is deterministic (§7), and degenerate
  requests (too few samples) raise rather than silently return garbage.
"""

from __future__ import annotations

import math
from math import comb

import pytest

from vn_core.uq import Uniform, pce_fit

PI = math.pi


# --- Exact recovery + agreement with quadrature --------------------------------

_A = [1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
_A12 = 0.5
_POLY_INPUTS = {f"x{i}": Uniform(-1.0, 1.0) for i in range(8)}


def _poly8(s):
    xs = [s[f"x{i}"] for i in range(8)]
    return sum(_A[i] * xs[i] for i in range(8)) + _A12 * xs[0] * xs[1]


def _analytic_poly8():
    var = sum(ai**2 / 3 for ai in _A) + _A12**2 / 9
    st = {}
    for i in range(8):
        num = _A[i] ** 2 / 3 + (_A12**2 / 9 if i in (0, 1) else 0.0)
        st[f"x{i}"] = num / var
    return var, st


def test_regression_recovers_a_polynomial_to_machine_precision():
    """A degree-2 polynomial in 8 inputs, fit by regression at degree 2, must be
    recovered essentially exactly - moments and Sobol - from ~2*n_terms samples."""
    var_an, st_an = _analytic_poly8()
    r = pce_fit(_POLY_INPUTS, _poly8, degree=2, method="regression", seed=1)
    assert r.fit_residual < 1e-10
    assert r.variance == pytest.approx(var_an, rel=1e-9)
    for name, s in st_an.items():
        assert r.total_order[name] == pytest.approx(s, abs=1e-9)


def test_regression_scales_where_quadrature_cannot():
    """The whole point: fit a d=8 finding from far fewer runs than quadrature's
    (degree+1)^d."""
    r = pce_fit(_POLY_INPUTS, _poly8, degree=2, method="regression", seed=1)
    quadrature_cost = (2 + 1) ** 8  # 6561
    assert r.n_evaluations < quadrature_cost // 10
    assert r.method == "regression"


def test_regression_agrees_with_quadrature_on_low_dimension():
    """Where both are feasible (d=3 Ishigami), the two methods must give the same
    variance and Sobol indices to within regression sampling noise."""
    ish_inputs = {n: Uniform(-PI, PI) for n in ("x1", "x2", "x3")}

    def ishigami(s):
        return math.sin(s["x1"]) + 7 * math.sin(s["x2"]) ** 2 + 0.1 * s["x3"] ** 4 * math.sin(s["x1"])

    q = pce_fit(ish_inputs, ishigami, degree=10, method="quadrature")
    r = pce_fit(ish_inputs, ishigami, degree=10, method="regression", seed=1)
    assert r.variance == pytest.approx(q.variance, rel=0.02)
    for name in ("x1", "x2", "x3"):
        assert r.total_order[name] == pytest.approx(q.total_order[name], abs=0.02)
        assert r.first_order[name] == pytest.approx(q.first_order[name], abs=0.02)


def test_regression_predict_reproduces_the_polynomial():
    r = pce_fit(_POLY_INPUTS, _poly8, degree=2, method="regression", seed=1)
    for probe_seed in (11, 22, 33):
        import random

        rng = random.Random(probe_seed)
        s = {f"x{i}": rng.uniform(-1, 1) for i in range(8)}
        assert r.predict(s) == pytest.approx(_poly8(s), abs=1e-9)


# --- Cost, determinism, contract ----------------------------------------------


def test_regression_eval_count_is_oversampling_times_terms():
    d = 8
    n_terms = comb(2 + d, d)
    calls = {"n": 0}

    def counted(s):
        calls["n"] += 1
        return _poly8(s)

    r = pce_fit(_POLY_INPUTS, counted, degree=2, method="regression", oversampling=2.0, seed=1, validation=100)
    assert r.n_evaluations == math.ceil(2.0 * n_terms)
    assert calls["n"] == r.n_evaluations + 100  # fit + validation


def test_regression_respects_explicit_n_samples():
    r = pce_fit(_POLY_INPUTS, _poly8, degree=2, method="regression", n_samples=300, seed=1, validation=0)
    assert r.n_evaluations == 300


def test_regression_underdetermined_raises():
    n_terms = comb(2 + 8, 8)  # 45
    with pytest.raises(ValueError, match="more samples than basis terms"):
        pce_fit(_POLY_INPUTS, _poly8, degree=2, method="regression", n_samples=n_terms - 5, seed=1)


def test_regression_is_deterministic():
    a = pce_fit(_POLY_INPUTS, _poly8, degree=2, method="regression", seed=7)
    b = pce_fit(_POLY_INPUTS, _poly8, degree=2, method="regression", seed=7)
    assert a.coefficients == b.coefficients
    assert (a.variance, a.fit_residual) == (b.variance, b.fit_residual)


def test_regression_different_seed_changes_the_sample_but_not_the_answer():
    """Different sampling seed -> different design points -> essentially the same
    recovered polynomial (it is overdetermined and the finding is exact)."""
    a = pce_fit(_POLY_INPUTS, _poly8, degree=2, method="regression", seed=1, validation=0)
    b = pce_fit(_POLY_INPUTS, _poly8, degree=2, method="regression", seed=2, validation=0)
    assert a.coefficients != b.coefficients  # different design points
    assert a.variance == pytest.approx(b.variance, rel=1e-9)  # same exact recovery


# --- Honesty guard survives the regression path -------------------------------


def test_regression_fit_residual_flags_a_kink():
    """The fit_residual is measured on an independent sample (seed+1), so a kink
    still trips it even though regression is overdetermined."""

    def kink(s):
        return max(0.0, s["a"] - 0.5) + 0.3 * s["b"]

    r = pce_fit({"a": Uniform(-1, 1), "b": Uniform(-1, 1)}, kink, degree=8, method="regression", seed=1)
    assert r.fit_residual > 1e-2
    assert not r.is_trustworthy()


def test_regression_rejects_nonfinite():
    with pytest.raises(ValueError, match="nan/inf"):
        pce_fit({"a": Uniform(0, 1)}, lambda s: float("nan"), degree=3, method="regression", seed=1)


def test_unknown_method_raises():
    with pytest.raises(ValueError, match="quadrature.*regression"):
        pce_fit({"a": Uniform(0, 1)}, lambda s: s["a"], degree=2, method="lstsq")
