"""Deep-space downlink data rate versus distance, and the data-return wall."""

from __future__ import annotations

from dataclasses import dataclass

# DSOC optical calibration fit to JPL's two verified-rate anchors (25 Mbps at 1.506 AU -> k=56.7; 8.3 Mbps at 2.582 AU -> k=55.3; agree to ~2.5%), adopted as k for the power-limited branch; see REFERENCES.md.
K_OPTICAL_MBPS_AU2: float = 56.0

# DSOC modem/protocol ceiling, Mbps - the rate-limited plateau near Earth.
R_MAX_DSOC_MBPS: float = 267.0

BITS_PER_MBIT: float = 1.0e6


@dataclass(frozen=True)
class BacklogResult:
    """Bits generated vs returned over a duration at a fixed distance."""

    generated_bits: float
    returned_bits: float
    backlog_bits: float
    return_rate_bits_per_s: float
    is_wall: bool


def calibrate_k(rate_mbps: float, distance_au: float) -> float:
    """Fit the power-limited constant k (Mbps*AU^2) from a mission anchor: k = R * d^2."""
    if rate_mbps <= 0:
        raise ValueError("rate_mbps must be positive")
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    return rate_mbps * distance_au * distance_au


def crossover_distance_au(k_mbps_au2: float, r_max_mbps: float) -> float:
    """Distance where the two regimes meet: d_cross = sqrt(k / R_max)."""
    if k_mbps_au2 <= 0 or r_max_mbps <= 0:
        raise ValueError("k and r_max must be positive")
    return (k_mbps_au2 / r_max_mbps) ** 0.5


def data_rate_at(
    distance_au: float,
    *,
    k_mbps_au2: float = K_OPTICAL_MBPS_AU2,
    r_max_mbps: float = R_MAX_DSOC_MBPS,
) -> float:
    """Downlink rate (Mbps) at an Earth-range distance: min(k/d^2, R_max)."""
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    if k_mbps_au2 <= 0 or r_max_mbps <= 0:
        raise ValueError("k and r_max must be positive")
    power_limited = k_mbps_au2 / (distance_au * distance_au)
    return min(power_limited, r_max_mbps)


def return_backlog(
    generated_bits_per_s: float,
    distance_au: float,
    duration_s: float,
    *,
    k_mbps_au2: float = K_OPTICAL_MBPS_AU2,
    r_max_mbps: float = R_MAX_DSOC_MBPS,
) -> BacklogResult:
    """Bits generated vs returned over a duration; positive backlog = the wall."""
    if generated_bits_per_s < 0:
        raise ValueError("generated_bits_per_s must be non-negative")
    if duration_s < 0:
        raise ValueError("duration_s must be non-negative")

    link_bits_per_s = data_rate_at(
        distance_au, k_mbps_au2=k_mbps_au2, r_max_mbps=r_max_mbps
    ) * BITS_PER_MBIT

    generated = generated_bits_per_s * duration_s
    returned = min(generated_bits_per_s, link_bits_per_s) * duration_s
    backlog = generated - returned
    return BacklogResult(
        generated_bits=generated,
        returned_bits=returned,
        backlog_bits=backlog,
        return_rate_bits_per_s=link_bits_per_s,
        is_wall=generated_bits_per_s > link_bits_per_s,
    )


def aggregate_return_rate_mbps(
    distances_au: list[float],
    *,
    k_mbps_au2: float = K_OPTICAL_MBPS_AU2,
    r_max_mbps: float = R_MAX_DSOC_MBPS,
) -> float:
    """Total returnable rate (Mbps) across a fleet: sum of each probe's link rate."""
    return sum(
        data_rate_at(d, k_mbps_au2=k_mbps_au2, r_max_mbps=r_max_mbps)
        for d in distances_au
    )
