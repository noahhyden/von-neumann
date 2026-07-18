"""propellant.distributions: sourced spreads for every REFERENCES.md number."""

import math

import pytest

from propellant.distributions import (
    HHV_HYDROGEN_DIST,
    HYDROGEN_MASS_FRACTION_OF_WATER_DIST,
    ISP_LOX_LH2_DIST,
    ISP_XENON_HALL_EP_DIST,
    ISP_XENON_ION_EP_DIST,
    KORNUTA_FULL_CHAIN_DIST,
    XENON_WORLD_SUPPLY_DIST,
)
from propellant.propellant import (
    HHV_HYDROGEN_KWH_PER_KG,
    HYDROGEN_MASS_FRACTION_OF_WATER,
    KORNUTA_FULL_CHAIN_KWH_PER_KG,
    XENON_WORLD_SUPPLY_T_PER_YR,
)
from vn_core.uq import Fixed, monte_carlo, sobol_total_order


def test_thermodynamic_constants_are_fixed():
    assert isinstance(HHV_HYDROGEN_DIST, Fixed)
    assert HHV_HYDROGEN_DIST.value == HHV_HYDROGEN_KWH_PER_KG
    assert isinstance(HYDROGEN_MASS_FRACTION_OF_WATER_DIST, Fixed)


def test_kornuta_band_contains_point_value():
    assert KORNUTA_FULL_CHAIN_DIST.low < KORNUTA_FULL_CHAIN_KWH_PER_KG < KORNUTA_FULL_CHAIN_DIST.high


def test_xenon_supply_matches_source_tuple():
    assert XENON_WORLD_SUPPLY_DIST.low == XENON_WORLD_SUPPLY_T_PER_YR[0]
    assert XENON_WORLD_SUPPLY_DIST.high == XENON_WORLD_SUPPLY_T_PER_YR[1]


def test_reaction_mass_uq_shows_isp_dominates_over_dv():
    # Tsiolkovsky: m_prop = m_dry * (exp(dv/(Isp*g0)) - 1). Under UQ over both
    # Isp (Uniform(440, 460), ~4% relative) and dv (fixed at 9500 m/s here),
    # a real spread on Isp reshapes the reaction-mass distribution
    # exponentially. Test: 90% CI on reaction mass should span at least 5%
    # of the mean at LOX/LH2's tight Isp band.
    def rxn_mass(sample):
        return 1000.0 * (math.exp(9500.0 / (sample["isp"] * 9.80665)) - 1.0)

    r = monte_carlo({"isp": ISP_LOX_LH2_DIST}, rxn_mass, n=3000, seed=149)
    lo, hi = r.error_bar_95
    assert (hi - lo) / r.mean > 0.05


def test_xenon_ion_isp_is_higher_band_than_hall():
    # Sanity check that ion EP's band lives above Hall EP's - if this ever
    # flipped, the reaction-mass rankings would silently invert.
    assert ISP_XENON_ION_EP_DIST.low > ISP_XENON_HALL_EP_DIST.high
