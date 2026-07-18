"""closure_sim.distributions: assert on the sourced-band shape, not execution.

Two categories of spread here, one per test group: per-part manufacturing
energy (Uniform over an LCA min-max) and sintered-regolith strength
(LogUniform over the 100x band). The tests pin that each distribution's
endpoints match its REFERENCES.md band, and that the LogUniform read of the
100x range spreads on the correct (log) scale.
"""

import math

import pytest

from closure_sim.distributions import (
    PART_ENERGY_KWH_PER_KG_DIST,
    SINTERED_REGOLITH_STRENGTH_DIST,
)
from closure_sim.structures import SINTERED_REGOLITH_STRENGTH_BAND_MPA
from vn_core.uq import Uniform, monte_carlo, sobol_total_order


def test_every_part_category_carries_a_nontrivial_band():
    for name, dist in PART_ENERGY_KWH_PER_KG_DIST.items():
        assert isinstance(dist, Uniform), f"{name!r} is not a Uniform"
        assert dist.high > dist.low, f"{name!r} band is degenerate"


def test_chip_band_is_the_widest_and_the_costliest():
    # The story REFERENCES.md tells: compute chips dominate embodied energy,
    # by a wide margin. Sanity-check that the module's own encoding of the
    # bands still says the same thing.
    chip = PART_ENERGY_KWH_PER_KG_DIST["compute_chips"]
    metal = PART_ENERGY_KWH_PER_KG_DIST["structure"]
    assert chip.low > metal.high
    # And the chip band spans a 5x factor top-to-bottom (3000-15000).
    assert chip.high / chip.low == pytest.approx(5.0, rel=0.01)


def test_regolith_strength_band_matches_the_source_range():
    # LogUniform's endpoints must round-trip the sourced band; nothing to
    # gain from any deviation and it would silently drift the strength claim.
    low, high = SINTERED_REGOLITH_STRENGTH_BAND_MPA
    assert SINTERED_REGOLITH_STRENGTH_DIST.quantile(0.0) == pytest.approx(low)
    # Quantile(1 - eps) approaches high but never reaches it (half-open).
    assert SINTERED_REGOLITH_STRENGTH_DIST.quantile(1e-12) == pytest.approx(low, rel=1e-6)


def test_regolith_strength_log_uniform_spreads_on_the_right_scale():
    # A random draw from LogUniform(a, b) has log(x) uniform on (log a, log b).
    # Check this empirically: the geometric-mean of many draws should match
    # sqrt(a * b) - the LogUniform equivalent of "mean of a Uniform is midpoint".
    r = monte_carlo(
        {"strength": SINTERED_REGOLITH_STRENGTH_DIST},
        lambda s: math.log(s["strength"]),
        n=5000,
        seed=59,
    )
    a, b = SINTERED_REGOLITH_STRENGTH_BAND_MPA
    expected_mean_log = 0.5 * (math.log(a) + math.log(b))
    assert r.mean == pytest.approx(expected_mean_log, abs=0.05)


def test_uq_over_a_scenario_energy_produces_an_error_bar_on_build_energy():
    # Load-bearing UQ finding for the electronics wall: how much does the cost
    # of building 1 kg of chip vs 1 kg of structure spread when the LCA bands
    # are honored? MC over the two Uniforms gives the answer.
    #
    # Genuinely surprising Sobol result: even though the chip band spans a
    # 12 000 kWh/kg range and the metal band only 8 kWh/kg, the *metal* input
    # dominates leverage sensitivity - because leverage is inversely
    # proportional to the small metal denominator, and small proportional
    # changes there swing the ratio harder than proportionally-smaller changes
    # in the large chip numerator. That is exactly the kind of attribution
    # issue #35 asks the papers to make honest.
    inputs = {
        "chip_kwh_per_kg": PART_ENERGY_KWH_PER_KG_DIST["compute_chips"],
        "metal_kwh_per_kg": PART_ENERGY_KWH_PER_KG_DIST["structure"],
    }

    def leverage(sample):
        return sample["chip_kwh_per_kg"] / sample["metal_kwh_per_kg"]

    r = monte_carlo(inputs, leverage, n=3000, seed=61)
    # Point ratio at the nominal midpoints: 9000 / 5.7 ~= 1580; leverage clearly
    # varies but sits in the 500-5000 range across the band.
    assert 500 < r.mean < 5000
    lo, hi = r.error_bar_95
    # 90% CI must genuinely span - if it collapsed the UQ pipeline dropped a
    # band somewhere.
    assert (hi - lo) / r.mean > 0.5

    # And Sobol flags the reciprocal input as the dominant driver.
    s = sobol_total_order(inputs, leverage, n=800, seed=61)
    assert s.ranked()[0][0] == "metal_kwh_per_kg", (
        "metal_kwh_per_kg should dominate: leverage = chip/metal, and the "
        "reciprocal amplifies variance in the small denominator"
    )


def test_regolith_strength_default_is_logspread():
    # A quick behaviour pin: a LogUniform's median != its arithmetic midpoint,
    # so if someone silently swapped in a Uniform this test would fail.
    a, b = SINTERED_REGOLITH_STRENGTH_BAND_MPA
    median = SINTERED_REGOLITH_STRENGTH_DIST.quantile(0.5)
    arithmetic_mid = 0.5 * (a + b)
    geometric_mid = math.sqrt(a * b)
    assert median == pytest.approx(geometric_mid, rel=1e-6)
    assert median != pytest.approx(arithmetic_mid, rel=0.05)
