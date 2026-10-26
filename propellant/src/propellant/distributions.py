"""Distributional companions to propellant's sourced numbers."""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, Uniform

from propellant.propellant import (
    HHV_HYDROGEN_KWH_PER_KG,
    HYDROGEN_MASS_FRACTION_OF_WATER,
    KORNUTA_FULL_CHAIN_KWH_PER_KG,
    XENON_WORLD_SUPPLY_T_PER_YR,
)

# Thermodynamic / definitional -> Fixed.
HHV_HYDROGEN_DIST: Distribution = Fixed(HHV_HYDROGEN_KWH_PER_KG)
HYDROGEN_MASS_FRACTION_OF_WATER_DIST: Distribution = Fixed(HYDROGEN_MASS_FRACTION_OF_WATER)

# Practical full-chain water-to-propellant energy: Kornuta 11.3 kWh/kg midpoint with a ~30% band for mining/liquefaction variability (REFERENCES.md).
KORNUTA_FULL_CHAIN_DIST: Distribution = Uniform(low=9.0, high=15.0)

# Xenon supply already sourced as a range.
XENON_WORLD_SUPPLY_DIST: Distribution = Uniform(
    low=XENON_WORLD_SUPPLY_T_PER_YR[0],
    high=XENON_WORLD_SUPPLY_T_PER_YR[1],
)

# Route-specific Isp bands from launch-economics; point values live in propellant/propellant.py and these match the sourced ranges.
ISP_LOX_LH2_DIST: Distribution = Uniform(low=440.0, high=460.0)
ISP_WATER_RESISTOJET_DIST: Distribution = Uniform(low=280.0, high=320.0)
ISP_XENON_HALL_EP_DIST: Distribution = Uniform(low=1500.0, high=2000.0)
ISP_XENON_ION_EP_DIST: Distribution = Uniform(low=4000.0, high=4300.0)


__all__ = [
    "HHV_HYDROGEN_DIST",
    "HYDROGEN_MASS_FRACTION_OF_WATER_DIST",
    "KORNUTA_FULL_CHAIN_DIST",
    "XENON_WORLD_SUPPLY_DIST",
    "ISP_LOX_LH2_DIST",
    "ISP_WATER_RESISTOJET_DIST",
    "ISP_XENON_HALL_EP_DIST",
    "ISP_XENON_ION_EP_DIST",
]
