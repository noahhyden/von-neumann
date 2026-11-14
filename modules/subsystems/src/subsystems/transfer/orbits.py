"""Impulsive (high-thrust) heliocentric transfers between circular coplanar orbits."""

from __future__ import annotations

import math
from dataclasses import dataclass

# Heliocentric gravitational parameter GM_sun, m^3/s^2: IAU 2015 nominal value (GM_sun^N = 1.3271244e20), defined not measured; see REFERENCES.md.
GM_SUN_M3_S2: float = 1.32712440018e20

# Astronomical unit, m. IAU 2012 exact definition. See REFERENCES.md.
AU_M: float = 1.495978707e11

# Seconds per day (exact: 86400 SI seconds).
SECONDS_PER_DAY: float = 86_400.0

# Reference heliocentric semi-major axes, AU: Earth/Mars/Jupiter from the NASA Planetary Fact Sheet, Ceres from the JPL small-body database; transfer inputs, not constants (REFERENCES.md).
BODY_SEMI_MAJOR_AXIS_AU: dict[str, float] = {
    "earth": 1.0000,
    "mars": 1.5237,
    "ceres": 2.77,
    "jupiter": 5.2034,
}

# Reference sidereal orbital periods, days (NASA Planetary Fact Sheet): inputs to the synodic-period cadence, documented here rather than hardcoded in the model.
BODY_SIDEREAL_PERIOD_DAYS: dict[str, float] = {
    "earth": 365.256,
    "mars": 686.980,
}


@dataclass(frozen=True)
class HohmannResult:
    """A two-burn Hohmann transfer between two circular coplanar heliocentric orbits."""

    dv1_m_s: float
    dv2_m_s: float
    dv_total_m_s: float
    transfer_time_days: float

    def __post_init__(self) -> None:
        # [inv:tr-hohmann] dv_total is a magnitude sum (>= 0) over a positive transfer time; dv1/dv2 signs are meaningful and not constrained.
        if self.dv_total_m_s < 0:
            raise ValueError(
                f"[inv:tr-hohmann] dv_total_m_s={self.dv_total_m_s} must be >= 0"
            )
        eps = 1e-9 * (abs(self.dv1_m_s) + abs(self.dv2_m_s) + 1.0)
        expected_total = abs(self.dv1_m_s) + abs(self.dv2_m_s)
        if abs(self.dv_total_m_s - expected_total) > eps:
            raise ValueError(
                f"[inv:tr-hohmann] dv_total={self.dv_total_m_s} != |dv1|+|dv2|={expected_total}"
            )
        if self.transfer_time_days <= 0:
            raise ValueError(
                f"[inv:tr-hohmann] transfer_time_days={self.transfer_time_days} must be > 0"
            )


def circular_orbital_speed_m_s(radius_au: float) -> float:
    """Circular heliocentric orbital speed (m/s) at a radius: v = sqrt(GM_sun / r)."""
    if radius_au <= 0:
        raise ValueError("radius_au must be positive")
    r = radius_au * AU_M
    return math.sqrt(GM_SUN_M3_S2 / r)


def hohmann_transfer(r1_au: float, r2_au: float) -> HohmannResult:
    """Two-burn heliocentric Hohmann Δv (m/s) and transfer time (days)."""
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
    """Synodic period (days) - the launch-window cadence between two orbits."""
    if period1_days <= 0 or period2_days <= 0:
        raise ValueError("orbital periods must be positive")
    inv_diff = abs(1.0 / period1_days - 1.0 / period2_days)
    if inv_diff == 0.0:
        raise ValueError("equal orbital periods have no finite synodic period")
    return 1.0 / inv_diff
