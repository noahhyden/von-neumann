"""Monte Carlo propagation: assert behavior, not execution.

The one discipline that silently breaks everything downstream is a random draw
that isn't seeded (CLAUDE.md §7). These tests pin: byte-identical determinism,
independence from dict-insertion accidents, error-bar shrinkage when spread
shrinks, and analytic sanity on cases with closed forms.
"""

import math

import pytest

from probe_sim.environment import solar_irradiance_w_m2
from probe_sim.uq.distributions import Fixed, Normal, Uniform
from probe_sim.uq.sample import monte_carlo


def irradiance_at_jupiter(sample):
    """Analytic finding: S0 / d^2 at Jupiter, spread from the sourced S0 std."""
    return solar_irradiance_w_m2(distance_au=sample["distance_au"], solar_constant=sample["S0"])


def test_same_seed_same_bytes():
    inputs = {
        "S0": Normal(mean=1360.8, std=0.5),
        "distance_au": Fixed(value=5.203),
    }
    a = monte_carlo(inputs, irradiance_at_jupiter, n=200, seed=42)
    b = monte_carlo(inputs, irradiance_at_jupiter, n=200, seed=42)
    assert a.values == b.values


def test_different_seed_different_values():
    inputs = {
        "S0": Normal(mean=1360.8, std=0.5),
        "distance_au": Fixed(value=5.203),
    }
    a = monte_carlo(inputs, irradiance_at_jupiter, n=200, seed=42)
    b = monte_carlo(inputs, irradiance_at_jupiter, n=200, seed=43)
    assert a.values != b.values
    # But the mean should be close either way, at N=200.
    assert a.mean == pytest.approx(b.mean, rel=0.02)


def test_mc_recovers_the_analytic_mean_and_std_for_pure_normal():
    # For finding = S0 * c with c constant, Var(finding) = c^2 * Var(S0).
    c = 1.0 / (5.203**2)
    inputs = {
        "S0": Normal(mean=1360.8, std=0.5),
        "distance_au": Fixed(value=5.203),
    }
    r = monte_carlo(inputs, irradiance_at_jupiter, n=10_000, seed=7)
    assert r.mean == pytest.approx(1360.8 * c, rel=1e-3)
    # Empirical std should match the analytic 0.5 * c to a few percent at N=10k.
    assert r.std == pytest.approx(0.5 * c, rel=0.03)


def test_error_bars_shrink_when_the_inputs_spread_shrinks():
    # THIS IS THE HEADLINE BEHAVIORAL TEST from issue #35: "error bars shrink when
    # an input's spread shrinks". If it fails, something upstream is not honest UQ.
    def_finding = irradiance_at_jupiter
    wide = monte_carlo(
        {"S0": Normal(mean=1360.8, std=5.0), "distance_au": Fixed(5.203)},
        def_finding,
        n=5000,
        seed=1,
    )
    narrow = monte_carlo(
        {"S0": Normal(mean=1360.8, std=0.5), "distance_au": Fixed(5.203)},
        def_finding,
        n=5000,
        seed=1,
    )
    tight = monte_carlo(
        {"S0": Normal(mean=1360.8, std=0.0), "distance_au": Fixed(5.203)},
        def_finding,
        n=5000,
        seed=1,
    )
    assert wide.std > narrow.std > tight.std
    assert tight.std == 0.0
    assert tight.mean == pytest.approx(1360.8 / (5.203**2), rel=1e-6)


def test_error_bar_bracket_median_and_quantiles_sane():
    inputs = {
        "S0": Normal(mean=1360.8, std=0.5),
        "distance_au": Fixed(5.203),
    }
    r = monte_carlo(inputs, irradiance_at_jupiter, n=5000, seed=3)
    lo, hi = r.error_bar_95
    assert lo < r.q50 < hi
    assert lo < r.mean < hi
    # 90% CI half-width should be close to 1.6449 * std for a Gaussian output.
    half = 0.5 * (hi - lo)
    assert half == pytest.approx(1.6449 * r.std, rel=0.05)


def test_quantiles_are_monotonic():
    inputs = {"S0": Uniform(low=1000, high=2000), "distance_au": Fixed(1.0)}
    r = monte_carlo(inputs, irradiance_at_jupiter, n=5000, seed=5)
    assert r.q05 < r.q50 < r.q95


