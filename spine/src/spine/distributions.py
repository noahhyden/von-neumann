"""Distributional companions for spine.

spine is an integrator that introduces no new physical numbers - every value
it reports traces to a sibling module's `distributions`. The only spine-owned
constant is `DAYS_PER_JULIAN_YEAR = 365.25`, derived from the IAU / SI clock
convention; `Fixed` is correct.

To run a spine-level UQ, callers reach for the sibling `distributions`
directly (probe-sim, closure-sim, multi-probe, swarm). No re-export is
needed here because spine's own outputs are derived from those, not
independently parametrised.
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed

from spine.run import DAYS_PER_JULIAN_YEAR

DAYS_PER_JULIAN_YEAR_DIST: Distribution = Fixed(DAYS_PER_JULIAN_YEAR)


__all__ = ["DAYS_PER_JULIAN_YEAR_DIST"]
