"""Impulsive-transfer validation: real transfers, edges, and monotonicity.

Targets are recomputed from the sourced constants (GM_sun, AU, orbital radii) and
cross-checked against textbook values (Earth->Mars ~5.59 km/s, ~259 d). See
transfer-SPEC.md and REFERENCES.md.
"""

import math

import pytest

from transfer.orbits import (
    BODY_SEMI_MAJOR_AXIS_AU,
    BODY_SIDEREAL_PERIOD_DAYS,
    circular_orbital_speed_m_s,
    hohmann_transfer,
    synodic_period_days,
)

EARTH = BODY_SEMI_MAJOR_AXIS_AU["earth"]
MARS = BODY_SEMI_MAJOR_AXIS_AU["mars"]
CERES = BODY_SEMI_MAJOR_AXIS_AU["ceres"]
JUPITER = BODY_SEMI_MAJOR_AXIS_AU["jupiter"]


def test_earth_circular_speed_matches_known_29_78_km_s():
    # Earth's mean heliocentric speed is ~29.78 km/s - a sanity anchor for GM_sun/AU.
    assert circular_orbital_speed_m_s(EARTH) == pytest.approx(29_784.8, rel=1e-4)


def test_earth_to_mars_delta_v_and_time():
    r = hohmann_transfer(EARTH, MARS)
    # Textbook Earth->Mars Hohmann: dv1 ~2.945, dv2 ~2.649, total ~5.59 km/s.
    assert r.dv1_m_s == pytest.approx(2945.0, abs=5.0)
    assert r.dv2_m_s == pytest.approx(2649.0, abs=5.0)
    assert r.dv_total_m_s == pytest.approx(5594.0, rel=1e-3)
    # Half the transfer-ellipse period: ~258.9 days.
    assert r.transfer_time_days == pytest.approx(258.9, rel=1e-3)


def test_earth_to_ceres():
    r = hohmann_transfer(EARTH, CERES)
    assert r.dv_total_m_s == pytest.approx(11_180.0, rel=2e-3)
    assert r.transfer_time_days == pytest.approx(472.6, rel=2e-3)


def test_earth_to_jupiter_explains_the_gravity_assist():
    r = hohmann_transfer(EARTH, JUPITER)
    # ~14.44 km/s and ~2.7 yr - why Jupiter missions use gravity assists.
    assert r.dv_total_m_s == pytest.approx(14_440.0, rel=2e-3)
    assert r.transfer_time_days == pytest.approx(997.6, rel=2e-3)


def test_same_orbit_is_exactly_zero_delta_v():
    r = hohmann_transfer(EARTH, EARTH)
    # Not "small" - identically zero (CLAUDE.md §2 edge behavior).
    assert r.dv1_m_s == 0.0
    assert r.dv2_m_s == 0.0
    assert r.dv_total_m_s == 0.0
    # Transfer time collapses to half the orbital period at 1 AU: ~182.6 days.
    assert r.transfer_time_days == pytest.approx(182.6, rel=1e-3)


def test_inward_transfer_is_symmetric_in_magnitude():
    # Δv is a magnitude sum, so out and back cost the same total.
    out = hohmann_transfer(EARTH, MARS)
    back = hohmann_transfer(MARS, EARTH)
    assert back.dv_total_m_s == pytest.approx(out.dv_total_m_s, rel=1e-12)
    assert back.transfer_time_days == pytest.approx(out.transfer_time_days, rel=1e-12)


def test_farther_target_costs_more_and_takes_longer():
    times = []
    totals = []
    for target in (MARS, CERES, JUPITER):
        r = hohmann_transfer(EARTH, target)
        times.append(r.transfer_time_days)
        totals.append(r.dv_total_m_s)
    assert times == sorted(times)
    assert totals == sorted(totals)


def test_synodic_earth_mars():
    t = synodic_period_days(
        BODY_SIDEREAL_PERIOD_DAYS["earth"], BODY_SIDEREAL_PERIOD_DAYS["mars"]
    )
    # ~779.9 days (~2.14 yr) between Earth-Mars launch windows.
    assert t == pytest.approx(779.9, rel=1e-3)


def test_synodic_equal_periods_raises():
    with pytest.raises(ValueError):
        synodic_period_days(365.256, 365.256)


def test_nonpositive_inputs_raise():
    with pytest.raises(ValueError):
        hohmann_transfer(0.0, 1.0)
    with pytest.raises(ValueError):
        hohmann_transfer(1.0, -1.0)
    with pytest.raises(ValueError):
        circular_orbital_speed_m_s(0.0)
