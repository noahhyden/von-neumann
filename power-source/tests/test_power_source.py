"""power-source validation: the two crossovers, the Pu-238 wall, reactor radiator.

Anchors: solar ~100 W/kg (ROSA flight), fission ~6.7 W/kg (Kilopower 10 kWe), GPHS-RTG
5.2 W/kg / 8.1 kg Pu-238; Pu-238 production 0.5-1.5 kg/yr. See REFERENCES.md.
"""

import math

import pytest

from power_source.power_source import (
    FISSION_SPECIFIC_POWER_W_PER_KG,
    GPHS_RTG_SPECIFIC_POWER_W_PER_KG,
    PU238_PER_GPHS_RTG_KG,
    SOLAR_SPECIFIC_POWER_1AU_W_PER_KG,
    choose_source,
    crossover_distance_au,
    fission_reactor_radiator,
    pu238_required_kg,
    solar_specific_power_at,
    source_mass_kg,
    years_of_pu238_production,
)


def test_solar_specific_power_falls_as_inverse_square():
    assert solar_specific_power_at(1.0) == pytest.approx(100.0)
    assert solar_specific_power_at(5.2) == pytest.approx(100.0 / 5.2**2, rel=1e-9)
    # ~3.7 W/kg at Jupiter - well below any nuclear source.
    assert solar_specific_power_at(5.2) == pytest.approx(3.70, rel=1e-2)


def test_distance_crossover_is_4_to_5_au():
    # Against fission: sqrt(100/6.7) = 3.86 AU.
    d_fission = crossover_distance_au(100.0, FISSION_SPECIFIC_POWER_W_PER_KG)
    assert d_fission == pytest.approx(math.sqrt(100.0 / 6.7), rel=1e-9)
    assert d_fission == pytest.approx(3.86, rel=1e-2)
    # Against an RTG: sqrt(100/5.2) = 4.39 AU. Both land in the 4-5 AU band.
    d_rtg = crossover_distance_au(100.0, GPHS_RTG_SPECIFIC_POWER_W_PER_KG)
    assert d_rtg == pytest.approx(4.39, rel=1e-2)
    assert 3.5 < d_fission < 5.0 and 3.5 < d_rtg < 5.0


def test_crossover_is_independent_of_power_level():
    # At the crossover, solar mass == nuclear mass for ANY power level (P cancels).
    d_cross = crossover_distance_au(100.0, FISSION_SPECIFIC_POWER_W_PER_KG)
    sp_solar_at_cross = solar_specific_power_at(d_cross)
    # Solar specific power at the crossover equals the nuclear specific power.
    assert sp_solar_at_cross == pytest.approx(FISSION_SPECIFIC_POWER_W_PER_KG, rel=1e-9)
    for power in (200.0, 1000.0, 50_000.0):
        solar_mass = source_mass_kg(power, sp_solar_at_cross)
        nuclear_mass = source_mass_kg(power, FISSION_SPECIFIC_POWER_W_PER_KG)
        assert solar_mass == pytest.approx(nuclear_mass, rel=1e-9)


def test_choose_source_matches_reality():
    # Inner system: solar wins (Mars, 1.52 AU).
    assert choose_source(1.524, power_we=1000.0) == "solar"
    # Beyond the crossover: nuclear wins (Jupiter, 5.2 AU) - "everything beyond switches".
    assert choose_source(5.2, power_we=5000.0) in ("fission", "rtg")
    assert choose_source(5.2, power_we=5000.0) == "fission"  # high power -> fission


def test_power_level_crossover_within_nuclear():
    # Far out, below ~1 kWe an RTG is lighter; above it, a fission reactor.
    assert choose_source(10.0, power_we=300.0) == "rtg"
    assert choose_source(10.0, power_we=5000.0) == "fission"


def test_pu238_vitamin_wall():
    # One GPHS-RTG needs 8.1 kg Pu-238.
    assert pu238_required_kg(1) == pytest.approx(8.1)
    # At the 1.5 kg/yr goal that is 5.4 years of the entire US supply for ONE RTG.
    assert years_of_pu238_production(8.1, annual_production_kg=1.5) == pytest.approx(5.4, rel=1e-2)
    # A 10-RTG fleet: 81 kg = 54 years at the goal rate, 162 years at today's ~0.5.
    fleet = pu238_required_kg(10)
    assert years_of_pu238_production(fleet, 1.5) == pytest.approx(54.0, rel=1e-2)
    assert years_of_pu238_production(fleet, 0.5) == pytest.approx(162.0, rel=1e-2)


def test_reactor_radiator_delegates_to_thermal():
    # 10 kWe fission at 30% conversion -> 23.3 kW of waste heat to reject.
    r = fission_reactor_radiator(10_000.0, conversion_efficiency=0.30, radiator_temp_k=500.0)
    assert r.waste_heat_w == pytest.approx(10_000.0 * 0.7 / 0.3, rel=1e-9)
    assert r.radiator_area_m2 > 0
    assert r.radiator_mass_kg == pytest.approx(r.radiator_area_m2 * 3.0, rel=1e-6)
    # A hotter radiator (thermal's T^4 leverage) is smaller for the same reactor.
    hot = fission_reactor_radiator(10_000.0, radiator_temp_k=800.0)
    assert hot.radiator_area_m2 < r.radiator_area_m2


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        solar_specific_power_at(0.0)
    with pytest.raises(ValueError):
        crossover_distance_au(100.0, 0.0)
    with pytest.raises(ValueError):
        choose_source(1.0, power_we=0.0)
    with pytest.raises(ValueError):
        years_of_pu238_production(8.1, annual_production_kg=0.0)
    with pytest.raises(ValueError):
        fission_reactor_radiator(10_000.0, conversion_efficiency=1.0)
