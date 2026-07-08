"""power-source - solar vs fission vs RTG, and the Pu-238 wall.

Picks the lightest power source by two crossovers - a distance crossover
`d = sqrt(sp_solar_1AU / sp_nuclear)` ~4-5 AU (independent of power level) and a
power-level crossover (RTG below ~1 kWe, fission above) - and surfaces the sharpest
vitamin in the project: one GPHS-RTG needs ~8 kg of plutonium-238, of which the US makes
only ~0.5-1.5 kg per year. It reuses `probe-sim`'s 1/d^2 law and calls `thermal` to size
a reactor's radiator. Pure, deterministic, no pimas, no RNG (CLAUDE.md 7). Every number
traces to a source; see REFERENCES.md.
"""

from power_source.power_source import (
    FISSION_CONVERSION_EFFICIENCY,
    FISSION_RADIATOR_TEMP_K,
    FISSION_SPECIFIC_POWER_W_PER_KG,
    GPHS_RTG_SPECIFIC_POWER_W_PER_KG,
    MMRTG_SPECIFIC_POWER_W_PER_KG,
    PU238_ANNUAL_PRODUCTION_KG,
    PU238_PER_GPHS_RTG_KG,
    RTG_FISSION_CROSSOVER_WE,
    SOLAR_SPECIFIC_POWER_1AU_W_PER_KG,
    ReactorRadiator,
    choose_source,
    crossover_distance_au,
    fission_reactor_radiator,
    pu238_required_kg,
    solar_specific_power_at,
    source_mass_kg,
    years_of_pu238_production,
)

__all__ = [
    "FISSION_CONVERSION_EFFICIENCY",
    "FISSION_RADIATOR_TEMP_K",
    "FISSION_SPECIFIC_POWER_W_PER_KG",
    "GPHS_RTG_SPECIFIC_POWER_W_PER_KG",
    "MMRTG_SPECIFIC_POWER_W_PER_KG",
    "PU238_ANNUAL_PRODUCTION_KG",
    "PU238_PER_GPHS_RTG_KG",
    "RTG_FISSION_CROSSOVER_WE",
    "SOLAR_SPECIFIC_POWER_1AU_W_PER_KG",
    "ReactorRadiator",
    "choose_source",
    "crossover_distance_au",
    "fission_reactor_radiator",
    "pu238_required_kg",
    "solar_specific_power_at",
    "source_mass_kg",
    "years_of_pu238_production",
]
