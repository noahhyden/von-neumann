"""Distributional companions to launch-economics' sourced numbers."""

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

# Point-in-time market anchors: sourced but they move over time, so update them in the same commit as the module constants.
PLATINUM_MARKET_ANNUAL_DIST: Distribution = Fixed(PLATINUM_MARKET_ANNUAL_USD)
PLATINUM_ANNUAL_PRODUCTION_DIST: Distribution = Fixed(PLATINUM_ANNUAL_PRODUCTION_T)
PSYCHE_QUOTED_VALUE_DIST: Distribution = Fixed(PSYCHE_QUOTED_VALUE_USD)

# Launch cost per kg to LEO (USD/kg): a scenario input, but each rocket has a published range (REFERENCES.md).
LAUNCH_COST_FALCON_9_DIST: Distribution = Uniform(low=2500.0, high=3500.0)
LAUNCH_COST_FALCON_HEAVY_DIST: Distribution = Uniform(low=1200.0, high=2000.0)
# Starship is aspirational (<=$100/kg target, no operational price), so a LogUniform over ~$100-1000/kg matches the REFERENCES.md label.
LAUNCH_COST_STARSHIP_DIST: Distribution = LogUniform(low=100.0, high=1000.0)

# Delta-V budgets (m/s), representative one-way from LEO or surface; each entry is a Uniform over the sourced band in REFERENCES.md.
DELTA_V_SURFACE_TO_LEO_DIST: Distribution = Uniform(low=9300.0, high=10000.0)
DELTA_V_LEO_TO_TLI_DIST: Distribution = Uniform(low=3050.0, high=3150.0)
DELTA_V_LEO_TO_MARS_DIST: Distribution = Uniform(low=3550.0, high=3650.0)
DELTA_V_LEO_TO_ESCAPE_DIST: Distribution = Uniform(low=3150.0, high=3250.0)

# Specific impulse (s) by propellant class; each Uniform is the vacuum-to-sea-level range (REFERENCES.md).
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
