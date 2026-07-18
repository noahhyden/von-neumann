"""Distributional companions for mission's scenario knobs.

Issue #35 (UQ). mission introduces no new physical quantities - it composes
four sibling modules, and every physical number it uses is sourced there.
So mission's UQ story is: reach into each sibling's `distributions` module
for the distributional companion of the number it consumed, and expose that
here as a re-export. Design-choice knobs (target installed mass, allocation
fractions) stay Fixed at the point of the scenario choice.

Doing this here (not in every downstream caller) means a mission-wide UQ
scan pulls in the honest bands *automatically* the moment sibling modules
tighten or widen a distribution. That is what having a shared `core/` UQ
package earns us at scale.
"""

from __future__ import annotations

from launch_economics.distributions import (
    DELTA_V_SURFACE_TO_LEO_DIST,
    ISP_LOX_RP1_DIST,
    LAUNCH_COST_FALCON_9_DIST,
)
from power_budget.distributions import COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST
from probe_sim.distributions import SOLAR_CELL_EFFICIENCY_DIST
from vn_core.uq import Distribution, Fixed

from mission.scenario import (
    DEFAULT_ARRAY_POWER_AT_1AU_W,
    DEFAULT_FRACTION_COMPUTE,
    DEFAULT_FRACTION_HOUSEKEEPING,
    DEFAULT_FRACTION_MANUFACTURING,
    DEFAULT_TARGET_INSTALLED_MASS_KG,
)

# Sibling-sourced distributions, re-exported so a mission-wide UQ scan
# reaches for the honest band automatically.
ARRAY_EFFICIENCY_DIST: Distribution = SOLAR_CELL_EFFICIENCY_DIST
DELTA_V_M_S_DIST: Distribution = DELTA_V_SURFACE_TO_LEO_DIST
SPECIFIC_IMPULSE_S_DIST: Distribution = ISP_LOX_RP1_DIST
COST_PER_KG_USD_DIST: Distribution = LAUNCH_COST_FALCON_9_DIST
COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST_MISSION: Distribution = (
    COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST
)

# Mission-level design choices: Fixed at the point of the scenario choice.
# When the scenario changes them, they change here in the same commit.
ARRAY_POWER_AT_1AU_DIST: Distribution = Fixed(DEFAULT_ARRAY_POWER_AT_1AU_W)
TARGET_INSTALLED_MASS_DIST: Distribution = Fixed(DEFAULT_TARGET_INSTALLED_MASS_KG)
FRACTION_MANUFACTURING_DIST: Distribution = Fixed(DEFAULT_FRACTION_MANUFACTURING)
FRACTION_COMPUTE_DIST: Distribution = Fixed(DEFAULT_FRACTION_COMPUTE)
FRACTION_HOUSEKEEPING_DIST: Distribution = Fixed(DEFAULT_FRACTION_HOUSEKEEPING)


__all__ = [
    "ARRAY_EFFICIENCY_DIST",
    "DELTA_V_M_S_DIST",
    "SPECIFIC_IMPULSE_S_DIST",
    "COST_PER_KG_USD_DIST",
    "COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST_MISSION",
    "ARRAY_POWER_AT_1AU_DIST",
    "TARGET_INSTALLED_MASS_DIST",
    "FRACTION_MANUFACTURING_DIST",
    "FRACTION_COMPUTE_DIST",
    "FRACTION_HOUSEKEEPING_DIST",
]
