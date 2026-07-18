"""assembly.distributions: sourced spreads for every REFERENCES.md band."""

import pytest

from assembly.distributions import (
    HOURS_PER_DAY_DIST,
    LPBF_RATE_DIST,
    TYPICAL_OEE_DIST,
    WAAM_RATE_DIST,
    WORLD_CLASS_OEE_DIST,
)
from assembly.rate import (
    LPBF_RATE_KG_PER_H,
    TYPICAL_OEE,
    WAAM_RATE_KG_PER_H,
    WORLD_CLASS_OEE,
)
from vn_core.uq import Fixed, Uniform, monte_carlo, sobol_total_order


def test_definitional_and_flight_anchors_are_fixed():
    assert isinstance(HOURS_PER_DAY_DIST, Fixed)


def test_deposition_rate_bands_match_source_tuples():
    assert WAAM_RATE_DIST.low == WAAM_RATE_KG_PER_H[0]
    assert WAAM_RATE_DIST.high == WAAM_RATE_KG_PER_H[1]
    assert LPBF_RATE_DIST.low == LPBF_RATE_KG_PER_H[0]
    assert LPBF_RATE_DIST.high == LPBF_RATE_KG_PER_H[1]


def test_waam_dominates_over_lpbf_in_throughput():
    # A sanity finding: WAAM's low is above LPBF's high (roughly). If a
    # regression flipped these, downstream doubling-clock predictions would
    # swing 10x.
    assert WAAM_RATE_DIST.low >= LPBF_RATE_DIST.high * 0.7


def test_oee_bands_bracket_point_values():
    assert WORLD_CLASS_OEE_DIST.low <= WORLD_CLASS_OEE <= WORLD_CLASS_OEE_DIST.high
    assert TYPICAL_OEE_DIST.low <= TYPICAL_OEE <= TYPICAL_OEE_DIST.high


def test_build_rate_uq_dominated_by_deposition_rate_not_oee():
    # Build rate = deposition_rate * OEE * hours_per_day. Under UQ over both,
    # deposition rate has a 10x band (WAAM 1-10) while OEE has ~10% relative
    # spread. Sobol should flag deposition rate as dominant driver.
    inputs = {
        "rate": WAAM_RATE_DIST,
        "oee": WORLD_CLASS_OEE_DIST,
    }

    def kg_per_day(sample):
        return sample["rate"] * sample["oee"] * 24.0

    s = sobol_total_order(inputs, kg_per_day, n=1000, seed=163)
    assert s.ranked()[0][0] == "rate"
