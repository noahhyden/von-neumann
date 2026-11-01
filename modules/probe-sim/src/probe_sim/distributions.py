"""Distributional companions to every sourced probe-sim number."""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, Normal, Uniform

from probe_sim.environment import (
    AU_DISTANCE,
    SOLAR_CONSTANT_1AU_W_M2,
    SOLAR_CONSTANT_1AU_W_M2_STD,
)
from probe_sim.models import REPLICATED_MASS_FRACTION

# --- Sourced spread ---------------------------------------------------------

# Total Solar Irradiance at 1 AU: Kopp & Lean (2011) 1360.8 +/- 0.5 W/m^2, mean and std from the same source.
SOLAR_CONSTANT_1AU_DIST: Distribution = Normal(
    mean=SOLAR_CONSTANT_1AU_W_M2,
    std=SOLAR_CONSTANT_1AU_W_M2_STD,
)

# Space multi-junction cell efficiency: Landis & Bailey (2002) ~28-32% AM0, Uniform over that interval, [ESTIMATE] until a specific cell is chosen.
SOLAR_CELL_EFFICIENCY_DIST: Distribution = Uniform(low=0.28, high=0.32)


# --- [GAP] spread -----------------------------------------------------------

# Borgue & Hein (2020) give "replicates ~70% of its mass" with no spread, so it stays Fixed (a [GAP], zero Sobol contribution) rather than an invented Gaussian.
REPLICATED_MASS_FRACTION_DIST: Distribution = Fixed(REPLICATED_MASS_FRACTION)


# --- Deterministic ----------------------------------------------------------

# Mean heliocentric distances (NASA planetary fact sheet): definitional constants, so Fixed is correct and not a gap.
AU_DISTANCE_DIST: dict[str, Distribution] = {
    name: Fixed(value) for name, value in AU_DISTANCE.items()
}


__all__ = [
    "SOLAR_CONSTANT_1AU_DIST",
    "SOLAR_CELL_EFFICIENCY_DIST",
    "REPLICATED_MASS_FRACTION_DIST",
    "AU_DISTANCE_DIST",
]
