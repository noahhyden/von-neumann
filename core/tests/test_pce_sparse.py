"""Validation for the Smolyak sparse-grid PCE quadrature (method="sparse").

Claims under attack:
- *exact on polynomials*: like tensor quadrature, the sparse rule integrates the
  pseudospectral projection exactly for a finding that is a polynomial up to the
  truncation degree (mean/variance/coefficients to machine precision);
- *agrees with tensor* on a smooth non-polynomial finding (Ishigami indices);
- *cheaper in moderate dimension*: at d=5 it uses far fewer model calls than the
  (degree+1)^d tensor grid;
- *works across adapters* (Legendre / Hermite / arbitrary), is deterministic, and its
  predict() surrogate is exact on a polynomial.
"""

from __future__ import annotations

import math

import pytest

from vn_core.uq import LogNormal, Normal, Uniform, pce_fit

PI = math.pi
_A, _B = 7.0, 0.1
_ISH = {n: Uniform(-PI, PI) for n in ("x1", "x2", "x3")}


def _ishigami(s):
    return math.sin(s["x1"]) + _A * math.sin(s["x2"]) ** 2 + _B * s["x3"] ** 4 * math.sin(s["x1"])


def _poly5(s):
    return 2.0 + 3.0 * s["x0"] - s["x1"] * s["x2"] + 0.5 * s["x4"] ** 2


_POLY5_INPUTS = {f"x{i}": Uniform(-1.0, 1.0) for i in range(5)}


def test_sparse_recovers_polynomial_exactly():
    r = pce_fit(_POLY5_INPUTS, _poly5, degree=2, method="sparse", validation=64)
    # E[poly5] = 2 + 0 - 0 + 0.5 * E[x4^2] = 2 + 0.5 * (1/3) = 13/6.
    assert r.mean == pytest.approx(13.0 / 6.0, abs=1e-12)
    assert r.fit_residual < 1e-10  # exact fit on a polynomial in-span
    assert r.is_trustworthy()


def test_sparse_matches_tensor_on_ishigami():
    tensor = pce_fit(_ISH, _ishigami, degree=8, method="quadrature", validation=0)
    sparse = pce_fit(_ISH, _ishigami, degree=8, method="sparse", validation=0)
    for k in _ISH:
        assert sparse.total_order[k] == pytest.approx(tensor.total_order[k], abs=0.01)
    assert sparse.variance == pytest.approx(tensor.variance, rel=0.02)


def test_sparse_is_cheaper_at_moderate_dimension():
    sparse = pce_fit(_POLY5_INPUTS, _poly5, degree=2, method="sparse", validation=0)
    tensor = pce_fit(_POLY5_INPUTS, _poly5, degree=2, method="quadrature", validation=0)
    assert sparse.n_evaluations < tensor.n_evaluations
    assert tensor.n_evaluations == 3**5  # (degree+1)^d


def test_sparse_predict_is_exact_on_polynomial():
    r = pce_fit(_POLY5_INPUTS, _poly5, degree=2, method="sparse", validation=0)
    for sample in (
        {"x0": 0.3, "x1": -0.7, "x2": 0.1, "x3": 0.9, "x4": -0.4},
        {"x0": -0.9, "x1": 0.2, "x2": -0.5, "x3": 0.0, "x4": 0.8},
    ):
        assert r.predict(sample) == pytest.approx(_poly5(sample), abs=1e-9)


def test_sparse_works_across_adapters():
    # Legendre (Uniform), Hermite (Normal), arbitrary (LogNormal) in one fit.
    inp = {"u": Uniform(-1.0, 1.0), "g": Normal(0.0, 1.0), "ln": LogNormal(1.0, 1.2)}
    f = lambda s: s["u"] ** 2 + s["g"] + 0.1 * s["ln"]  # noqa: E731
    r = pce_fit(inp, f, degree=3, method="sparse", validation=128)
    # E[u^2]=1/3, E[g]=0, mean ~ 1/3 + 0.1*E[ln]
    assert r.is_trustworthy()
    assert set(r.total_order) == {"u", "g", "ln"}


def test_sparse_is_deterministic():
    a = pce_fit(_POLY5_INPUTS, _poly5, degree=2, method="sparse", validation=0)
    b = pce_fit(_POLY5_INPUTS, _poly5, degree=2, method="sparse", validation=0)
    assert a.coefficients == b.coefficients


def test_sparse_handles_fixed_inputs():
    from vn_core.uq import Fixed

    inp = {"a": Uniform(-1.0, 1.0), "const": Fixed(5.0), "b": Uniform(-1.0, 1.0)}
    f = lambda s: s["a"] ** 2 + s["const"] + s["b"]  # noqa: E731
    r = pce_fit(inp, f, degree=2, method="sparse", validation=0)
    # const contributes only to the mean: 1/3 + 5 + 0.
    assert r.mean == pytest.approx(1.0 / 3.0 + 5.0, abs=1e-12)
    assert set(r.input_names) == {"a", "b"}  # Fixed is not an active dimension


def test_sparse_golden_values_are_bit_reproducible():
    inp = {"a": Uniform(-1.0, 1.0), "b": Normal(0.0, 1.0), "c": Uniform(0.0, 2.0)}
    f = lambda s: s["a"] ** 2 + s["b"] * s["c"] + 0.5 * s["a"] * s["b"]  # noqa: E731
    r = pce_fit(inp, f, degree=3, method="sparse", validation=0)
    assert r.mean == 0.3333333333333334
    assert r.variance == 1.5055555555555535
    assert r.n_evaluations == 69
    assert r.total_order["a"] == 0.1143911439114389


def test_pce_rejects_unknown_method():
    with pytest.raises(ValueError, match="quadrature.*sparse.*regression"):
        pce_fit(_POLY5_INPUTS, _poly5, degree=2, method="bogus")
