"""Distributional companions to propellant's sourced numbers.

Issue #35 (UQ). propellant's constants split as:

- **Thermodynamic / definitional**: HHV_HYDROGEN (39.4 kWh/kg, from
  standard-state Gibbs), HYDROGEN_MASS_FRACTION_OF_WATER (from atomic
  masses). Fixed.
- **Practical / process-dependent**: KORNUTA_FULL_CHAIN (11.3 kWh/kg for
  water-ice-to-propellant) has a documented practical range roughly
  9-15 kWh/kg depending on mining and liquefaction losses. Uniform(9, 15).
- **Market range**: XENON_WORLD_SUPPLY = (40, 60) t/yr already carried as
  a tuple; expose the corresponding Uniform.
- **Route Isp values**: point values from `launch-economics/REFERENCES.md`
  bands; expose distributional companions per route so a UQ propagation on
  reaction mass reflects the honest Isp band.
"""

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

# Practical full-chain water-to-propellant energy: Kornuta's 11.3 kWh/kg
# midpoint with a ~30% band for mining/liquefaction variability.
KORNUTA_FULL_CHAIN_DIST: Distribution = Uniform(low=9.0, high=15.0)

# Xenon supply already sourced as a range.
XENON_WORLD_SUPPLY_DIST: Distribution = Uniform(
    low=XENON_WORLD_SUPPLY_T_PER_YR[0],
    high=XENON_WORLD_SUPPLY_T_PER_YR[1],
)

# Route-specific Isp bands from launch-economics. Point values in
# propellant/propellant.py; the distributions here match the sourced ranges.
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
