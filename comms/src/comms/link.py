"""Deep-space downlink data rate versus distance, and the data-return wall.

A deep-space link has two regimes. Far out it is **power-limited**: the achievable
data rate falls as the inverse square of distance. This is not an assumption - it
falls out of Shannon meeting Friis. Friis gives received power `Pr proportional 1/d^2`;
Shannon capacity is `C = B log2(1 + Pr/(N0 B))`; in the power-limited (below-noise)
wideband limit `log2(1+x) -> x/ln2`, so `C -> Pr/(N0 ln2) proportional 1/d^2`,
independent of bandwidth. JPL's DSOC demonstration confirmed the 1/d^2 shape directly.

Near Earth the link is instead **rate-limited**: the modem/protocol tops out at a
hardware ceiling `R_max` (DSOC's 267 Mbps plateau) and cannot go faster no matter how
strong the signal. So the achievable rate is `R(d) = min(k/d^2, R_max)`, where `k` is
a single calibration constant fit to one real mission anchor.

The payoff is the **data-return wall**: a probe generates science bits far faster than
a power-limited link can return them, so a backlog grows without bound and aggregate
knowledge across a fleet saturates at the sum of per-probe link rates, not at probe
count.

Distance here is the **Earth-spacecraft range**, NOT heliocentric distance - they
differ by up to ~2 AU near Earth (CLAUDE.md §1: pin the basis). Deterministic, plain
data, zero pimas imports, no RNG (CLAUDE.md §7). All figures sourced in REFERENCES.md.
"""

from __future__ import annotations

from dataclasses import dataclass

# DSOC optical calibration, fit to JPL's two published verified-rate anchors
# (25 Mbps at 1.506 AU -> k=56.7; 8.3 Mbps at 2.582 AU -> k=55.3; agree to ~2.5%).
# Adopted k for the power-limited branch. See REFERENCES.md.
K_OPTICAL_MBPS_AU2: float = 56.0

# DSOC modem/protocol ceiling, Mbps - the rate-limited plateau near Earth.
R_MAX_DSOC_MBPS: float = 267.0

BITS_PER_MBIT: float = 1.0e6


@dataclass(frozen=True)
class BacklogResult:
    """Bits generated vs returned over a duration at a fixed distance.

    A positive backlog_bits is the data-return wall: the probe is producing science
    faster than its link can send it home. saturated is True when the link is running
    at its full rate the whole duration (return is link-limited, not supply-limited).
    """

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
    """Distance where the two regimes meet: d_cross = sqrt(k / R_max).

    Inside d_cross the link is rate-limited (clamped at R_max); outside, power-limited
    (k/d^2).
    """
    if k_mbps_au2 <= 0 or r_max_mbps <= 0:
        raise ValueError("k and r_max must be positive")
    return (k_mbps_au2 / r_max_mbps) ** 0.5


def data_rate_at(
    distance_au: float,
    *,
    k_mbps_au2: float = K_OPTICAL_MBPS_AU2,
    r_max_mbps: float = R_MAX_DSOC_MBPS,
) -> float:
    """Downlink rate (Mbps) at an Earth-range distance: min(k/d^2, R_max).

    Near Earth the min picks R_max (rate-limited); far out it picks k/d^2
    (power-limited). Never blows up as d -> 0 (clamped), goes to 0 as d -> infinity.
    """
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
    """Bits generated vs returned over a duration; positive backlog = the wall.

    Return rate is `data_rate_at(distance)` in bits/s. If the probe generates faster
    than that, the un-returned remainder accumulates as backlog. The link runs at its
    full rate whenever there is anything to send, so returned = min(generation,
    link-rate) * duration.
    """
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
    """Total returnable rate (Mbps) across a fleet: sum of each probe's link rate.

    Once every link is saturated, aggregate knowledge return is bounded by this sum -
    it does not grow with probe *count* beyond what each distance-limited link allows.
    """
    return sum(
        data_rate_at(d, k_mbps_au2=k_mbps_au2, r_max_mbps=r_max_mbps)
        for d in distances_au
    )
