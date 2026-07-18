"""Distributional companions to every sourced probe-sim number.

Issue #35's central claim is that a **spread is a citable claim in its own
right**. This module names the honest distribution for each REFERENCES.md
entry - callers reach here (not for the point value) when they run UQ.

Each entry does one of three things:
- **Sourced spread**: mean AND spread come from the same reference (or a
  companion reference); the distribution stands on its own citation.
- **`[GAP]` spread**: mean is sourced, but no source names a spread. Kept as
  `Fixed(value)` here rather than inventing a plausible-looking Gaussian.
  Callers using UQ will see zero contribution from this input in Sobol - the
  honest outcome, not a bug.
- **Deterministic**: the underlying quantity is a definition (e.g. an AU), so
  `Fixed` is not a gap, it is correct.

Every symbol below is annotated with which case it is. When a new source
appears, the annotation and the distribution update together, in the same
change - never one without the other (CLAUDE.md §1).
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, Normal, Uniform

from probe_sim.environment import (
    AU_DISTANCE,
    SOLAR_CONSTANT_1AU_W_M2,
    SOLAR_CONSTANT_1AU_W_M2_STD,
)
from probe_sim.models import REPLICATED_MASS_FRACTION

# --- Sourced spread ---------------------------------------------------------

# Total Solar Irradiance at 1 AU. Kopp & Lean (2011) report 1360.8 +/- 0.5 W/m^2,
# so both the mean and the std cite the same source. Solid.
SOLAR_CONSTANT_1AU_DIST: Distribution = Normal(
    mean=SOLAR_CONSTANT_1AU_W_M2,
    std=SOLAR_CONSTANT_1AU_W_M2_STD,
)

# Solar-cell efficiency for a space multi-junction cell. The reported operating
# range in Landis & Bailey (2002) for triple-junction GaInP/GaAs/Ge cells is
# ~28-32% AM0; Uniform over that range is the honest read when the source gives
# an interval, not a shape. `[ESTIMATE]` until a specific cell (with a
# manufacturer datasheet range) is chosen for a scenario.
SOLAR_CELL_EFFICIENCY_DIST: Distribution = Uniform(low=0.28, high=0.32)


# --- [GAP] spread -----------------------------------------------------------

# Borgue & Hein (2020) state "replicates ~70% of its mass" as a design target;
# the paper does not report a spread on that fraction. Rather than invent a
# Gaussian, we hold it as `Fixed(0.70)` and let Sobol read this input as
# zero-contribution. The honest outcome is "70% is the point value and the UQ
# does not know the spread" - which is exactly what the [GAP] system tracks.
# When a source names a spread (a design-margin table, a variant analysis),
# widen this to `Uniform`/`Normal` in the same change.
REPLICATED_MASS_FRACTION_DIST: Distribution = Fixed(REPLICATED_MASS_FRACTION)


# --- Deterministic ----------------------------------------------------------

# Mean heliocentric distances (NASA planetary fact sheet). These are defined
# constants of the solar-system reference model at the fidelity probe-sim uses;
# the true instantaneous distance varies with orbital phase but the *mean* is
# not a random variable in the UQ sense. Fixed is correct, not a gap.
AU_DISTANCE_DIST: dict[str, Distribution] = {
    name: Fixed(value) for name, value in AU_DISTANCE.items()
}


__all__ = [
    "SOLAR_CONSTANT_1AU_DIST",
    "SOLAR_CELL_EFFICIENCY_DIST",
    "REPLICATED_MASS_FRACTION_DIST",
    "AU_DISTANCE_DIST",
]
