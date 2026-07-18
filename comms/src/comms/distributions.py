"""Distributional companions to comms' sourced numbers.

Issue #35 (UQ). comms' constants have small documented spreads:

- **K_OPTICAL_MBPS_AU2**: fit to two verified DSOC anchors, k=56.7 and
  k=55.3 - the +/- ~1% agreement between them IS the honest error bar.
  Uniform(55.3, 56.7).
- **R_MAX_DSOC_MBPS**: the modem/protocol ceiling as published; DSOC has
  demonstrated up to ~267 Mbps but the near-Earth plateau in practice
  runs 200-267 Mbps depending on link margin. Uniform(200, 267).
- **BITS_PER_MBIT**: definitional (unit conversion). Fixed.
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, Uniform

from comms.link import BITS_PER_MBIT

K_OPTICAL_MBPS_AU2_DIST: Distribution = Uniform(low=55.3, high=56.7)
R_MAX_DSOC_MBPS_DIST: Distribution = Uniform(low=200.0, high=267.0)
BITS_PER_MBIT_DIST: Distribution = Fixed(BITS_PER_MBIT)


__all__ = [
    "K_OPTICAL_MBPS_AU2_DIST",
    "R_MAX_DSOC_MBPS_DIST",
    "BITS_PER_MBIT_DIST",
]
