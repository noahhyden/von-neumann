"""Distributional companions to launch-economics' sourced numbers.

Issue #35 (UQ) applied to launch-economics. Two categories:

- **Definitional / market anchors.** `G0_M_S2 = 9.80665` is exact by SI;
  platinum market total and annual production and the Psyche quoted value
  are annual-report figures - Fixed at the point of citation, updated in the
  same commit as the module constant when they move.
- **Sourced spread.** Launch cost per kg is *a scenario input*, not a
  constant, so the module exposes distributions over the documented
  Falcon 9 / Falcon Heavy / Starship ranges. Same for delta-V budgets and
  specific impulse - the REFERENCES.md tables give bands, not points.
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, LogUniform, Uniform

from launch_economics.launch import G0_M_S2
from launch_economics.value import (
    PLATINUM_ANNUAL_PRODUCTION_T,
    PLATINUM_MARKET_ANNUAL_USD,
    PSYCHE_QUOTED_VALUE_USD,
)

# Definitional (exact by SI).
G0_DIST: Distribution = Fixed(G0_M_S2)

# Point-in-time market anchors. Sourced but move over time - update at the
# same time as the module constants.
PLATINUM_MARKET_ANNUAL_DIST: Distribution = Fixed(PLATINUM_MARKET_ANNUAL_USD)
PLATINUM_ANNUAL_PRODUCTION_DIST: Distribution = Fixed(PLATINUM_ANNUAL_PRODUCTION_T)
PSYCHE_QUOTED_VALUE_DIST: Distribution = Fixed(PSYCHE_QUOTED_VALUE_USD)

# Launch cost per kg to LEO (USD/kg). Scenario input, but each rocket has a
# published range.
LAUNCH_COST_FALCON_9_DIST: Distribution = Uniform(low=2500.0, high=3500.0)
LAUNCH_COST_FALCON_HEAVY_DIST: Distribution = Uniform(low=1200.0, high=2000.0)
# Starship is aspirational: <=$100/kg target, no operational price. LogUniform
# over the wide plausible band matches the REFERENCES.md label ~$100-1000/kg.
LAUNCH_COST_STARSHIP_DIST: Distribution = LogUniform(low=100.0, high=1000.0)

# Delta-V budgets (m/s), representative one-way from LEO or surface. Each
# entry is a Uniform over the sourced band.
DELTA_V_SURFACE_TO_LEO_DIST: Distribution = Uniform(low=9300.0, high=10000.0)
DELTA_V_LEO_TO_TLI_DIST: Distribution = Uniform(low=3050.0, high=3150.0)
DELTA_V_LEO_TO_MARS_DIST: Distribution = Uniform(low=3550.0, high=3650.0)
DELTA_V_LEO_TO_ESCAPE_DIST: Distribution = Uniform(low=3150.0, high=3250.0)

# Specific impulse (s) by propellant class. Each Uniform is the vacuum/sea-
# level range.
ISP_LOX_RP1_DIST: Distribution = Uniform(low=280.0, high=340.0)
ISP_LOX_LH2_DIST: Distribution = Uniform(low=440.0, high=460.0)
ISP_ELECTRIC_DIST: Distribution = LogUniform(low=1500.0, high=4000.0)


__all__ = [
    "G0_DIST",
    "PLATINUM_MARKET_ANNUAL_DIST",
    "PLATINUM_ANNUAL_PRODUCTION_DIST",
    "PSYCHE_QUOTED_VALUE_DIST",
    "LAUNCH_COST_FALCON_9_DIST",
    "LAUNCH_COST_FALCON_HEAVY_DIST",
    "LAUNCH_COST_STARSHIP_DIST",
    "DELTA_V_SURFACE_TO_LEO_DIST",
    "DELTA_V_LEO_TO_TLI_DIST",
    "DELTA_V_LEO_TO_MARS_DIST",
    "DELTA_V_LEO_TO_ESCAPE_DIST",
    "ISP_LOX_RP1_DIST",
    "ISP_LOX_LH2_DIST",
    "ISP_ELECTRIC_DIST",
]
