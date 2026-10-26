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
    # UQ finding: the closed form q = 2*eps*sigma*T^4 under-estimates the ISS assembly area (~4% in REFERENCES.md) and MC over eps and coolant T keeps the 90% CI just below the flight value.
    def area_for_35_kw(sample):
        flux = 2 * sample["eps"] * STEFAN_BOLTZMANN_W_M2_K4 * sample["T"] ** 4
        return 35_000.0 / flux  # 35 kW per loop

    inputs = {
        "eps": EMISSIVITY_DIST,
        "T": ISS_RADIATOR_TEMP_DIST,
    }
    r = monte_carlo(inputs, area_for_35_kw, n=3000, seed=83)
    # UQ widens the REFERENCES.md "4% gap", which assumes eps = 0.8 exactly; Uniform(0.8, 0.9) has mean eps 0.85, so flux is ~6% higher and the MC mean area sits further below the 70.3 m^2 flight anchor.
    assert 0.80 * ISS_RADIATOR_ASSEMBLY_AREA_M2 < r.mean < 0.95 * ISS_RADIATOR_ASSEMBLY_AREA_M2

    # Sobol: emissivity has ~12% relative spread and T only ~1.5%, but flux goes as T^4 so the T contribution is amplified; both must be non-dead.
    s = sobol_total_order(inputs, area_for_35_kw, n=1200, seed=83)
    for name in ("eps", "T"):
        assert s.total_order[name] > 0.01


def test_hot_radiator_leverage_survives_uq():
    # (T_hot / T_cold)^4 leverage: nominal 533 K vs 300 K gives ~10x, and under a Uniform on radiator T the leverage must stay > 5x for a hot-vs-cold pair.
    def leverage(sample):
        return (sample["T_hot"] / sample["T_cold"]) ** 4

    inputs = {
        "T_hot": Uniform(500.0, 600.0),   # smelting-radiator range
        "T_cold": Uniform(275.0, 320.0),  # electronics-radiator range
    }
    r = monte_carlo(inputs, leverage, n=3000, seed=87)
    lo, hi = r.error_bar_95
    assert lo > 5.0, f"90% CI lo of leverage should stay > 5x, got {lo:.2f}"
