"""Impulsive (high-thrust) heliocentric transfers between circular coplanar orbits.

The classical two-burn Hohmann transfer is the minimum-Δv way to move between two
circular coplanar orbits, and its transfer time is exactly half the period of the
transfer ellipse. Both fall out of the vis-viva equation and depend only on the Sun's
gravitational parameter and the two orbital radii - no ephemeris, no optimizer.

The synodic period is the launch-window cadence: how often the geometry between two
bodies repeats. It sets how long you wait between opportunities, independent of the
transfer itself.

Only defined/measured constants are hardcoded (GM_sun, the AU); orbital radii are
inputs, with representative sourced values in REFERENCES.md. Deterministic, plain
data, zero pimas imports (CLAUDE.md §7). SI units internally: metres, seconds; the
public API takes AU and returns days for readability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Heliocentric gravitational parameter GM_sun, m^3/s^2. IAU 2015 nominal solar mass
# parameter (GM_sun^N = 1.3271244e20). Defined nominal value. See REFERENCES.md.
GM_SUN_M3_S2: float = 1.32712440018e20

# Astronomical unit, m. IAU 2012 exact definition. See REFERENCES.md.
AU_M: float = 1.495978707e11

# Seconds per day (exact: 86400 SI seconds).
SECONDS_PER_DAY: float = 86_400.0

# Reference heliocentric semi-major axes, AU. Earth/Mars/Jupiter from the NASA
# Planetary Fact Sheet; Ceres (main-belt reference) from the JPL small-body database.
# These are transfer *inputs*, not physical constants of this module - documented here
# so scenarios and tests can cite one place. See REFERENCES.md.
BODY_SEMI_MAJOR_AXIS_AU: dict[str, float] = {
    "earth": 1.0000,
    "mars": 1.5237,
    "ceres": 2.77,
    "jupiter": 5.2034,
}

# Reference sidereal orbital periods, days (NASA Planetary Fact Sheet). Inputs to the
# synodic-period cadence, documented here rather than hardcoded in the model.
BODY_SIDEREAL_PERIOD_DAYS: dict[str, float] = {
    "earth": 365.256,
    "mars": 686.980,
}


@dataclass(frozen=True)
class HohmannResult:
    """A two-burn Hohmann transfer between two circular coplanar heliocentric orbits.

    All speeds in m/s, time in days. dv1 is the departure (perihelion/aphelion) burn,
    dv2 the arrival circularization burn; dv_total is their magnitude sum.
    """

    dv1_m_s: float
    dv2_m_s: float
    dv_total_m_s: float
    transfer_time_days: float


def circular_orbital_speed_m_s(radius_au: float) -> float:
    """Circular heliocentric orbital speed (m/s) at a radius: v = sqrt(GM_sun / r)."""
    if radius_au <= 0:
        raise ValueError("radius_au must be positive")
    r = radius_au * AU_M
    return math.sqrt(GM_SUN_M3_S2 / r)


def hohmann_transfer(r1_au: float, r2_au: float) -> HohmannResult:
    """Two-burn heliocentric Hohmann Δv (m/s) and transfer time (days).

    Vis-viva gives the circular speeds v1, v2 and the transfer-ellipse speeds at
    each apse:
        dv1 = v1 * (sqrt(2 r2 / (r1 + r2)) - 1)     departure burn
        dv2 = v2 * (1 - sqrt(2 r1 / (r1 + r2)))     arrival burn
        t   = pi * sqrt((r1 + r2)^3 / (8 GM_sun))   half the transfer-ellipse period
    Signs are preserved before summing magnitudes, so an inward transfer (r2 < r1)
    is handled symmetrically. Same orbit (r1 == r2) yields exactly zero Δv and a
    transfer time of half the orbital period.
    """
    if r1_au <= 0 or r2_au <= 0:
        raise ValueError("orbital radii must be positive")

    r1 = r1_au * AU_M
    r2 = r2_au * AU_M
    mu = GM_SUN_M3_S2

    v1 = math.sqrt(mu / r1)
    v2 = math.sqrt(mu / r2)

    dv1 = v1 * (math.sqrt(2.0 * r2 / (r1 + r2)) - 1.0)
    dv2 = v2 * (1.0 - math.sqrt(2.0 * r1 / (r1 + r2)))
    dv_total = abs(dv1) + abs(dv2)

    t_s = math.pi * math.sqrt((r1 + r2) ** 3 / (8.0 * mu))
    return HohmannResult(
        dv1_m_s=dv1,
        dv2_m_s=dv2,
        dv_total_m_s=dv_total,
        transfer_time_days=t_s / SECONDS_PER_DAY,
    )


def synodic_period_days(period1_days: float, period2_days: float) -> float:
    """Synodic period (days) - the launch-window cadence between two orbits.

    T_syn = 1 / |1/T1 - 1/T2|. For equal periods the geometry never repeats
    (infinite synodic period); raise rather than divide by zero.
    """
    if period1_days <= 0 or period2_days <= 0:
        raise ValueError("orbital periods must be positive")
    inv_diff = abs(1.0 / period1_days - 1.0 / period2_days)
    if inv_diff == 0.0:
        raise ValueError("equal orbital periods have no finite synodic period")
    return 1.0 / inv_diff
