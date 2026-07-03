"""Launch physics and cost: what it takes to put a kilogram somewhere.

Two pieces:

- **cost** - `launch_cost_usd(mass, cost_per_kg)`. The $/kg is a scenario input (it
  varies by vehicle and year); representative sourced values live in REFERENCES.md.
- **the Δv penalty** - the Tsiolkovsky rocket equation, `mass_ratio = exp(Δv / v_e)`.
  Reaching a higher-energy destination costs exponentially more propellant per kg of
  payload, which is the physical reason launching finished mass across the solar
  system is so expensive - and why replicating it in place is worth so much.

Only defined physical constants are hardcoded (standard gravity); Δv budgets and
specific impulse are inputs, documented in REFERENCES.md. Deterministic, plain data,
zero pimas imports (CLAUDE.md §7). SI units: m/s, kg, seconds, USD.
"""

from __future__ import annotations

import math

# Standard gravity, m/s^2 - defined constant (BIPM/SI), used to turn specific impulse
# (seconds) into exhaust velocity. Exact by definition.
G0_M_S2: float = 9.80665


def exhaust_velocity_m_s(specific_impulse_s: float) -> float:
    """Effective exhaust velocity (m/s) from specific impulse (s): v_e = Isp * g0."""
    if specific_impulse_s <= 0:
        raise ValueError("specific_impulse_s must be positive")
    return specific_impulse_s * G0_M_S2


def rocket_equation_mass_ratio(delta_v_m_s: float, exhaust_velocity_m_s: float) -> float:
    """Tsiolkovsky mass ratio m0/mf = exp(Δv / v_e) for a burn of Δv."""
    if delta_v_m_s < 0:
        raise ValueError("delta_v_m_s must be non-negative")
    if exhaust_velocity_m_s <= 0:
        raise ValueError("exhaust_velocity_m_s must be positive")
    return math.exp(delta_v_m_s / exhaust_velocity_m_s)


def propellant_fraction(delta_v_m_s: float, exhaust_velocity_m_s: float) -> float:
    """Fraction of initial mass that must be propellant to achieve Δv: 1 - 1/mass_ratio."""
    ratio = rocket_equation_mass_ratio(delta_v_m_s, exhaust_velocity_m_s)
    return 1.0 - 1.0 / ratio


def launch_cost_usd(mass_kg: float, cost_per_kg_usd: float) -> float:
    """Cost (USD) to launch a payload mass at a given specific launch cost ($/kg)."""
    if mass_kg < 0:
        raise ValueError("mass_kg must be non-negative")
    if cost_per_kg_usd < 0:
        raise ValueError("cost_per_kg_usd must be non-negative")
    return mass_kg * cost_per_kg_usd
