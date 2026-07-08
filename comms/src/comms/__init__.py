"""comms - deep-space downlink data rate and the data-return wall.

Models how fast a probe can send its findings home versus how far away it is. Two
regimes on a single distance axis: power-limited (`R proportional 1/d^2`, from Shannon
meeting Friis and confirmed by JPL's DSOC demo) and rate-limited (clamped at a modem
ceiling near Earth). The payoff is a new wall: probes generate bits faster than a
1/d^2 link returns them, so a fleet's aggregate knowledge saturates at the sum of its
link rates, not at probe count.

Distance is Earth-spacecraft range (not heliocentric). Deterministic, plain data, no
RNG (CLAUDE.md §7). Every number traces to a source; see REFERENCES.md.
"""

from comms.link import (
    BITS_PER_MBIT,
    K_OPTICAL_MBPS_AU2,
    R_MAX_DSOC_MBPS,
    BacklogResult,
    aggregate_return_rate_mbps,
    calibrate_k,
    crossover_distance_au,
    data_rate_at,
    return_backlog,
)

__all__ = [
    "BITS_PER_MBIT",
    "K_OPTICAL_MBPS_AU2",
    "R_MAX_DSOC_MBPS",
    "BacklogResult",
    "aggregate_return_rate_mbps",
    "calibrate_k",
    "crossover_distance_au",
    "data_rate_at",
    "return_backlog",
]
