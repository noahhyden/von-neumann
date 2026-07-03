"""Operational range: how far from the Sun the probe can still self-replicate.

This ties the solar environment (`SolarArray`) to `closure-sim`'s replication model.
As the probe moves outward, delivered power falls as 1/d^2, which lowers the energy
ceiling on local production; past some heliocentric distance the probe can no longer
reach its target output and replication is no longer viable. That crossover distance
is the operational range.

Because delivered power decreases monotonically with distance, viability is
monotonic too - viable close in, not viable far out - so a single bisection finds
the crossover exactly.

closure-sim is consumed through its public API (`Factory`, `ReplicationParams`,
`simulate`) - no reaching into internals (CLAUDE.md §4). This module stays a pure,
deterministic fold with zero pimas imports (§7).
"""

from __future__ import annotations

from closure_sim.models import Factory, ReplicationParams
from closure_sim.replication import simulate
from pydantic import BaseModel

from probe_sim.environment import SolarArray


def available_power_kw(array: SolarArray, distance_au: float) -> float:
    """Electrical power (kW) the array delivers at a heliocentric distance (AU)."""
    return array.power_w(distance_au) / 1000.0


def is_viable_at(
    array: SolarArray,
    factory: Factory,
    rep: ReplicationParams,
    distance_au: float,
) -> bool:
    """True if the probe reaches its target output at this heliocentric distance.

    Runs closure-sim's replication with the array's delivered power substituted in
    for ``available_power_kw``; viability is "does output ever reach the target".
    """
    power_kw = available_power_kw(array, distance_au)
    if power_kw <= 0:
        return False
    params = rep.model_copy(update={"available_power_kw": power_kw})
    return simulate(factory, params).time_to_target_days is not None


class RangeResult(BaseModel):
    """Where a probe's replication stops being viable as it moves outward."""

    operational_range_au: float | None  # None => underpowered even at lo_au
    saturated: bool  # True => still viable at hi_au (true range >= hi_au)
    lo_au: float
    hi_au: float


def operational_range(
    array: SolarArray,
    factory: Factory,
    rep: ReplicationParams,
    *,
    lo_au: float = 0.3,
    hi_au: float = 40.0,
    tol_au: float = 1e-3,
) -> RangeResult:
    """Max heliocentric distance (AU) at which the probe still reaches its target.

    Bisects between ``lo_au`` and ``hi_au``. Returns ``operational_range_au=None`` if
    the probe is underpowered even at ``lo_au``, and ``saturated=True`` if it is still
    viable at ``hi_au`` (the true range lies beyond the search ceiling).
    """
    if not is_viable_at(array, factory, rep, lo_au):
        return RangeResult(
            operational_range_au=None, saturated=False, lo_au=lo_au, hi_au=hi_au
        )
    if is_viable_at(array, factory, rep, hi_au):
        return RangeResult(
            operational_range_au=hi_au, saturated=True, lo_au=lo_au, hi_au=hi_au
        )

    lo, hi = lo_au, hi_au
    while hi - lo > tol_au:
        mid = 0.5 * (lo + hi)
        if is_viable_at(array, factory, rep, mid):
            lo = mid
        else:
            hi = mid
    return RangeResult(
        operational_range_au=lo, saturated=False, lo_au=lo_au, hi_au=hi_au
    )
