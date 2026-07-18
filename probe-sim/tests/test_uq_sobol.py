"""Sobol total-order indices: assert attribution, not execution.

The tests below pin the four properties from issue #35's validation list applied
to sensitivity analysis: (1) indices sum close to 1, (2) a genuinely dominant
input dominates, (3) a Fixed / non-contributing input reads as ~0, and (4) the
estimator is deterministic under seeding.

Analytic reference: for an additive model f = sum_i g_i(X_i) with independent
X_i, first-order and total-order Sobol indices coincide and sum exactly to 1.
For an interactive model f = X_1 * X_2 the sum exceeds 1 because interactions
are counted in each participating input's total-order index.
"""

import math

import pytest

from probe_sim.uq.distributions import Fixed, Normal, Uniform
from probe_sim.uq.sobol import sobol_total_order


def linear_additive(sample):
    return sample["a"] + sample["b"] + sample["c"]


def multiplicative(sample):
    return sample["a"] * sample["b"]


def test_additive_indices_sum_to_one():
    # Three independent Uniform(0, 1)s, each contributing Var = 1/12. Total-order
    # indices should each be ~1/3 and sum to ~1 (this is a *closed* case where
    # sum-to-1 is exact in the population; sampling error at n=2000 keeps this
    # a soft assertion).
    inputs = {
        "a": Uniform(0.0, 1.0),
        "b": Uniform(0.0, 1.0),
        "c": Uniform(0.0, 1.0),
    }
    r = sobol_total_order(inputs, linear_additive, n=2000, seed=13)
    total = sum(r.total_order.values())
    assert total == pytest.approx(1.0, abs=0.10)
    for v in r.total_order.values():
        assert v == pytest.approx(1.0 / 3.0, abs=0.08)


def test_dominant_input_actually_dominates():
    # Same additive model but "a" has 100x the variance. Its S_T should approach 1
    # and the others should be near 0. Big gap, so ranking is stable.
    inputs = {
        "a": Uniform(low=-5.0, high=5.0),  # var = 100/12 ~= 8.33
        "b": Uniform(low=-0.5, high=0.5),  # var = 1/12 ~= 0.083
        "c": Uniform(low=-0.5, high=0.5),
    }
    r = sobol_total_order(inputs, linear_additive, n=2000, seed=17)
    assert r.total_order["a"] > 0.90
    assert r.total_order["b"] < 0.05
    assert r.total_order["c"] < 0.05
    top_name, _ = r.ranked()[0]
    assert top_name == "a"


def test_fixed_input_registers_as_zero_contribution():
    # If an input is a Fixed (spread = 0), it cannot drive variance; the
    # estimator should read its S_T at ~0. This is the "honest [GAP]" property:
    # we do not conjure sensitivity where there is no spread.
    inputs = {
        "a": Uniform(low=-1.0, high=1.0),
        "b": Uniform(low=-1.0, high=1.0),
        "constant": Fixed(value=42.0),
    }

    def add_with_constant(s):
        return s["a"] + s["b"] + s["constant"]

    r = sobol_total_order(inputs, add_with_constant, n=1500, seed=23)
    assert r.total_order["constant"] == pytest.approx(0.0, abs=0.01)


def test_multiplicative_model_indices_can_exceed_one():
    # f = a * b with a, b ~ Uniform(1, 3). Total-order for each is E[a^2]*Var(b)/Var(f)
    # + Var(a)*Var(b)/Var(f) etc.; the sum exceeds 1 because the interaction is
    # attributed to both inputs. This test doesn't pin an exact value - it pins
    # the *shape* (both nonzero, sum > 1 within sampling slack).
    inputs = {
        "a": Uniform(low=1.0, high=3.0),
        "b": Uniform(low=1.0, high=3.0),
    }
    r = sobol_total_order(inputs, multiplicative, n=2000, seed=29)
    assert r.total_order["a"] > 0.3
    assert r.total_order["b"] > 0.3
    total = r.total_order["a"] + r.total_order["b"]
    assert total > 1.0
    assert total < 1.5  # loose upper bound, not a claim


def test_deterministic_same_seed():
    inputs = {"a": Uniform(0.0, 1.0), "b": Normal(0.0, 1.0)}
    finding = lambda s: s["a"] + s["b"]  # noqa: E731 - inline for one-shot use
    r1 = sobol_total_order(inputs, finding, n=500, seed=31)
    r2 = sobol_total_order(inputs, finding, n=500, seed=31)
    assert r1.total_order == r2.total_order
    assert r1.variance == r2.variance


def test_evaluation_count_matches_the_advertised_cost():
    # Documented cost is n * (K + 2). If this stops holding a caller planning
    # around evaluation budget will be silently misled.
    inputs = {"a": Uniform(0, 1), "b": Uniform(0, 1), "c": Uniform(0, 1)}
    evals = 0

    def counting(sample):
        nonlocal evals
        evals += 1
        return sample["a"] + sample["b"] + sample["c"]

    r = sobol_total_order(inputs, counting, n=100, seed=1)
    assert r.n_evaluations == 100 * (3 + 2)
    assert evals == r.n_evaluations


def test_probe_range_sobol_ranks_efficiency_as_dominant():
    # The realistic probe-sim finding from test_uq_sample: max heliocentric
    # distance for a solar-electric probe. Efficiency has a factor-of-1.14 range
    # (0.28-0.32); TSI has +/- 0.5 on 1360.8, a factor-of-1.0004 range. So
    # efficiency should dominate S_T by orders of magnitude - this is the
    # concrete "which input drives the finding" claim UQ has to make honestly.
    def finding(sample):
        return math.sqrt(
            sample["S0"] * sample["area_m2"] * sample["efficiency"]
            / sample["required_power_w"]
        )

    inputs = {
        "S0": Normal(mean=1360.8, std=0.5),
        "efficiency": Uniform(low=0.28, high=0.32),
        "area_m2": Fixed(200.0),
        "required_power_w": Fixed(208_000.0),
    }
    r = sobol_total_order(inputs, finding, n=1500, seed=37)
    ranked = r.ranked()
    assert ranked[0][0] == "efficiency"
    assert r.total_order["efficiency"] > 0.95
    assert r.total_order["S0"] < 0.05
    assert r.total_order["area_m2"] == pytest.approx(0.0, abs=0.005)
    assert r.total_order["required_power_w"] == pytest.approx(0.0, abs=0.005)


def test_degenerate_constant_finding_returns_zero_indices():
    # A finding that ignores its inputs has no variance; every S_T must be 0
    # (and the estimator must not divide by zero).
    inputs = {"a": Uniform(0, 1), "b": Uniform(0, 1)}
    r = sobol_total_order(inputs, lambda s: 3.14, n=100, seed=41)
    assert r.variance == 0.0
    assert all(v == 0.0 for v in r.total_order.values())


def test_sobol_rejects_bad_n_and_empty_inputs():
    with pytest.raises(ValueError):
        sobol_total_order({"a": Uniform(0, 1)}, lambda s: s["a"], n=1, seed=1)
    with pytest.raises(ValueError):
        sobol_total_order({}, lambda s: 0.0, n=100, seed=1)
