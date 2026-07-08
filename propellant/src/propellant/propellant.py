"""Reaction mass, its production energy, and propellant closure.

A self-replicating probe that must ship its propellant from Earth is not self-
sufficient, no matter how well it closes its *structural* mass. This module adds a
distinct closure axis - **propellant closure** - and shows the trade at its heart.

Three pieces, each reusing physics already in the repo:

1. **Reaction-mass demand.** How much propellant a hop costs is the Tsiolkovsky rocket
   equation (reused from `launch-economics`) fed by the Delta-v from `transfer`:
   `m_prop = m_dry * (exp(Delta_v / v_e) - 1)`.
2. **Production energy.** Making propellant in place costs energy. For the water route,
   the thermodynamic floor is the higher heating value of the hydrogen you liberate:
   HHV(H2) = 39.4 kWh/kg, and water is 11.2 wt% hydrogen, so electrolysing 1 kg of water
   costs at least 4.41 kWh. The practical full chain (mining, purification, electrolysis,
   liquefaction) is ~11 kWh/kg (Kornuta et al.).
3. **Propellant closure and the import wall.** Water/O2 routes reach closure 1.0 on a
   water-bearing body (both H and O are local). Noble-gas electric propulsion (xenon) is
   a hard import wall: xenon cannot be extracted in bulk off-world, and Earth's entire
   supply is only ~40-60 tonnes per year. The payoff: high-Isp xenon EP minimises
   propellant *mass* but tethers the probe to Earth forever; water routes carry more
   propellant mass but close.

Pure algebra over sourced numbers - no thruster or plume physics (over-nesting,
CLAUDE.md 3), no pimas, no RNG (7). Every number is in REFERENCES.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from launch_economics.launch import (
    exhaust_velocity_m_s,
    propellant_fraction,
    rocket_equation_mass_ratio,
)

# --- Production energy (water route). See REFERENCES.md. ---
# Higher heating value of hydrogen, kWh/kg H2 (142 MJ/kg). Thermodynamic total to
# dissociate water at standard conditions.
HHV_HYDROGEN_KWH_PER_KG: float = 39.4
# Hydrogen mass fraction of water: 2 x 1.008 / 18.015 = 0.1119.
HYDROGEN_MASS_FRACTION_OF_WATER: float = 2.016 / 18.015
# Practical full-chain water-ice-to-propellant energy (Kornuta et al.), kWh/kg. Same
# figure isru cites for the water-ice LOX route; the seam is kept clean (isru: regolith
# -> parts; propellant: water-ice -> reaction mass).
KORNUTA_FULL_CHAIN_KWH_PER_KG: float = 11.3

# --- Noble-gas import wall. See REFERENCES.md. ---
# Earth's entire annual xenon production, tonnes/year (extraction from air; scarce).
XENON_WORLD_SUPPLY_T_PER_YR: tuple[float, float] = (40.0, 60.0)


@dataclass(frozen=True)
class PropellantRoute:
    """A way to produce and use propellant.

    isp_s: specific impulse (sets reaction-mass demand via Tsiolkovsky).
    needs_water: True if the route's reaction mass comes from water (H and/or O).
    is_noble_gas: True if the route burns an imported noble gas (the import wall).
    """

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
    """Propellant mass (kg) for a hop: m_dry * (exp(Delta_v/v_e) - 1) (Tsiolkovsky).

    Reuses `launch-economics` for the rocket equation rather than re-deriving it.
    """
    if delta_v_m_s < 0:
        raise ValueError("delta_v_m_s must be non-negative")
    if dry_mass_kg <= 0:
        raise ValueError("dry_mass_kg must be positive")
    v_e = exhaust_velocity_m_s(isp_s)
    ratio = rocket_equation_mass_ratio(delta_v_m_s, v_e)
    return dry_mass_kg * (ratio - 1.0)


def water_electrolysis_hhv_min_kwh_per_kg() -> float:
    """Thermodynamic floor to electrolyse 1 kg of water: HHV(H2) x H2 mass fraction.

    39.4 kWh/kg H2 x 0.1119 = 4.41 kWh per kg of water. This is a minimum; real systems
    (and the full mining-to-liquefaction chain) cost more (see KORNUTA_FULL_CHAIN).
    """
    return HHV_HYDROGEN_KWH_PER_KG * HYDROGEN_MASS_FRACTION_OF_WATER


def propellant_closure(route: PropellantRoute, body_has_water: bool) -> float:
    """Fraction of a route's reaction mass obtainable locally (the propellant-closure axis).

    - A water route on a water-bearing body: 1.0 (H and O are both local).
    - A water route on a dry body: 0.0 (the reaction mass must be imported).
    - A noble-gas route: 0.0 anywhere (xenon/krypton cannot be extracted off-world in
      bulk - the hard import wall), regardless of water.
    """
    if route.is_noble_gas:
        return 0.0
    if route.needs_water:
        return 1.0 if body_has_water else 0.0
    return 0.0


def xenon_supply_fraction(
    xenon_mass_t: float, annual_supply_t: float = XENON_WORLD_SUPPLY_T_PER_YR[1]
) -> float:
    """Fraction of Earth's annual xenon production a mission's xenon load consumes.

    A load that is a large fraction of world supply cannot be sourced without disrupting
    the market - the practical ceiling on xenon-EP fleets.
    """
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
    """Reaction-mass demand + propellant closure per route - the mass-vs-tether trade.

    imported_propellant_kg = (1 - closure) x propellant_mass: the mass that still has to
    come from Earth. High-Isp noble-gas routes drive propellant_mass down but leave
    imported mass at 100% of it; water routes carry more mass but import none.
    """
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
