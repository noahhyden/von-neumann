"""Launch physics and cost: real numbers and edges."""

import math

import pytest

from launch_economics.launch import (
    G0_M_S2,
    exhaust_velocity_m_s,
    launch_cost_usd,
    propellant_fraction,
    rocket_equation_mass_ratio,
)


def test_exhaust_velocity_from_isp():
    # Isp 350 s -> v_e = 350 * 9.80665 = 3432.3 m/s.
    assert exhaust_velocity_m_s(350.0) == pytest.approx(350.0 * G0_M_S2)
    assert exhaust_velocity_m_s(350.0) == pytest.approx(3432.3, rel=1e-3)


def test_rocket_equation_mass_ratio():
    ve = exhaust_velocity_m_s(350.0)
    # ~9.4 km/s to LEO -> mass ratio exp(9400/3432.3) ~= 15.5.
    assert rocket_equation_mass_ratio(9400.0, ve) == pytest.approx(math.exp(9400.0 / ve))
    assert rocket_equation_mass_ratio(9400.0, ve) == pytest.approx(15.5, rel=1e-2)


def test_zero_delta_v_needs_no_propellant():
    ve = exhaust_velocity_m_s(300.0)
    assert rocket_equation_mass_ratio(0.0, ve) == pytest.approx(1.0)
    assert propellant_fraction(0.0, ve) == pytest.approx(0.0)


def test_propellant_fraction_high_for_leo():
    ve = exhaust_velocity_m_s(350.0)
    # ~93% of liftoff mass is propellant for a ~9.4 km/s single-stage budget.
    assert propellant_fraction(9400.0, ve) == pytest.approx(0.935, abs=0.01)


def test_higher_delta_v_needs_more_propellant():
    ve = exhaust_velocity_m_s(350.0)
    assert propellant_fraction(12000.0, ve) > propellant_fraction(9400.0, ve)


def test_launch_cost_is_linear():
    assert launch_cost_usd(1000.0, 3000.0) == pytest.approx(3_000_000.0)
    assert launch_cost_usd(0.0, 3000.0) == 0.0


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        exhaust_velocity_m_s(0.0)
    with pytest.raises(ValueError):
        rocket_equation_mass_ratio(-1.0, 3000.0)
    with pytest.raises(ValueError):
        rocket_equation_mass_ratio(1000.0, 0.0)
    with pytest.raises(ValueError):
        launch_cost_usd(-1.0, 3000.0)
