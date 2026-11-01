"""Red-hat (adversarial) tests: things that would go wrong SILENTLY."""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pytest

from closure_sim.models import Factory, ReplicationParams, Subsystem

from probe_sim.environment import SolarArray
from probe_sim.range import is_viable_at, operational_range
from vn_core.uq.distributions import Fixed, LogNormal, Normal, Uniform
from vn_core.uq.sample import monte_carlo
from vn_core.uq.sobol import sobol_total_order


def test_mc_bytes_survive_a_fresh_subprocess():
    # Cross-process byte-identity: catches any wall-clock or unseeded RNG that would silently drift results between runs.
    script = (
        "from vn_core.uq.distributions import Normal, Fixed;"
        "from vn_core.uq.sample import monte_carlo;"
        "r = monte_carlo({'S0': Normal(1360.8, 0.5), 'd': Fixed(5.203)},"
        " lambda s: s['S0'] / s['d']**2, n=200, seed=42);"
        "import sys; sys.stdout.write(repr(r.values[:5]))"
    )
    out = subprocess.check_output([sys.executable, "-c", script], text=True)
    # Recompute in-process and compare.
    r = monte_carlo(
        {"S0": Normal(1360.8, 0.5), "d": Fixed(5.203)},
        lambda s: s["S0"] / s["d"] ** 2,
        n=200,
        seed=42,
    )
    assert out == repr(r.values[:5])


def test_mc_golden_head_of_stream():
    # TRUE golden: pre-recorded values, so any change to RNG threading, quantile math or iteration order trips this and must be regenerated deliberately.
    r = monte_carlo(
        {"S0": Normal(1360.8, 0.5), "d": Fixed(5.203)},
        lambda s: s["S0"] / s["d"] ** 2,
        n=10,
        seed=42,
    )
    expected_head = (
        50.27401855363882,
        50.256387288382896,
        50.27910840695209,
        50.29029554653985,
        50.26378800768964,
    )
    assert r.values[:5] == expected_head


def test_sobol_bounds_are_respected_on_a_zero_contribution_case():
    # An input in the dict that the finding never reads: S_T must be ~0, and crucially must not go significantly negative from estimator noise.
    inputs = {
        "a": Uniform(0.0, 1.0),
        "phantom": Normal(mean=0.0, std=1e6),  # huge spread, but unused
    }

    def finding(s):
        return s["a"]  # phantom is silently unused

    r = sobol_total_order(inputs, finding, n=1500, seed=101)
    assert r.total_order["phantom"] == pytest.approx(0.0, abs=0.01)
    # Bound: within a small sampling slack of 0, never <-0.02.
    assert r.total_order["phantom"] > -0.02
    # And "a" carries essentially all the variance.
    assert r.total_order["a"] > 0.95


def test_sobol_key_order_does_not_change_ranking_or_values():
    # Reordering the input dict should give up to a sampling-noise-sized change in each S_T (because the uniform stream is consumed in dict order, so the exact draws differ).
    def_finding = lambda s: s["a"] * 3.0 + s["b"] * 1.0  # a dominates  # noqa: E731

    fwd = sobol_total_order(
        {"a": Uniform(0.0, 1.0), "b": Uniform(0.0, 1.0)}, def_finding, n=2000, seed=103
    )
    rev = sobol_total_order(
        {"b": Uniform(0.0, 1.0), "a": Uniform(0.0, 1.0)}, def_finding, n=2000, seed=103
    )
    # Rankings by input name identity, not by position.
    assert fwd.ranked()[0][0] == "a"
    assert rev.ranked()[0][0] == "a"
    # Values match to within sampling slack.
    assert fwd.total_order["a"] == pytest.approx(rev.total_order["a"], abs=0.08)
    assert fwd.total_order["b"] == pytest.approx(rev.total_order["b"], abs=0.08)


