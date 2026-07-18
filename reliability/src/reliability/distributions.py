"""Distributional companions to reliability's sourced numbers.

Issue #35 (UQ). reliability's constants:

- Array degradation per year: source explicitly gives a (0.002, 0.010) band
  spanning ISS P6 (0.2-0.5%/yr) to GEO GaAs (0.44-1.03%/yr).
- Satellite proxy hazard 1.1e-5/day: [ESTIMATE] - source flags the analog
  status. Real satellite hazards span 5e-6 to 2e-5 per day depending on
  bus class. LogUniform captures the order-of-magnitude spread.
"""

from __future__ import annotations

from vn_core.uq import Distribution, LogUniform, Uniform

from reliability.degradation import ARRAY_DEGRADATION_BAND_PER_YR
from reliability.mortality import SATELLITE_HAZARD_PER_DAY

ARRAY_DEGRADATION_DIST: Distribution = Uniform(
    low=ARRAY_DEGRADATION_BAND_PER_YR[0],
    high=ARRAY_DEGRADATION_BAND_PER_YR[1],
)

# LogUniform over the satellite-bus hazard range.
SATELLITE_HAZARD_PER_DAY_DIST: Distribution = LogUniform(low=5e-6, high=2e-5)


__all__ = [
    "ARRAY_DEGRADATION_DIST",
    "SATELLITE_HAZARD_PER_DAY_DIST",
]
