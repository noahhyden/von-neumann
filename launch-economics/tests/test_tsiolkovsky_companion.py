"""Analytical companion for the Tsiolkovsky rocket equation (issue #50, #22).

The propellant-fraction claim is a one-liner over sourced constants, and
Tsiolkovsky's derivation is the cleanest exponential in propulsion physics.
This file states the derivation and asserts sim matches at multiple regimes.

## Derivation

A rocket ejects mass at effective exhaust velocity `v_e`. Momentum
conservation over a thrust interval gives

    m * dv/dt = -v_e * dm/dt

which integrates to Tsiolkovsky:

    Δv = v_e * ln(m0 / mf)                          (1)

Rearranging:

    mass_ratio  = m0 / mf = exp(Δv / v_e)            (2)
    prop_frac   = 1 - mf/m0 = 1 - exp(-Δv / v_e)     (3)

The exhaust velocity is set by specific impulse: `v_e = Isp * g0`.

## Test coverage
- (2) and (3) match the closed forms at 1e-12 relative.
- Boundary Δv = 0 gives mass_ratio = 1 and prop_frac = 0 exactly.
- Additivity: two sequential burns Δv1 + Δv2 give mass_ratio = ratio1 * ratio2
  (a direct consequence of ln converting sums to products).
- LEO anchor: Δv ≈ 9.4 km/s at typical Isp (450 s H2/O2) gives prop_frac ≈ 0.88.
  At Isp = 300 s (kerolox typical) it gives ≈ 0.96. The frequently-cited "93%"
  sits between these depending on which Isp is anchored.
"""

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
