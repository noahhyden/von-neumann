"""Distributional companions for multi-probe.

multi-probe introduces no new physical constants - the physics it uses is
sourced in the sibling modules it composes. Its "distributions" are, like
mission's, re-exports of the honest bands owned upstream.

Scenario choices (manufacturing fraction 0.70, array size derived from the
mission's 4 MW / 30% efficiency line) stay Fixed at the point of the
scenario choice.
"""

from __future__ import annotations

from probe_sim.distributions import SOLAR_CELL_EFFICIENCY_DIST
from vn_core.uq import Distribution, Fixed

# Sibling-sourced.
ARRAY_EFFICIENCY_DIST: Distribution = SOLAR_CELL_EFFICIENCY_DIST

# Design-choice defaults for the fleet scenario. Match mission's split.
DEFAULT_FRACTION_MANUFACTURING_DIST: Distribution = Fixed(0.70)


__all__ = [
    "ARRAY_EFFICIENCY_DIST",
    "DEFAULT_FRACTION_MANUFACTURING_DIST",
]
