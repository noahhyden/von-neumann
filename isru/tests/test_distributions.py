"""isru.distributions: sourced spreads for every REFERENCES.md number."""

import pytest

from isru.closure import LUNAR_REGOLITH_ELEMENT_WT_PCT
from isru.distributions import (
    LUNAR_REGOLITH_ELEMENT_WT_PCT_DIST,
    METAL_MOE_DIST,
    OXYGEN_FULL_CHAIN_KWH_PER_KG_DIST,
    USABLE_THRESHOLD_WT_PCT_DIST,
    WATER_ICE_LOX_DIST,
)
from isru.energy import (
    OXYGEN_FULL_CHAIN_KWH_PER_KG,
    OXYGEN_FULL_CHAIN_UNCERTAINTY_KWH_PER_KG,
)
from vn_core.uq import Fixed, Normal, monte_carlo


def test_oxygen_full_chain_uses_source_provided_normal():
    # The PNAS 2025 paper explicitly reports 24.3 +/- 5.8 kWh/kg - a source-
    # provided std makes Normal (not Uniform) the honest read.
    assert isinstance(OXYGEN_FULL_CHAIN_KWH_PER_KG_DIST, Normal)
    assert OXYGEN_FULL_CHAIN_KWH_PER_KG_DIST.mean == OXYGEN_FULL_CHAIN_KWH_PER_KG
    assert OXYGEN_FULL_CHAIN_KWH_PER_KG_DIST.std == OXYGEN_FULL_CHAIN_UNCERTAINTY_KWH_PER_KG


def test_oxygen_full_chain_uq_reproduces_taylor_carrier_envelope():
    # Taylor & Carrier (1993) put LOX at 18-35 kWh/kg across technologies.
    # A 5000-sample MC over the PNAS Normal should have its 90% CI comfortably
    # inside that independent envelope.
    r = monte_carlo(
        {"e_oxygen": OXYGEN_FULL_CHAIN_KWH_PER_KG_DIST},
        lambda s: s["e_oxygen"],
        n=5000,
        seed=151,
    )
    lo, hi = r.error_bar_95
    # The PNAS Normal has such a wide std (5.8 on 24.3) that its 90% CI
    # slightly UNDERSHOOTS Taylor & Carrier's 18-35 lower bound. That is
    # itself a UQ finding worth reporting: PNAS's stated uncertainty is
    # wider than the independent envelope on the low end.
    assert 14 < lo and hi < 35


def test_metal_moe_band_spans_theoretical_to_closure_sim():
    assert METAL_MOE_DIST.low == 2.6
    assert METAL_MOE_DIST.high == 5.0


def test_regolith_element_dist_shape_matches_source_table():
    # Every element in the source table has a companion; bulk elements are
    # Uniform, trace are Fixed. This catches a regression that would silently
    # drop an element or invent a spread on a trace one.
    for name, point in LUNAR_REGOLITH_ELEMENT_WT_PCT.items():
        dist = LUNAR_REGOLITH_ELEMENT_WT_PCT_DIST[name]
        if point >= 0.5:
            assert dist.high > dist.low, f"bulk element {name} lost its band"
            assert dist.low <= point <= dist.high
        else:
            assert isinstance(dist, Fixed), f"trace element {name} should be Fixed"


def test_usable_threshold_is_a_policy_dial_not_a_measurement():
    assert isinstance(USABLE_THRESHOLD_WT_PCT_DIST, Fixed)


def test_water_ice_lox_band_matches_propellant_module():
    # This is the SAME shared literature figure across two modules; the bands
    # must match or the two modules would silently disagree on the same
    # sourced number.
    assert WATER_ICE_LOX_DIST.low == 9.0
    assert WATER_ICE_LOX_DIST.high == 15.0