def test_sobol_total_order_beats_first_order_on_pure_interaction():
    # f = X_1 * X_2 with X_i ~ Uniform(-1, 1) has zero-mean marginals, so first-order indices read ~0 and only the total-order estimator credits ~0.5 to each input.
    def finding(s):
        return s["x1"] * s["x2"]

    r = sobol_total_order(
        {"x1": Uniform(-1.0, 1.0), "x2": Uniform(-1.0, 1.0)},
        finding,
        n=3000,
        seed=113,
    )
    assert r.total_order["x1"] > 0.30
    assert r.total_order["x2"] > 0.30


def test_mc_does_not_bleed_state_across_calls():
    # Bug pattern: caching the RNG on module state across monte_carlo calls would make the second call depend on the first.
    inputs = {"a": Uniform(0.0, 1.0)}
    _ = monte_carlo(inputs, lambda s: s["a"], n=100, seed=7)  # spuriously first
    _ = monte_carlo(inputs, lambda s: s["a"] * 2, n=50, seed=99)  # different finding
    a = monte_carlo(inputs, lambda s: s["a"], n=100, seed=7)
    b = monte_carlo(inputs, lambda s: s["a"], n=100, seed=7)
    assert a.values == b.values


def test_normal_extreme_tail_stays_finite():
    # u very close to 1 pushes erfinv toward infinity, so the extreme tail must still return a finite number.
    d = Normal(mean=0.0, std=1.0)
    for u in [0.999, 0.9999, 0.99999, 0.999999]:
        v = d.quantile(u)
        assert math.isfinite(v)
        assert v > 0.0


def test_mc_propagates_finding_exception():
    # If a finding raises on a particular sample, MC should NOT swallow it.
    class Sentinel(Exception):
        pass

    def brittle(sample):
        if sample["x"] > 0.99:
            raise Sentinel("this input is impossible")
        return sample["x"]

    # Uniform(0, 1) hits >0.99 with prob 0.01, so n=1000 makes at least one trigger virtually certain.
    with pytest.raises(Sentinel):
        monte_carlo({"x": Uniform(0.0, 1.0)}, brittle, n=1000, seed=61)


def test_mc_quantile_boundary_values_are_exact():
    # A degenerate check on the internal quantile helper via a full MC call: the min/max of a monotone finding over sampled inputs must equal the (approximate) analytic min/max.
    r = monte_carlo({"x": Uniform(0.0, 1.0)}, lambda s: s["x"], n=5000, seed=71)
    assert min(r.values) < 0.01
    assert max(r.values) > 0.99
    # q05 and q95 should bracket the true 0.05 / 0.95 quantiles of Uniform(0,1).
    assert r.q05 == pytest.approx(0.05, abs=0.02)
    assert r.q95 == pytest.approx(0.95, abs=0.02)


def test_sobol_all_fixed_inputs_are_zero_not_nan():
    # If every input is Fixed, variance is 0 and each S_Ti is 0/0, so the honest answer is zeros, not nan or a divide-by-zero.
    inputs = {"a": Fixed(1.0), "b": Fixed(2.0), "c": Fixed(3.0)}
    r = sobol_total_order(inputs, lambda s: s["a"] + s["b"] * s["c"], n=100, seed=73)
    assert r.variance == 0.0
    for v in r.total_order.values():
        assert v == 0.0
        assert not math.isnan(v)


def _synthetic_factory() -> Factory:
    return Factory(
        name="synthetic-uq-probe",
        subsystems=[
            Subsystem(
                name="structure",
                mass_kg=1000.0,
                category="structure",
                producible_locally=True,
                energy_to_produce_kwh_per_kg=100.0,
            ),
            Subsystem(
                name="chips",
                mass_kg=100.0,
                category="electronics",
                producible_locally=False,
            ),
        ],
    )


def _synthetic_rep() -> ReplicationParams:
    return ReplicationParams(
        seed_mass_kg=1000.0,
        local_build_rate_kg_per_day=10.0,
        vitamin_resupply_mass_kg=1000.0,
        resupply_cadence_days=30.0,
        available_power_kw=1000.0,
        target_output_kg_per_day=50.0,
        duration_days=3650,
        dt_days=1.0,
    )


