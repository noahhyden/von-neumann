"""Distributional companions to comms' sourced numbers."""

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
