"""Validation for second-order (pairwise interaction) Sobol indices.

sobol_total_order / uq_and_gsa gain second_order=True, which estimates S_ij for each
input pair from the extra "BA" matrices. Claims under attack:

- *correct*: on Ishigami the only real interaction is x1-x3 (S_13 ~ 0.244, equal to
  x3's total-order since x3 has no main effect); x1-x2 and x2-x3 are ~0;
- *honest CIs*: the S_13 CI brackets the analytic value and the zero interactions'
  CIs straddle 0;
- *the right cost*: N*(2K+2) evaluations, and it does not perturb the first/total
  point estimates (those use only A and AB);
- *opt-in and deterministic*: None unless requested; byte-reproducible.
"""

from __future__ import annotations

import math

import pytest

from vn_core.uq import Uniform, sobol_total_order, uq_and_gsa

PI = math.pi
_A, _B = 7.0, 0.1
_ISH = {n: Uniform(-PI, PI) for n in ("x1", "x2", "x3")}


def _ishigami(s):
    return math.sin(s["x1"]) + _A * math.sin(s["x2"]) ** 2 + _B * s["x3"] ** 4 * math.sin(s["x1"])


_D = _A**2 / 8 + _B * PI**4 / 5 + _B**2 * PI**8 / 18 + 0.5
_S13 = (8 * _B**2 * PI**8 / 225) / _D  # ~0.244, the only nonzero Ishigami interaction


def test_second_order_matches_ishigami_analytic():
    r = sobol_total_order(_ISH, _ishigami, n=8000, seed=1, second_order=True)
    assert r.second_order[("x1", "x3")] == pytest.approx(_S13, abs=0.05)
    assert r.second_order[("x1", "x2")] == pytest.approx(0.0, abs=0.05)
    assert r.second_order[("x2", "x3")] == pytest.approx(0.0, abs=0.05)


def test_second_order_cis_are_honest():
    r = sobol_total_order(_ISH, _ishigami, n=8000, seed=1, second_order=True)
    lo, hi = r.second_order_ci[("x1", "x3")]
    assert lo <= _S13 <= hi  # brackets the real interaction
    zlo, zhi = r.second_order_ci[("x1", "x2")]
    assert zlo <= 0.0 <= zhi  # a non-interaction reads as "CI straddles 0"


def test_second_order_evaluation_count_is_2k_plus_2():
    calls = {"n": 0}

    def counted(s):
        calls["n"] += 1
        return _ishigami(s)

    n, k = 200, 3
    r = sobol_total_order(_ISH, counted, n=n, seed=1, second_order=True)
    assert r.n_evaluations == n * (2 * k + 2) == calls["n"]


def test_second_order_is_none_by_default():
    r = sobol_total_order(_ISH, _ishigami, n=200, seed=1)
    assert r.second_order is None
    assert r.second_order_ci is None


def test_second_order_does_not_perturb_first_and_total():
    """Enabling second-order adds the BA matrices but must not change the first/total
    point estimates - those depend only on A and AB, which are identical."""
    base = sobol_total_order(_ISH, _ishigami, n=500, seed=2)
    withso = sobol_total_order(_ISH, _ishigami, n=500, seed=2, second_order=True)
    assert base.total_order == withso.total_order
    assert base.first_order == withso.first_order


def test_second_order_pair_keys_are_input_order():
    r = sobol_total_order(_ISH, _ishigami, n=100, seed=1, second_order=True)
    assert list(r.second_order.keys()) == [("x1", "x2"), ("x1", "x3"), ("x2", "x3")]


def test_second_order_is_deterministic():
    a = sobol_total_order(_ISH, _ishigami, n=256, seed=5, second_order=True)
    b = sobol_total_order(_ISH, _ishigami, n=256, seed=5, second_order=True)
    assert a.second_order == b.second_order
    assert a.second_order_ci == b.second_order_ci


def test_second_order_with_sobol_sampler_golden():
    """Bit-reproducibility for the second-order estimator under the (seed-independent)
    Sobol' sampler - pins exact values so a silent estimator change is a red test."""
    inp = {"a": Uniform(0.0, 1.0), "b": Uniform(0.0, 1.0), "c": Uniform(0.0, 1.0)}
    f = lambda s: s["a"] + 2 * s["b"] + 3 * s["a"] * s["b"]  # noqa: E731
    r = sobol_total_order(inp, f, n=128, seed=0, sampler="sobol", second_order=True)
    assert r.second_order[("a", "b")] == 0.0392749031666721
    assert r.second_order[("a", "c")] == -0.00018170970588359404
    assert r.second_order[("b", "c")] == 0.008744142762567436


def test_second_order_constant_finding_is_zero():
    """A constant finding has zero variance: every interaction index is honestly 0
    (the var==0 path), not a divide-by-zero."""
    inp = {"a": Uniform(0.0, 1.0), "b": Uniform(0.0, 1.0)}
    r = sobol_total_order(inp, lambda s: 3.0, n=32, seed=1, second_order=True)
    assert r.second_order == {("a", "b"): 0.0}
    assert r.second_order_ci == {("a", "b"): (0.0, 0.0)}
    assert r.variance == 0.0


def test_uq_and_gsa_second_order():
    a = uq_and_gsa(_ISH, _ishigami, n=4000, seed=1, second_order=True)
    assert a.gsa.second_order[("x1", "x3")] == pytest.approx(_S13, abs=0.06)
    assert a.uq.mean == pytest.approx(_A / 2.0, abs=0.1)
