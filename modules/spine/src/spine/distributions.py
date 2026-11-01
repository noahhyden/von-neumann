"""Distributional companions for spine."""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed

from spine.run import DAYS_PER_JULIAN_YEAR

DAYS_PER_JULIAN_YEAR_DIST: Distribution = Fixed(DAYS_PER_JULIAN_YEAR)


__all__ = ["DAYS_PER_JULIAN_YEAR_DIST"]
