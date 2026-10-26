"""Distributional companions to closure-sim's sourced numbers."""

from __future__ import annotations

from vn_core.uq import Distribution, LogUniform, Uniform

from closure_sim.structures import SINTERED_REGOLITH_STRENGTH_BAND_MPA


# Per-part manufacturing energy ranges (kWh/kg), from the REFERENCES.md table.
PART_ENERGY_KWH_PER_KG_DIST: dict[str, Distribution] = {
    # metals / structure: recycled -> primary steel
    "structure": Uniform(1.7, 9.7),
    "thermal": Uniform(1.7, 5.6),
    "refining_plant": Uniform(6.0, 24.0),
    # motors / actuators / manipulators
    "actuators": Uniform(14.0, 20.0),
    "manipulators": Uniform(14.0, 20.0),
    # precision alloys / superalloys
    "bearings": Uniform(20.0, 46.0),
    # precision metal housings (tens)
    "sensor_housings": Uniform(20.0, 100.0),
    # silicon PV
    "solar_arrays": Uniform(40.0, 120.0),
    # power electronics / ICs
    "power_electronics": Uniform(1000.0, 3000.0),
    # electronic sensors
    "electronic_sensors": Uniform(2000.0, 8000.0),
    # finished packaged compute / logic chips (the widest, most consequential range)
    "compute_chips": Uniform(3000.0, 15000.0),
}

# Sintered lunar-regolith compressive strength (MPa).
SINTERED_REGOLITH_STRENGTH_DIST: Distribution = LogUniform(
    low=SINTERED_REGOLITH_STRENGTH_BAND_MPA[0],
    high=SINTERED_REGOLITH_STRENGTH_BAND_MPA[1],
)


__all__ = [
    "PART_ENERGY_KWH_PER_KG_DIST",
    "SINTERED_REGOLITH_STRENGTH_DIST",
]
