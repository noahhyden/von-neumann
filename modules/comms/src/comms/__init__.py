"""comms - deep-space downlink data rate and the data-return wall."""

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
