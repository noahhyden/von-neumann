"""Red-hat (adversarial) + validation tests for the unified UQ+GSA surface.

`uq_and_gsa` runs one Saltelli design and reads two answers off it: the output
distribution (UQ) and the total-order Sobol indices (GSA). The whole claim is
that the UQ is *free* - it reuses the evaluations Sobol already does, adding zero
model calls and introducing no numeric drift in the GSA it used to compute alone.

These tests attack that claim on the cases where a bug would look plausible:
- the "free" claim is really a promise about **evaluation count** - pin it exactly;
- the refactor must leave `sobol_total_order` **byte-identical** - pin it;
- the free UQ must be a **real** MC estimate, not an approximation - tie it to a
  closed form and to a standalone `monte_carlo`;
- degenerate/dishonest inputs (constant finding, a phantom input, a nonfinite
  return) must be handled the same honest way the separate surfaces handle them;
- same seed -> byte-identical, no wall-clock leak (§7).
"""

from __future__ import annotations

import math

import pytest

from vn_core.uq import (
    Fixed,
    Normal,
    Uniform,
    monte_carlo,
    sobol_total_order,
    uq_and_gsa,
)

_INPUTS = {"a": Normal(mean=1.0, std=0.2), "b": Uniform(low=0.0, high=1.0)}


def _linear(sample):
    # Additive (no interaction): total-order == first-order, and both are exactly
    # each input's variance share. Gives a closed form to test against.
    return 3.0 * sample["a"] + 0.5 * sample["b"]


# --- The headline claim: UQ is free (zero extra evaluations) -------------------


def test_free_uq_costs_zero_extra_evaluations():
    """uq_and_gsa must call the finding exactly N*(K+2) times - same as a Sobol
    run alone. If it were secretly running a separate MC for the UQ, the count
    would be higher. This is the entire point of the surface."""
    n, k = 500, len(_INPUTS)
    calls = {"n": 0}

    def counted(sample):
        calls["n"] += 1
        return _linear(sample)

    uq_and_gsa(_INPUTS, counted, n=n, seed=7)
    assert calls["n"] == n * (k + 2) == 2000


def test_unified_is_cheaper_than_separate_mc_plus_sobol():
    """The unified surface must cost strictly fewer evaluations than running a
    standalone monte_carlo and a standalone sobol on the same design size."""
    n, k, m = 400, len(_INPUTS), 400
    counts = {}
    for label, run in (
        ("uni", lambda f: uq_and_gsa(_INPUTS, f, n=n, seed=1)),
        ("mc", lambda f: monte_carlo(_INPUTS, f, n=m, seed=1)),
        ("sob", lambda f: sobol_total_order(_INPUTS, f, n=n, seed=1)),
    ):
        c = {"n": 0}

        def counted(s, _c=c):
            _c["n"] += 1
            return _linear(s)

        run(counted)
        counts[label] = c["n"]
    assert counts["uni"] == n * (k + 2)
    assert counts["uni"] < counts["mc"] + counts["sob"]


# --- The refactor must not move the Sobol numbers ------------------------------


def test_gsa_is_byte_identical_to_standalone_sobol():
    """Extracting the shared Saltelli evaluator must leave sobol_total_order's
    output bit-for-bit unchanged - the free UQ is an addition, not a rewrite."""
    sob = sobol_total_order(_INPUTS, _linear, n=600, seed=99)
    ana = uq_and_gsa(_INPUTS, _linear, n=600, seed=99)
    assert ana.gsa.total_order == sob.total_order
    assert ana.gsa.variance == sob.variance
    assert ana.gsa.mean == sob.mean
    assert (ana.gsa.n, ana.gsa.n_evaluations) == (sob.n, sob.n_evaluations)


# --- The free UQ must be a real MC estimate, not a fudge -----------------------


def test_free_uq_carries_2n_samples():
    ana = uq_and_gsa(_INPUTS, _linear, n=300, seed=3)
    assert ana.uq.n == 2 * 300
    assert len(ana.uq.values) == 2 * 300


def test_uq_mean_equals_gsa_mean_exactly():
    """UQ and GSA are read off the same 2N A+B samples, so their means are the
    same float, not just close."""
    ana = uq_and_gsa(_INPUTS, _linear, n=500, seed=11)
    assert ana.uq.mean == ana.gsa.mean


