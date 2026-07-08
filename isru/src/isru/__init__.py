"""isru - in-situ feedstock processing.

Derives the two things `closure-sim` currently assumes about making material in place:
the *energy* it costs (retiring the hand-set ~5 kWh/kg for in-situ iron with a
molten-oxide-electrolysis figure, and adding a well-sourced 24.3 +/- 5.8 kWh/kg for
full-chain lunar oxygen), and the *closure ceiling* - the hard upper bound on how much
of a copy can be built locally, set by which elements the body actually has (you cannot
smelt carbon out of a body that has none).

Lunar tier is solid; in-situ non-iron metal and asteroid extraction are `[ESTIMATE]`
(terrestrial proxies). Pure algebra and table lookup over sourced numbers - no reactor
or geochemistry simulation (CLAUDE.md 3), no pimas, no RNG (7). See REFERENCES.md.
"""

from isru.energy import (
    CLOSURE_SIM_IRON_KWH_PER_KG,
    METAL_MOE_GLOBAL_SCALE_KWH_PER_KG,
    METAL_MOE_PRACTICAL_KWH_PER_KG,
    METAL_MOE_THEORETICAL_MIN_KWH_PER_KG,
    OXYGEN_ENERGY_SHARES,
    OXYGEN_FULL_CHAIN_KWH_PER_KG,
    OXYGEN_FULL_CHAIN_UNCERTAINTY_KWH_PER_KG,
    WATER_ICE_LOX_KWH_PER_KG,
    EnergyBand,
    metal_energy_kwh_per_kg,
    oxygen_energy_kwh_per_kg,
)
from isru.closure import (
    DEFAULT_USABLE_THRESHOLD_WT_PCT,
    LUNAR_REGOLITH_ELEMENT_WT_PCT,
    Part,
    available_elements,
    closure_ceiling,
    part_producible_locally,
)

__all__ = [
    "CLOSURE_SIM_IRON_KWH_PER_KG",
    "METAL_MOE_GLOBAL_SCALE_KWH_PER_KG",
    "METAL_MOE_PRACTICAL_KWH_PER_KG",
    "METAL_MOE_THEORETICAL_MIN_KWH_PER_KG",
    "OXYGEN_ENERGY_SHARES",
    "OXYGEN_FULL_CHAIN_KWH_PER_KG",
    "OXYGEN_FULL_CHAIN_UNCERTAINTY_KWH_PER_KG",
    "WATER_ICE_LOX_KWH_PER_KG",
    "EnergyBand",
    "metal_energy_kwh_per_kg",
    "oxygen_energy_kwh_per_kg",
    "DEFAULT_USABLE_THRESHOLD_WT_PCT",
    "LUNAR_REGOLITH_ELEMENT_WT_PCT",
    "Part",
    "available_elements",
    "closure_ceiling",
    "part_producible_locally",
]
