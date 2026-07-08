"""thermal - heat rejection and radiator sizing.

Closes the project's own gap: FINDINGS calls self-replication "a power-and-cooling
problem, not a physics one", but nothing modelled the cooling. Every watt delivered
becomes waste heat, and in vacuum a radiator is the only way out. This module sizes that
radiator by Stefan-Boltzmann and returns its mass to closure-sim's BOM, so heat
rejection stops being free.

Two headline results: the T^4 leverage (a ~530 K smelting radiator is ~10x lighter per
kW than a ~300 K electronics radiator, so heat must be binned by process temperature),
and the parasitic solar-load distance story (radiators improve as you leave the Sun).
Validated against the ISS thermal control system. Pure, deterministic, no pimas, no RNG
(CLAUDE.md 7). Every number traces to a source; see REFERENCES.md.
"""

from thermal.thermal import (
    DEFAULT_EMISSIVITY,
    ISS_HEAT_REJECTION_PER_LOOP_KW,
    ISS_HEAT_REJECTION_TOTAL_KW,
    ISS_RADIATOR_ASSEMBLY_AREA_M2,
    ISS_RADIATOR_TEMP_K,
    RADIATOR_SPECIFIC_MASS_BAND_KG_M2,
    RADIATOR_SPECIFIC_MASS_KG_M2,
    STEFAN_BOLTZMANN_W_M2_K4,
    RadiatorResult,
    mass_per_kw_kg,
    net_flux_with_solar_load_w_m2,
    radiated_flux_w_m2,
    radiator_area_m2,
    radiator_mass_kg,
    size_radiator,
)

__all__ = [
    "DEFAULT_EMISSIVITY",
    "ISS_HEAT_REJECTION_PER_LOOP_KW",
    "ISS_HEAT_REJECTION_TOTAL_KW",
    "ISS_RADIATOR_ASSEMBLY_AREA_M2",
    "ISS_RADIATOR_TEMP_K",
    "RADIATOR_SPECIFIC_MASS_BAND_KG_M2",
    "RADIATOR_SPECIFIC_MASS_KG_M2",
    "STEFAN_BOLTZMANN_W_M2_K4",
    "RadiatorResult",
    "mass_per_kw_kg",
    "net_flux_with_solar_load_w_m2",
    "radiated_flux_w_m2",
    "radiator_area_m2",
    "radiator_mass_kg",
    "size_radiator",
]
