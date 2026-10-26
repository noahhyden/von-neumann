"""Analytical companion for power-source (issue #50, Phase 2)."""

import math

import pytest

from power_source.power_source import (
    FISSION_SPECIFIC_POWER_W_PER_KG,
    SOLAR_SPECIFIC_POWER_1AU_W_PER_KG,
    choose_source,
    crossover_distance_au,
    solar_specific_power_at,
    source_mass_kg,
)


# ---------- (3) matches sqrt(sp_solar / sp_nuclear) ----------

def test_crossover_matches_closed_form():
    sp_solar = 100.0
    sp_nuclear = 6.7
    expected = math.sqrt(sp_solar / sp_nuclear)
    assert crossover_distance_au(sp_solar, sp_nuclear) == pytest.approx(expected, rel=1e-12)


# ---------- P cancels: crossover is invariant under total-power rescaling ----------

@pytest.mark.parametrize("power_we", [1.0, 100.0, 1_000.0, 100_000.0])
def test_crossover_independent_of_power(power_we):
    d_cross = crossover_distance_au()
    m_solar = source_mass_kg(power_we, solar_specific_power_at(d_cross))
    m_nuclear = source_mass_kg(power_we, FISSION_SPECIFIC_POWER_W_PER_KG)
    assert m_solar == pytest.approx(m_nuclear, rel=1e-9)


# ---------- Inside crossover, solar is lighter; outside, nuclear is ----------

def test_solar_lighter_inside_crossover():
    d_cross = crossover_distance_au()
    for d in (d_cross * 0.5, d_cross * 0.9):
        m_solar = source_mass_kg(1000.0, solar_specific_power_at(d))
        m_nuclear = source_mass_kg(1000.0, FISSION_SPECIFIC_POWER_W_PER_KG)
        assert m_solar < m_nuclear


def test_nuclear_lighter_outside_crossover():
    d_cross = crossover_distance_au()
    for d in (d_cross * 1.1, d_cross * 2.0, d_cross * 5.0):
        m_solar = source_mass_kg(1000.0, solar_specific_power_at(d))
        m_nuclear = source_mass_kg(1000.0, FISSION_SPECIFIC_POWER_W_PER_KG)
        assert m_solar > m_nuclear


# ---------- choose_source flips at the crossover ----------

def test_choose_source_consistent_with_crossover():
    d_cross = crossover_distance_au()
    assert choose_source(distance_au=d_cross * 0.5, power_we=10_000.0) == "solar"
    assert choose_source(distance_au=d_cross * 2.0, power_we=10_000.0) == "fission"


# ---------- Default numerical crossover in the sourced 4-5 AU band ----------

def test_default_crossover_in_the_sourced_band():
    d_cross = crossover_distance_au()
    # Sourced anchors from REFERENCES.md: ~3.9 AU (fission), ~4.4 AU (RTG); the default is fission and must be near 3.9.
    assert 3.5 < d_cross < 4.5
