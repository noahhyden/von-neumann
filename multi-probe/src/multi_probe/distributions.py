"""Distributional companions for multi-probe."""

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
