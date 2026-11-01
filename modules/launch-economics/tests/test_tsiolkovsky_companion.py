"""Analytical companion for the Tsiolkovsky rocket equation (issue #50, #22)."""

import math

import pytest

from launch_economics.launch import (
    G0_M_S2,
    exhaust_velocity_m_s,
    propellant_fraction,
    rocket_equation_mass_ratio,
)


# ---------- (2) matches exp(Δv / v_e) ----------

@pytest.mark.parametrize("delta_v,isp", [(4400.0, 300.0), (9400.0, 450.0), (3000.0, 350.0)])
def test_mass_ratio_matches_closed_form(delta_v, isp):
    v_e = exhaust_velocity_m_s(isp)
    expected = math.exp(delta_v / v_e)
    assert rocket_equation_mass_ratio(delta_v, v_e) == pytest.approx(expected, rel=1e-12)


# ---------- (3) matches 1 - exp(-Δv / v_e) ----------

def test_propellant_fraction_matches_closed_form():
    delta_v = 9400.0
    v_e = exhaust_velocity_m_s(450.0)
    expected = 1.0 - math.exp(-delta_v / v_e)
    assert propellant_fraction(delta_v, v_e) == pytest.approx(expected, rel=1e-12)


# ---------- Boundary Δv = 0 ----------

def test_zero_delta_v_boundary():
    v_e = exhaust_velocity_m_s(300.0)
    assert rocket_equation_mass_ratio(0.0, v_e) == pytest.approx(1.0, rel=1e-12)
    assert propellant_fraction(0.0, v_e) == pytest.approx(0.0, abs=1e-12)


# ---------- Additivity: sequential burns multiply mass ratios ----------

def test_sequential_burns_multiply_mass_ratios():
    """Δv_total = Δv_1 + Δv_2  =>  ratio_total = ratio_1 * ratio_2."""
    v_e = exhaust_velocity_m_s(300.0)
    r_total = rocket_equation_mass_ratio(9000.0, v_e)
    r1 = rocket_equation_mass_ratio(5000.0, v_e)
    r2 = rocket_equation_mass_ratio(4000.0, v_e)
    assert r_total == pytest.approx(r1 * r2, rel=1e-12)


# ---------- v_e = Isp * g0 with SI-defined g0 ----------

def test_exhaust_velocity_uses_defined_g0():
    assert G0_M_S2 == 9.80665  # BIPM defined constant, exact
    assert exhaust_velocity_m_s(1.0) == pytest.approx(9.80665, rel=1e-12)


# ---------- LEO anchor: 9.4 km/s at Isp 450 gives ~88%; at Isp 300 gives ~96% ----------

def test_leo_anchor_bracket():
    """The '93%' popular anchor lives between H2/O2 (450 s) and kerolox (300 s)."""
    leo_delta_v = 9400.0
    v_h2o2 = exhaust_velocity_m_s(450.0)
    v_kero = exhaust_velocity_m_s(300.0)
    frac_h2o2 = propellant_fraction(leo_delta_v, v_h2o2)
    frac_kero = propellant_fraction(leo_delta_v, v_kero)
    assert 0.86 < frac_h2o2 < 0.90       # ~88%
    assert 0.94 < frac_kero < 0.97       # ~96%
    assert frac_h2o2 < 0.93 < frac_kero  # the '93%' lives between


# ---------- Higher Isp always shrinks propellant fraction at fixed Δv ----------

def test_higher_isp_reduces_propellant_fraction():
    delta_v = 9400.0
    fracs = [propellant_fraction(delta_v, exhaust_velocity_m_s(isp)) for isp in (200.0, 300.0, 450.0, 900.0)]
    for a, b in zip(fracs, fracs[1:]):
        assert b < a
