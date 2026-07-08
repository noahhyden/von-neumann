"""propellant - reaction mass, its production energy, and propellant closure.

Adds a closure axis the structural models miss: a probe that ships its propellant from
Earth is not self-sufficient. Reaction-mass demand is Tsiolkovsky (reused from
`launch-economics`) fed by `transfer`'s Delta-v; production energy for the water route
has a thermodynamic floor of 4.41 kWh/kg (HHV of the liberated hydrogen); and propellant
closure reaches 1.0 on a water-bearing body but 0.0 for noble-gas EP - whose real
ceiling is that Earth makes only ~40-60 tonnes of xenon a year.

Pure algebra over sourced numbers - no thruster physics (CLAUDE.md 3), no pimas, no RNG
(7). Every number traces to a source; see REFERENCES.md.
"""

from propellant.propellant import (
    HHV_HYDROGEN_KWH_PER_KG,
    HYDROGEN_MASS_FRACTION_OF_WATER,
    KORNUTA_FULL_CHAIN_KWH_PER_KG,
    LOX_LH2_FROM_WATER,
    WATER_RESISTOJET,
    XENON_HALL_EP,
    XENON_ION_EP,
    XENON_WORLD_SUPPLY_T_PER_YR,
    PropellantRoute,
    RouteComparison,
    compare_routes,
    propellant_closure,
    reaction_mass_kg,
    water_electrolysis_hhv_min_kwh_per_kg,
    xenon_supply_fraction,
)

__all__ = [
    "HHV_HYDROGEN_KWH_PER_KG",
    "HYDROGEN_MASS_FRACTION_OF_WATER",
    "KORNUTA_FULL_CHAIN_KWH_PER_KG",
    "XENON_WORLD_SUPPLY_T_PER_YR",
    "LOX_LH2_FROM_WATER",
    "WATER_RESISTOJET",
    "XENON_HALL_EP",
    "XENON_ION_EP",
    "PropellantRoute",
    "RouteComparison",
    "compare_routes",
    "propellant_closure",
    "reaction_mass_kg",
    "water_electrolysis_hhv_min_kwh_per_kg",
    "xenon_supply_fraction",
]
