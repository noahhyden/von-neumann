"""Deterministic degradation: solar arrays wear out, and dose accumulates.

Every current model in the project is failure-free and un-ageing - a probe's array
delivers the same power on day 6000 as on day 1. Reality is not so kind: flight-measured
arrays lose a fraction of a percent to a percent of their output every year, and the
loss accelerates near the Sun and inside Jupiter's radiation belts. This is the
deterministic (no-RNG) half of `reliability`.

Cumulative radiation dose is the same idea for the electronics: it just adds up with
time, and it drives the mortality hazard in `mortality.py`. The dose rate comes from the
shared `shielding.radenv` primitive (one radiation environment, not two).

Numbers in REFERENCES.md; pure functions, no RNG here (that is mortality.py).
"""

from __future__ import annotations

from shielding.radenv import GCR_DEEP_SPACE_DOSE_MSV_PER_DAY

# Solar-array power loss per year (fraction). ISS P6 arrays: 0.2-0.5 %/yr (flight-
# measured); GEO GaAs cells 0.44-1.03 %/yr. Default is the ISS mid-range. See REFERENCES.
ARRAY_DEGRADATION_PER_YR: float = 0.003
ARRAY_DEGRADATION_BAND_PER_YR: tuple[float, float] = (0.002, 0.010)


def array_power_fraction(
    years: float,
    degradation_per_yr: float = ARRAY_DEGRADATION_PER_YR,
    environment_multiplier: float = 1.0,
) -> float:
    """Fraction of original array power left after some years (compounding annual loss).

    (1 - rate)^years, with rate = degradation_per_yr x environment_multiplier. The
    multiplier is >1 near the Sun or in the Jovian belts, where degradation accelerates
    (a documented parameter, not a sub-simulation). Returns 1.0 at t=0.
    """
    if years < 0:
        raise ValueError("years must be non-negative")
    if not 0.0 <= degradation_per_yr < 1.0:
        raise ValueError("degradation_per_yr must be in [0, 1)")
    if environment_multiplier <= 0:
        raise ValueError("environment_multiplier must be positive")
    rate = degradation_per_yr * environment_multiplier
    if rate >= 1.0:
        raise ValueError("effective degradation rate reached/exceeded 1/yr")
    return (1.0 - rate) ** years


def cumulative_gcr_dose_msv(
    days: float, dose_rate_msv_per_day: float = GCR_DEEP_SPACE_DOSE_MSV_PER_DAY
) -> float:
    """Cumulative GCR dose-equivalent (mSv) over a number of days: rate x days.

    Uses the shared radenv deep-space rate by default (single source of truth for the
    radiation environment).
    """
    if days < 0:
        raise ValueError("days must be non-negative")
    if dose_rate_msv_per_day < 0:
        raise ValueError("dose_rate_msv_per_day must be non-negative")
    return dose_rate_msv_per_day * days