def test_dict_insertion_order_does_not_change_reproducibility_shape():
    # Reordering keys changes which uniform gets pushed through which distribution,
    # so raw `values` will differ - but the empirical mean/std should not.
    a_inputs = {
        "S0": Normal(mean=1360.8, std=0.5),
        "distance_au": Fixed(5.203),
    }
    b_inputs = {
        "distance_au": Fixed(5.203),
        "S0": Normal(mean=1360.8, std=0.5),
    }
    a = monte_carlo(a_inputs, irradiance_at_jupiter, n=5000, seed=11)
    b = monte_carlo(b_inputs, irradiance_at_jupiter, n=5000, seed=11)
    # Same seed + same insertion order = byte-identical; reordering IS allowed to
    # produce a different stream (this is honest to the RNG model), but the
    # statistics of the finding shouldn't drift.
    assert a.mean == pytest.approx(b.mean, rel=1e-3)
    assert a.std == pytest.approx(b.std, rel=0.03)


def test_monte_carlo_rejects_bad_n():
    inputs = {"S0": Fixed(1.0)}
    with pytest.raises(ValueError):
        monte_carlo(inputs, lambda s: s["S0"], n=0, seed=1)


def test_monte_carlo_rejects_nonfinite_finding():
    inputs = {"x": Fixed(0.0)}
    with pytest.raises(ValueError):
        monte_carlo(inputs, lambda s: math.nan, n=10, seed=1)
    with pytest.raises(ValueError):
        monte_carlo(inputs, lambda s: math.inf, n=10, seed=1)


def test_probe_range_headline_uq_delivers_a_useful_error_bar():
    # A realistic probe-sim finding: max heliocentric distance for a 208 kW demand
    # on a 200 m^2 array with a cell efficiency in [0.28, 0.32] (Landis & Bailey
    # range) and TSI = 1360.8 +/- 0.5 (Kopp & Lean). Analytic finding:
    #   d = sqrt(S0 * area * eff / P)
    inputs = {
        "S0": Normal(mean=1360.8, std=0.5),
        "efficiency": Uniform(low=0.28, high=0.32),
        "area_m2": Fixed(200.0),
        "required_power_w": Fixed(208_000.0),
    }

    def finding(sample):
        # Closed form for max reach: d = sqrt(S0 * area * eff / P_req). Written
        # out from the sourced pieces so *every* sampled input actually flows
        # into the answer (contrast: SolarArray.max_distance_au reads the module
        # constant for S0 and would silently drop the sampled S0).
        return math.sqrt(
            sample["S0"] * sample["area_m2"] * sample["efficiency"]
            / sample["required_power_w"]
        )

    r = monte_carlo(inputs, finding, n=5000, seed=17)
    # Nominal at efficiency=0.30: d = sqrt(1360.8 * 200 * 0.30 / 208000) ~ 0.626 AU.
    assert r.mean == pytest.approx(0.626, abs=0.02)
    # Error bar should be nontrivial (efficiency spans a factor 32/28 ~ 14%,
    # so d spans a factor sqrt(1.14) ~ 1.07): std must be > 0 and much smaller
    # than the mean.
    assert 0.005 < r.std < 0.05
    lo, hi = r.error_bar_95
    assert lo > 0.55 and hi < 0.70


def test_probe_range_narrow_efficiency_shrinks_error_bar():
    # Same shape as above but with efficiency pinned. Error bar collapses to the
    # (tiny) TSI contribution only. This is the second half of the shrink-spread
    # validation, targeted at a *real* probe-sim finding.
    def finding(sample):
        return math.sqrt(
            sample["S0"] * sample["area_m2"] * sample["efficiency"]
            / sample["required_power_w"]
        )

    wide = monte_carlo(
        {
            "S0": Normal(1360.8, 0.5),
            "efficiency": Uniform(0.28, 0.32),
            "area_m2": Fixed(200.0),
            "required_power_w": Fixed(208_000.0),
        },
        finding,
        n=5000,
        seed=19,
    )
    narrow = monte_carlo(
        {
            "S0": Normal(1360.8, 0.5),
            "efficiency": Fixed(0.30),
            "area_m2": Fixed(200.0),
            "required_power_w": Fixed(208_000.0),
        },
        finding,
        n=5000,
        seed=19,
    )
    assert narrow.std < wide.std
    # With efficiency pinned, only TSI contributes: std ~ 0.5 * d / (2 * S0)
    # ~ 1.15e-4 AU. Must be tiny but positive.
    assert narrow.std < 5e-4
    assert narrow.std > 0
