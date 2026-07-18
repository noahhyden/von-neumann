"""Distributional companions to swarm's sourced numbers.

Issue #35 (UQ). swarm's scenario inputs trace verbatim to Nicholson & Forgan
(2013), which uses point values. The honest distributional companions are:

- **C_PC_PER_YEAR**: derived from defined constants (SI c, IAU pc, Julian
  year). Fixed.
- **Powered cruise speed = 3e-5 c**: N&F point value. Real design targets
  span 1e-5 - 1e-4 c depending on propulsion architecture. LogUniform
  captures the full order-of-magnitude spread.
- **Stellar density = 1 star/pc^3**: N&F uniform-density choice. Real solar
  neighborhood is 0.14 stars/pc^3 (RECONS 10-pc census); Milky Way disk
  mean is ~0.4. Uniform(0.1, 1.0) covers "real neighborhood" to "N&F choice".
- **Offspring per settlement**: scenario choice. Fixed at 2 for the paper's
  branching factor.
- **Settle/dwell time**: 0 years default is the paper's "replicate in
  transit" convention. Fixed at 0.
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, LogUniform, Uniform

from swarm.models import C_PC_PER_YEAR

# Derived from SI-defined constants.
C_PC_PER_YEAR_DIST: Distribution = Fixed(C_PC_PER_YEAR)

# Powered cruise speed: 3e-5 c point value, spread across 1e-5 to 1e-4 c
# depending on propulsion architecture. LogUniform is the honest read of
# the order-of-magnitude uncertainty.
POWERED_CRUISE_SPEED_C_DIST: Distribution = LogUniform(low=1e-5, high=1e-4)

# Stellar density spans the RECONS 10-pc census (0.14) to N&F's 1 star/pc^3.
# Uniform captures the "which local density do you use" scenario choice.
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
