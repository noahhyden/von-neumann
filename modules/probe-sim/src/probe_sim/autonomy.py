"""Compute headroom vs. heliocentric distance: how far the probe can think, not just build, as solar power falls as 1/d^2."""

from __future__ import annotations

from power_budget.budget import PowerBudget, compute_capacity_flops
from power_budget.physics import brain_equivalents
from pydantic import BaseModel

from probe_sim.environment import SOLAR_CONSTANT_1AU_W_M2, SolarArray


class ComputeHeadroom(BaseModel):
    """The compute an array can power at a heliocentric distance, given an allocation."""

    distance_au: float
    delivered_power_w: float  # total solar-electric power at this distance
    compute_power_w: float  # the share allocated to computation
    compute_flops: float  # throughput that share buys at the given efficiency
    brain_equivalents: float  # against the [ESTIMATE] brain-FLOPS scale (power_budget)


def compute_headroom_at(
    array: SolarArray,
    distance_au: float,
    *,
    compute_fraction: float,
    efficiency_flops_per_w: float,
    solar_constant: float = SOLAR_CONSTANT_1AU_W_M2,
) -> ComputeHeadroom:
    """Compute headroom at one heliocentric distance."""
    delivered = array.power_w(distance_au, solar_constant)
    budget = PowerBudget(total_w=delivered, fraction_compute=compute_fraction)
    flops = compute_capacity_flops(budget.compute_w, efficiency_flops_per_w)
    return ComputeHeadroom(
        distance_au=distance_au,
        delivered_power_w=delivered,
        compute_power_w=budget.compute_w,
        compute_flops=flops,
        brain_equivalents=brain_equivalents(flops),
    )


def max_distance_for_compute(
    array: SolarArray,
    required_flops: float,
    *,
    compute_fraction: float,
    efficiency_flops_per_w: float,
    solar_constant: float = SOLAR_CONSTANT_1AU_W_M2,
) -> float:
    """Farthest heliocentric distance (AU) at which the probe still affords ``required_flops``."""
    if required_flops <= 0:
        raise ValueError("required_flops must be positive")
    if not 0.0 < compute_fraction <= 1.0:
        raise ValueError("compute_fraction must be in (0, 1]")
    if efficiency_flops_per_w <= 0:
        raise ValueError("efficiency_flops_per_w must be positive")
    required_total_w = (required_flops / efficiency_flops_per_w) / compute_fraction
    return array.max_distance_au(required_total_w, solar_constant)
