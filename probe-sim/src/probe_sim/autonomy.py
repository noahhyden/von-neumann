"""Compute headroom vs. distance - how far the probe can think, not just build.

An autonomous probe light-minutes from Earth has to run its own control and
perception, and that compute is powered by the same solar array whose output falls
as 1/d^2. So the compute the probe can afford - its autonomy budget - shrinks with
heliocentric distance exactly as delivered power does.

This couples two sibling modules through their public APIs (CLAUDE.md §4):
`probe_sim.environment` (delivered solar power vs distance) and `power_budget`
(splitting a budget and converting compute-watts to throughput). Pure, deterministic,
zero pimas imports (§7).
"""

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
    """Compute headroom at one heliocentric distance.

    ``compute_fraction`` is the share of delivered power given to computation (the rest
    is manufacturing/housekeeping/margin); ``efficiency_flops_per_w`` is the compute
    hardware efficiency (a sourced scenario input - see power-budget/REFERENCES.md).
    ``solar_constant`` is exposed so UQ can push a sampled S0 through the fold.
    """
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
    """Farthest heliocentric distance (AU) at which the probe still affords ``required_flops``.

    The compute share must supply ``required_flops / efficiency`` watts, i.e. the total
    delivered power must reach ``(required_flops / efficiency) / compute_fraction``; the
    inverse-square law then fixes the distance (reusing ``SolarArray.max_distance_au``).
    """
    if required_flops <= 0:
        raise ValueError("required_flops must be positive")
    if not 0.0 < compute_fraction <= 1.0:
        raise ValueError("compute_fraction must be in (0, 1]")
    if efficiency_flops_per_w <= 0:
        raise ValueError("efficiency_flops_per_w must be positive")
    required_total_w = (required_flops / efficiency_flops_per_w) / compute_fraction
    return array.max_distance_au(required_total_w, solar_constant)
