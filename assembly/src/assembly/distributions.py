"""Distributional companions to assembly's sourced numbers.

Issue #35 (UQ). assembly's constants:

- HOURS_PER_DAY: definitional -> Fixed.
- WAAM / LPBF rates: source explicitly gives (low, high) tuples -> Uniform.
- OEE anchors: WORLD_CLASS (0.85) and TYPICAL (0.60) point values sit inside
  a documented industrial spread; expose bands around each.
- AASM seed mass and self-copy days: NASA CP-2255 design-point anchors, Fixed.
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, Uniform

from assembly.rate import (
    AASM_SEED_MASS_KG,
    AASM_SELF_COPY_DAYS,
    HOURS_PER_DAY,
    LPBF_RATE_KG_PER_H,
    TYPICAL_OEE,
    WAAM_RATE_KG_PER_H,
    WORLD_CLASS_OEE,
    WORLD_CLASS_QUALITY,
)

HOURS_PER_DAY_DIST: Distribution = Fixed(HOURS_PER_DAY)

# Sourced deposition-rate bands from REFERENCES.md.
WAAM_RATE_DIST: Distribution = Uniform(low=WAAM_RATE_KG_PER_H[0], high=WAAM_RATE_KG_PER_H[1])
LPBF_RATE_DIST: Distribution = Uniform(low=LPBF_RATE_KG_PER_H[0], high=LPBF_RATE_KG_PER_H[1])

# OEE bands: Nakajima's world-class is a *floor*, so above 0.85 possible;
# typical discrete manufacturing spreads roughly 0.50-0.70.
WORLD_CLASS_OEE_DIST: Distribution = Uniform(low=0.80, high=0.90)
TYPICAL_OEE_DIST: Distribution = Uniform(low=0.50, high=0.70)
WORLD_CLASS_QUALITY_DIST: Distribution = Uniform(low=0.995, high=0.9999)

# NASA CP-2255 anchor - a specific reference design, Fixed.
AASM_SEED_MASS_DIST: Distribution = Fixed(AASM_SEED_MASS_KG)
AASM_SELF_COPY_DAYS_DIST: Distribution = Fixed(AASM_SELF_COPY_DAYS)


__all__ = [
    "HOURS_PER_DAY_DIST",
    "WAAM_RATE_DIST",
    "LPBF_RATE_DIST",
    "WORLD_CLASS_OEE_DIST",
    "TYPICAL_OEE_DIST",
    "WORLD_CLASS_QUALITY_DIST",
    "AASM_SEED_MASS_DIST",
    "AASM_SELF_COPY_DAYS_DIST",
]
