"""Distributional companions to transfer's sourced numbers.

Issue #35 (UQ). transfer's constants split cleanly:

- **Definitional / measured to high precision**: heliocentric gravitational
  parameter (JPL DE441 header), the AU definition (IAU 2012), seconds per
  day (SI). All Fixed - no meaningful spread.
- **Sourced orbital elements**: `BODY_SEMI_MAJOR_AXIS_AU` and
  `BODY_SIDEREAL_PERIOD_DAYS` are the NASA fact-sheet mean values. Also
  Fixed at the fidelity transfer uses (Hohmann approximations).
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed

from transfer.orbits import (
    AU_M,
    BODY_SEMI_MAJOR_AXIS_AU,
    BODY_SIDEREAL_PERIOD_DAYS,
    GM_SUN_M3_S2,
    SECONDS_PER_DAY,
)

GM_SUN_DIST: Distribution = Fixed(GM_SUN_M3_S2)
AU_M_DIST: Distribution = Fixed(AU_M)
SECONDS_PER_DAY_DIST: Distribution = Fixed(SECONDS_PER_DAY)

BODY_SEMI_MAJOR_AXIS_AU_DIST: dict[str, Distribution] = {
    name: Fixed(v) for name, v in BODY_SEMI_MAJOR_AXIS_AU.items()
}
BODY_SIDEREAL_PERIOD_DAYS_DIST: dict[str, Distribution] = {
    name: Fixed(v) for name, v in BODY_SIDEREAL_PERIOD_DAYS.items()
}


__all__ = [
    "GM_SUN_DIST",
    "AU_M_DIST",
    "SECONDS_PER_DAY_DIST",
    "BODY_SEMI_MAJOR_AXIS_AU_DIST",
    "BODY_SIDEREAL_PERIOD_DAYS_DIST",
]
