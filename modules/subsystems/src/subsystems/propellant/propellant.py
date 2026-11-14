"""Reaction mass, its production energy, and propellant closure."""

from __future__ import annotations

from dataclasses import dataclass

from launch_economics.launch import (
    exhaust_velocity_m_s,
    propellant_fraction,
    rocket_equation_mass_ratio,
)

# --- Production energy (water route): HHV of hydrogen, kWh/kg H2 (142 MJ/kg), the thermodynamic total to dissociate water at standard conditions. See REFERENCES.md. ---
HHV_HYDROGEN_KWH_PER_KG: float = 39.4
# Hydrogen mass fraction of water: 2 x 1.008 / 18.015 = 0.1119.
HYDROGEN_MASS_FRACTION_OF_WATER: float = 2.016 / 18.015
# Practical full-chain water-ice-to-propellant energy (Kornuta et al.), kWh/kg; the same figure isru cites for the water-ice LOX route, with the seam kept clean (isru: regolith -> parts; propellant: water-ice -> reaction mass).
KORNUTA_FULL_CHAIN_KWH_PER_KG: float = 11.3

# --- Noble-gas import wall: Earth's entire annual xenon production, tonnes/year (extraction from air; scarce). See REFERENCES.md. ---
XENON_WORLD_SUPPLY_T_PER_YR: tuple[float, float] = (40.0, 60.0)


@dataclass(frozen=True)
class PropellantRoute:
    """A way to produce and use propellant."""

    name: str
    isp_s: float
    needs_water: bool
    is_noble_gas: bool


# Representative routes, Isp from launch-economics' sourced bands. See REFERENCES.md.
LOX_LH2_FROM_WATER = PropellantRoute("LOX/LH2 (water-derived)", 450.0, needs_water=True, is_noble_gas=False)
WATER_RESISTOJET = PropellantRoute("water electrothermal", 300.0, needs_water=True, is_noble_gas=False)
XENON_HALL_EP = PropellantRoute("xenon Hall EP", 1800.0, needs_water=False, is_noble_gas=True)
XENON_ION_EP = PropellantRoute("xenon ion EP (NEXT-C)", 4190.0, needs_water=False, is_noble_gas=True)


def reaction_mass_kg(delta_v_m_s: float, isp_s: float, dry_mass_kg: float) -> float:
    """Propellant mass (kg) for a hop: m_dry * (exp(Delta_v/v_e) - 1) (Tsiolkovsky)."""
    if delta_v_m_s < 0:
        raise ValueError("delta_v_m_s must be non-negative")
    if dry_mass_kg <= 0:
        raise ValueError("dry_mass_kg must be positive")
    v_e = exhaust_velocity_m_s(isp_s)
    ratio = rocket_equation_mass_ratio(delta_v_m_s, v_e)
    return dry_mass_kg * (ratio - 1.0)


def water_electrolysis_hhv_min_kwh_per_kg() -> float:
    """Thermodynamic floor to electrolyse 1 kg of water: HHV(H2) x H2 mass fraction."""
    return HHV_HYDROGEN_KWH_PER_KG * HYDROGEN_MASS_FRACTION_OF_WATER


def propellant_closure(route: PropellantRoute, body_has_water: bool) -> float:
    """Fraction of a route's reaction mass obtainable locally (the propellant-closure axis)."""
    if route.is_noble_gas:
        return 0.0
    if route.needs_water:
        return 1.0 if body_has_water else 0.0
    return 0.0


def xenon_supply_fraction(
    xenon_mass_t: float, annual_supply_t: float = XENON_WORLD_SUPPLY_T_PER_YR[1]
) -> float:
    """Fraction of Earth's annual xenon production a mission's xenon load consumes."""
    if xenon_mass_t < 0:
        raise ValueError("xenon_mass_t must be non-negative")
    if annual_supply_t <= 0:
        raise ValueError("annual_supply_t must be positive")
    return xenon_mass_t / annual_supply_t


@dataclass(frozen=True)
class RouteComparison:
    """One route's reaction-mass demand and propellant closure for a given hop."""

    name: str
    propellant_mass_kg: float
    propellant_closure: float
    imported_propellant_kg: float


def compare_routes(
    delta_v_m_s: float,
    dry_mass_kg: float,
    routes: list[PropellantRoute],
    body_has_water: bool,
) -> list[RouteComparison]:
    """Reaction-mass demand + propellant closure per route - the mass-vs-tether trade."""
    out: list[RouteComparison] = []
    for r in routes:
        m = reaction_mass_kg(delta_v_m_s, r.isp_s, dry_mass_kg)
        c = propellant_closure(r, body_has_water)
        out.append(
            RouteComparison(
                name=r.name,
                propellant_mass_kg=m,
                propellant_closure=c,
                imported_propellant_kg=(1.0 - c) * m,
            )
        )
    return out