def test_linear_finding_uq_and_gsa_both_match_closed_form():
    """One run, two answers, both pinned to analytic ground truth:
    Var(3a + 0.5b) = 9 Var(a) + 0.25 Var(b); additivity => S_T is the variance
    share of each input."""
    sa = 0.2
    var_f = 9 * sa**2 + 0.25 * (1.0 / 12.0)  # Var(Uniform(0,1)) = 1/12
    st_a = 9 * sa**2 / var_f
    st_b = (0.25 / 12.0) / var_f

    ana = uq_and_gsa(_INPUTS, _linear, n=8000, seed=12345)
    assert ana.uq.std == pytest.approx(math.sqrt(var_f), rel=0.03)
    assert ana.gsa.total_order["a"] == pytest.approx(st_a, abs=0.02)
    assert ana.gsa.total_order["b"] == pytest.approx(st_b, abs=0.02)
    # Additive finding: total-order indices sum to ~1.
    assert sum(ana.gsa.total_order.values()) == pytest.approx(1.0, abs=0.03)


def test_free_uq_matches_a_standalone_monte_carlo():
    """The UQ from the Saltelli A+B samples must agree with an independent
    monte_carlo of the same size - it is the same estimator on iid draws."""
    ana = uq_and_gsa(_INPUTS, _linear, n=4000, seed=21)
    mc = monte_carlo(_INPUTS, _linear, n=8000, seed=777)  # 2N, different seed
    # Different seeds -> different draws, so agreement is statistical, not exact.
    assert ana.uq.mean == pytest.approx(mc.mean, rel=0.02)
    assert ana.uq.q05 == pytest.approx(mc.q05, rel=0.03)
    assert ana.uq.q95 == pytest.approx(mc.q95, rel=0.03)


# --- Degenerate / adversarial inputs handled honestly --------------------------


def test_phantom_input_gets_zero_sensitivity_without_corrupting_uq():
    """An input the finding ignores must read S_T ~ 0, and its presence must not
    change the output distribution (a spread with no path to the output)."""
    with_phantom = dict(_INPUTS, phantom=Normal(mean=5.0, std=3.0))
    ana = uq_and_gsa(with_phantom, _linear, n=4000, seed=5)
    assert ana.gsa.total_order["phantom"] == pytest.approx(0.0, abs=0.01)
    assert ana.gsa.total_order["phantom"] > -0.02  # estimator noise, not wrong-sign

    # UQ spread must match the no-phantom run's spread (phantom carries no signal).
    base = uq_and_gsa(_INPUTS, _linear, n=4000, seed=5)
    assert ana.uq.std == pytest.approx(base.uq.std, rel=0.05)


def test_constant_finding_is_zero_variance_everywhere_no_crash():
    """A finding with no output variance: GSA reports zeros (no divide-by-zero),
    UQ reports a spike (all quantiles equal the mean, std 0)."""
    ana = uq_and_gsa(_INPUTS, lambda s: 42.0, n=200, seed=1)
    assert ana.gsa.variance == 0.0
    assert all(v == 0.0 for v in ana.gsa.total_order.values())
    assert ana.uq.std == 0.0
    assert ana.uq.q05 == ana.uq.q50 == ana.uq.q95 == 42.0
    assert ana.uq.mean == 42.0


def test_nonfinite_finding_is_rejected():
    """A nan/inf return is not honest UQ - uq_and_gsa must raise, like
    monte_carlo does, rather than emit nan error bars and nan indices."""
    with pytest.raises(ValueError, match="nan/inf"):
        uq_and_gsa(_INPUTS, lambda s: float("nan"), n=50, seed=1)


def test_single_input_takes_all_the_sensitivity():
    ana = uq_and_gsa({"a": Normal(mean=0.0, std=1.0)}, lambda s: 2.0 * s["a"], n=4000, seed=2)
    assert ana.gsa.total_order["a"] == pytest.approx(1.0, abs=0.02)


def test_fixed_input_contributes_no_variance():
    """A Fixed input (a [GAP] with no sourced spread) must read S_T ~ 0 - the
    honest 'UQ does not know this input's spread' outcome."""
    inputs = {"a": Normal(mean=1.0, std=0.2), "gap": Fixed(3.0)}
    ana = uq_and_gsa(inputs, lambda s: s["a"] + s["gap"], n=3000, seed=8)
    assert ana.gsa.total_order["gap"] == pytest.approx(0.0, abs=1e-9)
    assert ana.gsa.total_order["a"] == pytest.approx(1.0, abs=0.02)


# --- Determinism (§7) ----------------------------------------------------------


def test_same_seed_is_byte_identical():
    a = uq_and_gsa(_INPUTS, _linear, n=400, seed=1234)
    b = uq_and_gsa(_INPUTS, _linear, n=400, seed=1234)
    assert a.uq.values == b.uq.values
    assert a.gsa.total_order == b.gsa.total_order
    assert (a.uq.mean, a.uq.std, a.uq.q05, a.uq.q95) == (b.uq.mean, b.uq.std, b.uq.q05, b.uq.q95)


def test_different_seed_changes_the_draws():
    a = uq_and_gsa(_INPUTS, _linear, n=400, seed=1)
    b = uq_and_gsa(_INPUTS, _linear, n=400, seed=2)
    assert a.uq.values != b.uq.values
