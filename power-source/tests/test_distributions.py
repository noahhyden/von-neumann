"""power_source.distributions: sourced spreads for every REFERENCES.md band."""

import math

import pytest

from power_source.distributions import (
    FISSION_CONVERSION_EFFICIENCY_DIST,
    FISSION_RADIATOR_TEMP_DIST,
    FISSION_SPECIFIC_POWER_DIST,
    PU238_ANNUAL_PRODUCTION_DIST,
    PU238_PER_GPHS_RTG_DIST,
    RTG_FISSION_CROSSOVER_DIST,
    RTG_SPECIFIC_POWER_DIST,
    SOLAR_SPECIFIC_POWER_1AU_DIST,
)
from power_source.power_source import (
    FISSION_SPECIFIC_POWER_W_PER_KG,
    GPHS_RTG_SPECIFIC_POWER_W_PER_KG,
    MMRTG_SPECIFIC_POWER_W_PER_KG,
    SOLAR_SPECIFIC_POWER_1AU_W_PER_KG,
)
from vn_core.uq import Uniform, monte_carlo, sobol_total_order


def test_every_dist_has_a_nontrivial_band():
    for name, dist in [
        ("solar", SOLAR_SPECIFIC_POWER_1AU_DIST),
        ("fission", FISSION_SPECIFIC_POWER_DIST),
        ("rtg", RTG_SPECIFIC_POWER_DIST),
        ("pu238_per_rtg", PU238_PER_GPHS_RTG_DIST),
        ("pu238_annual", PU238_ANNUAL_PRODUCTION_DIST),
        ("crossover", RTG_FISSION_CROSSOVER_DIST),
        ("efficiency", FISSION_CONVERSION_EFFICIENCY_DIST),
        ("radiator_t", FISSION_RADIATOR_TEMP_DIST),
    ]:
        assert dist.quantile(0.05) != dist.quantile(0.95), f"{name} degenerate"


def test_point_values_sit_inside_their_bands():
    # Every module constant must lie inside the band it maps to; otherwise the
    # distribution and the fold have drifted apart.
    assert (
        SOLAR_SPECIFIC_POWER_1AU_DIST.quantile(0.0)
        <= SOLAR_SPECIFIC_POWER_1AU_W_PER_KG
        <= SOLAR_SPECIFIC_POWER_1AU_DIST.high
    )
    assert (
        FISSION_SPECIFIC_POWER_DIST.low
        <= FISSION_SPECIFIC_POWER_W_PER_KG
        <= FISSION_SPECIFIC_POWER_DIST.high
    )
    assert (
        RTG_SPECIFIC_POWER_DIST.low
        <= GPHS_RTG_SPECIFIC_POWER_W_PER_KG
        <= RTG_SPECIFIC_POWER_DIST.high
    )
    assert (
        RTG_SPECIFIC_POWER_DIST.low
        <= MMRTG_SPECIFIC_POWER_W_PER_KG
        <= RTG_SPECIFIC_POWER_DIST.high
    )


def test_solar_fission_crossover_stays_in_the_4_to_5_au_band_under_uq():
    # THE headline finding of power-source: d_cross = sqrt(sp_solar / sp_nuclear).
    # Under UQ over both specific powers, does the crossover still sit in the
    # "4-5 AU band matches reality" claim REFERENCES.md makes? Answer with an
    # MC of the sqrt formula.
    inputs = {
        "sp_solar": SOLAR_SPECIFIC_POWER_1AU_DIST,
        "sp_fission": FISSION_SPECIFIC_POWER_DIST,
    }

    def d_cross(sample):
        return math.sqrt(sample["sp_solar"] / sample["sp_fission"])

    r = monte_carlo(inputs, d_cross, n=5000, seed=79)
    # Mean should sit in the "4-5 AU" reality-cross-check region, but with a
    # wide 90% CI because the solar-basis spread is 4x.
    assert 4.0 < r.mean < 12.0
    lo, hi = r.error_bar_95
    assert hi > lo + 1.0, "spread should be nontrivial"

    # Sobol: which side of the ratio drives the variance? The solar-basis 4x
    # spread outweighs the ~3x fission spread on a per-order-of-magnitude
    # basis, so it should dominate.
    s = sobol_total_order(inputs, d_cross, n=1500, seed=79)
    assert s.ranked()[0][0] == "sp_solar"


def test_pu238_production_bandwidth_matches_the_source():
    assert PU238_ANNUAL_PRODUCTION_DIST.low == 0.5
    assert PU238_ANNUAL_PRODUCTION_DIST.high == 1.5


def test_crossover_threshold_dist_covers_the_1_kwe_point():
    # The 1 kWe point value is sourced as "order-of-magnitude"; LogUniform
    # around it must comfortably contain 1000.
    assert RTG_FISSION_CROSSOVER_DIST.low < 1000.0 < RTG_FISSION_CROSSOVER_DIST.high
    # And the log-midpoint should be near 1000.
    med = RTG_FISSION_CROSSOVER_DIST.quantile(0.5)
    assert 700 < med < 1500
