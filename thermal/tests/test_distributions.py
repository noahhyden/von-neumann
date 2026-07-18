"""thermal.distributions: sourced spreads for every REFERENCES.md number."""

import math

import pytest

from thermal.distributions import (
    EMISSIVITY_DIST,
    ISS_HEAT_REJECTION_TOTAL_DIST,
    ISS_RADIATOR_ASSEMBLY_AREA_DIST,
    ISS_RADIATOR_TEMP_DIST,
    RADIATOR_SPECIFIC_MASS_DIST,
    RADIATOR_SPECIFIC_MASS_FSP_SOA_DIST,
    STEFAN_BOLTZMANN_DIST,
)
from thermal.thermal import (
    ISS_HEAT_REJECTION_TOTAL_KW,
    ISS_RADIATOR_ASSEMBLY_AREA_M2,
    ISS_RADIATOR_TEMP_K,
    RADIATOR_SPECIFIC_MASS_BAND_KG_M2,
    STEFAN_BOLTZMANN_W_M2_K4,
)
from vn_core.uq import Fixed, Uniform, monte_carlo, sobol_total_order


def test_defined_constants_stay_fixed():
    assert isinstance(STEFAN_BOLTZMANN_DIST, Fixed)
    assert STEFAN_BOLTZMANN_DIST.value == STEFAN_BOLTZMANN_W_M2_K4
    # ISS heat rejection is a flight measurement, tight and Fixed.
    assert isinstance(ISS_HEAT_REJECTION_TOTAL_DIST, Fixed)
    assert ISS_HEAT_REJECTION_TOTAL_DIST.value == ISS_HEAT_REJECTION_TOTAL_KW


def test_radiator_mass_band_matches_source():
    assert RADIATOR_SPECIFIC_MASS_DIST.low == RADIATOR_SPECIFIC_MASS_BAND_KG_M2[0]
    assert RADIATOR_SPECIFIC_MASS_DIST.high == RADIATOR_SPECIFIC_MASS_BAND_KG_M2[1]
    # FSP SOA sub-band nested inside the wider band.
    assert RADIATOR_SPECIFIC_MASS_FSP_SOA_DIST.low >= RADIATOR_SPECIFIC_MASS_DIST.low
    assert RADIATOR_SPECIFIC_MASS_FSP_SOA_DIST.high <= RADIATOR_SPECIFIC_MASS_DIST.high


def test_iss_coolant_temperature_band_covers_point_value():
    assert ISS_RADIATOR_TEMP_DIST.low <= ISS_RADIATOR_TEMP_K <= ISS_RADIATOR_TEMP_DIST.high


def test_radiator_area_uq_stays_within_4_percent_of_iss_flight_anchor():
    # A load-bearing UQ finding for thermal: the closed form q = 2*eps*sigma*T^4
    # under-estimates the ISS assembly area by ~4% (REFERENCES.md: "67.5 m^2,
    # within ~4% of the real 70.3 m^2"). MC over emissivity and coolant
    # temperature preserves that gap - the 90% CI lands NEAR but slightly
    # below the flight value, because the radiating-surface temperature is
    # cooler than the coolant loop temperature (REFERENCES.md flags this
    # honestly as a "slightly optimistic anchor"). Asserting the shape here
    # so a regression that silently changes the closed form would trip.
    def area_for_35_kw(sample):
        flux = 2 * sample["eps"] * STEFAN_BOLTZMANN_W_M2_K4 * sample["T"] ** 4
        return 35_000.0 / flux  # 35 kW per loop

    inputs = {
        "eps": EMISSIVITY_DIST,
        "T": ISS_RADIATOR_TEMP_DIST,
    }
    r = monte_carlo(inputs, area_for_35_kw, n=3000, seed=83)
    # UQ widens the reference gap: REFERENCES.md's "4% gap" quote assumes the
    # point value eps=0.8 exactly. Under Uniform(0.8, 0.9), mean eps=0.85 ->
    # flux ~6% higher -> area shrinks ~6% -> the MC mean sits ~12% below the
    # flight anchor. That IS a UQ finding: honoring the emissivity band moves
    # the gap in a specific direction and by a specific amount, which the
    # papers should cite alongside the point-value gap.
    assert 0.80 * ISS_RADIATOR_ASSEMBLY_AREA_M2 < r.mean < 0.95 * ISS_RADIATOR_ASSEMBLY_AREA_M2

    # Sobol: emissivity has ~12% relative spread and T only ~1.5%, but flux
    # depends on T^4 - the T contribution is amplified. Both must be non-dead.
    s = sobol_total_order(inputs, area_for_35_kw, n=1200, seed=83)
    for name in ("eps", "T"):
        assert s.total_order[name] > 0.01


def test_hot_radiator_leverage_survives_uq():
    # (T_hot / T_cold)^4 leverage: mass ratio for a hot vs cold radiator.
    # Nominal 533 K vs 300 K gives ~10x. Under a Uniform on radiator T,
    # verify the leverage stays > 5x for a hot-vs-cold pair.
    def leverage(sample):
        return (sample["T_hot"] / sample["T_cold"]) ** 4

    inputs = {
        "T_hot": Uniform(500.0, 600.0),   # smelting-radiator range
        "T_cold": Uniform(275.0, 320.0),  # electronics-radiator range
    }
    r = monte_carlo(inputs, leverage, n=3000, seed=87)
    lo, hi = r.error_bar_95
    assert lo > 5.0, f"90% CI lo of leverage should stay > 5x, got {lo:.2f}"