def test_range_solar_constant_actually_reaches_the_fold():
    # BUG-CATCH TEST: if solar_constant is not threaded end-to-end through is_viable_at -> available_power_kw -> array.power_w, then doubling it would silently change nothing (default is used) and the assertion below would trip.
    array = SolarArray(area_m2=200.0, efficiency=0.30)
    factory, rep = _synthetic_factory(), _synthetic_rep()

    # At a distance where the default TSI leaves the probe underpowered, but a 4x TSI would push it into viability.
    d_marginal_high = 1.5  # AU: past the default-TSI viability crossover
    assert not is_viable_at(array, factory, rep, d_marginal_high)
    assert is_viable_at(array, factory, rep, d_marginal_high, solar_constant=8 * 1360.8)


def test_operational_range_moves_with_solar_constant():
    # Same idea, one level up: the bisection endpoint (operational_range_au) must scale with sqrt(solar_constant) - a doubled TSI gives a sqrt(2)~=1.414 further reach.
    array = SolarArray(area_m2=200.0, efficiency=0.30)
    factory, rep = _synthetic_factory(), _synthetic_rep()

    base = operational_range(array, factory, rep, tol_au=1e-3).operational_range_au
    doubled = operational_range(
        array, factory, rep, tol_au=1e-3, solar_constant=2 * 1360.8
    ).operational_range_au
    assert base is not None and doubled is not None
    assert doubled == pytest.approx(math.sqrt(2.0) * base, rel=0.01)


def test_honest_null_point_answer_is_overconfident():
    # THE POINT of issue #35, stated in one test: "UQ is a filter, not polish".
    threshold_au = 0.63

    def d_max(s):
        return math.sqrt(
            s["S0"] * s["area_m2"] * s["efficiency"] / s["required_power_w"]
        )

    point = math.sqrt(1360.8 * 200.0 * 0.30 / 208_000.0)
    assert point < threshold_au, "test scenario requires the point answer to say NO"

    r = monte_carlo(
        {
            "S0": Normal(1360.8, 0.5),
            "efficiency": Uniform(0.28, 0.32),
            "area_m2": Fixed(200.0),
            "required_power_w": Fixed(208_000.0),
        },
        d_max,
        n=10_000,
        seed=91,
    )
    # The 95th percentile must sit above the threshold - i.e., a plausible realization DOES reach 0.63.
    assert r.q95 > threshold_au
    # Empirical P(d >= threshold) far from 0 or 1: the honest-null test.
    p_reaches = sum(1 for v in r.values if v >= threshold_au) / r.n
    assert 0.20 < p_reaches < 0.60, (
        f"expected the answer to be genuinely uncertain; got P(reach)={p_reaches:.2f}"
    )


def test_monte_carlo_over_lognormal_gives_finite_result():
    # LogNormal is exercised at the quantile level in test_uq_distributions but never through a full MC.
    inputs = {"x": LogNormal(gmean=100.0, gstd=1.10)}
    r = monte_carlo(inputs, lambda s: s["x"], n=5000, seed=93)
    assert all(math.isfinite(v) and v > 0 for v in r.values)
    # Geometric mean of the samples estimates gmean.
    geo_mean = math.exp(sum(math.log(v) for v in r.values) / r.n)
    assert geo_mean == pytest.approx(100.0, rel=0.02)


def test_uq_module_imports_no_pimas():
    # CLAUDE.md §7 rule: the fold and its UQ wrapper carry ZERO pimas imports.
    import re

    pat = re.compile(r"^\s*(from\s+pimas|import\s+pimas)\b", re.MULTILINE)
    uq_dir = Path(__file__).resolve().parent.parent / "src" / "probe_sim" / "uq"
    for py in uq_dir.glob("*.py"):
        text = py.read_text()
        assert not pat.search(text), f"{py.name} imports pimas"
