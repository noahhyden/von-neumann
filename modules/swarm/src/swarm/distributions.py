"""Distributional companions to swarm's sourced numbers."""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, LogUniform, Uniform

from swarm.models import C_PC_PER_YEAR

# Derived from SI-defined constants.
C_PC_PER_YEAR_DIST: Distribution = Fixed(C_PC_PER_YEAR)

# Powered cruise speed: 3e-5 c point value, spread across 1e-5 to 1e-4 c depending on propulsion architecture.
POWERED_CRUISE_SPEED_C_DIST: Distribution = LogUniform(low=1e-5, high=1e-4)

# Stellar density spans the RECONS 10-pc census (0.14) to N&F's 1 star/pc^3.
STELLAR_DENSITY_PER_PC3_DIST: Distribution = Uniform(low=0.1, high=1.0)

# Offspring per settlement: scenario branching factor; N&F fix at 2.
OFFSPRING_PER_SETTLEMENT_DIST: Distribution = Fixed(2.0)

# Settle/dwell time: 0 by paper convention.
SETTLE_DWELL_YEARS_DIST: Distribution = Fixed(0.0)


__all__ = [
    "C_PC_PER_YEAR_DIST",
    "POWERED_CRUISE_SPEED_C_DIST",
    "STELLAR_DENSITY_PER_PC3_DIST",
    "OFFSPRING_PER_SETTLEMENT_DIST",
    "SETTLE_DWELL_YEARS_DIST",
]
