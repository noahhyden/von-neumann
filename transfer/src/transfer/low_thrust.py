"""Low-thrust solar-electric (SEP) transfers: propellant, thrust, and trip time."""

from __future__ import annotations

import math
from dataclasses import dataclass

from launch_economics.launch import exhaust_velocity_m_s, rocket_equation_mass_ratio
from probe_sim.environment import solar_irradiance_w_m2

from transfer.orbits import SECONDS_PER_DAY, circular_orbital_speed_m_s


@dataclass(frozen=True)
class SepResult:
    """A low-thrust solar-electric transfer leg."""

    propellant_mass_kg: float
    power_at_distance_w: float
    thrust_n: float
    accel_m_s2: float
    trip_time_days: float


def available_power_w(power_w_at_1au: float, distance_au: float) -> float:
    """SEP array power (W) at a heliocentric distance, by probe-sim's 1/d^2 law."""
    if power_w_at_1au <= 0:
        raise ValueError("power_w_at_1au must be positive")
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    ratio = solar_irradiance_w_m2(distance_au) / solar_irradiance_w_m2(1.0)
    return power_w_at_1au * ratio


def sep_thrust_n(power_w: float, isp_s: float, efficiency: float) -> float:
    """Thrust (N) from jet power: F = 2 eta P / (g0 Isp) = 2 eta P / v_e."""
    if power_w < 0:
        raise ValueError("power_w must be non-negative")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError("efficiency must be in (0, 1]")
    v_e = exhaust_velocity_m_s(isp_s)
    return 2.0 * efficiency * power_w / v_e


def edelbaum_delta_v_m_s(
    r1_au: float, r2_au: float, plane_change_deg: float = 0.0
) -> float:
    """Edelbaum circle-to-circle Δv (m/s) for a low-thrust spiral."""
    v1 = circular_orbital_speed_m_s(r1_au)
    v2 = circular_orbital_speed_m_s(r2_au)
    dtheta = plane_change_deg / 90.0
    inner = v1 * v1 - 2.0 * v1 * v2 * math.cos((math.pi / 2.0) * dtheta) + v2 * v2
    # Guard tiny negative from floating error at the coplanar limit.
    return math.sqrt(max(inner, 0.0))


def sep_transfer(
    dv_m_s: float,
    isp_s: float,
    dry_mass_kg: float,
    power_w_at_1au: float,
    distance_au: float,
    efficiency: float,
) -> SepResult:
    """Propellant, thrust, acceleration, and Edelbaum trip time for an SEP leg."""
    if dv_m_s < 0:
        raise ValueError("dv_m_s must be non-negative")
    if dry_mass_kg <= 0:
        raise ValueError("dry_mass_kg must be positive")

    v_e = exhaust_velocity_m_s(isp_s)
    mass_ratio = rocket_equation_mass_ratio(dv_m_s, v_e)
    propellant_kg = dry_mass_kg * (mass_ratio - 1.0)
    wet_mass_kg = dry_mass_kg + propellant_kg

    power_w = available_power_w(power_w_at_1au, distance_au)
    thrust_n = sep_thrust_n(power_w, isp_s, efficiency)
    accel = thrust_n / wet_mass_kg

    if accel <= 0:
        # Δv == 0 => no thrust needed, no time; zero-length leg.
        trip_time_days = 0.0
    else:
        trip_time_days = (dv_m_s / accel) / SECONDS_PER_DAY

    return SepResult(
        propellant_mass_kg=propellant_kg,
        power_at_distance_w=power_w,
        thrust_n=thrust_n,
        accel_m_s2=accel,
        trip_time_days=trip_time_days,
    )
