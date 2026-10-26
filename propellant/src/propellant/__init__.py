"""propellant - reaction mass, its production energy, and propellant closure."""

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
