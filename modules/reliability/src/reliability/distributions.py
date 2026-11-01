"""Distributional companions to reliability's sourced numbers."""

from __future__ import annotations

from vn_core.uq import Distribution, LogUniform, Uniform

from reliability.degradation import ARRAY_DEGRADATION_BAND_PER_YR
from reliability.mortality import SATELLITE_HAZARD_PER_DAY

ARRAY_DEGRADATION_DIST: Distribution = Uniform(
    low=ARRAY_DEGRADATION_BAND_PER_YR[0],
    high=ARRAY_DEGRADATION_BAND_PER_YR[1],
)

# LogUniform over the satellite-bus hazard range 5e-6 to 2e-5 per day ([ESTIMATE], REFERENCES.md); proxy 1.1e-5 sits inside it.
SATELLITE_HAZARD_PER_DAY_DIST: Distribution = LogUniform(low=5e-6, high=2e-5)


__all__ = [
    "ARRAY_DEGRADATION_DIST",
    "SATELLITE_HAZARD_PER_DAY_DIST",
]
