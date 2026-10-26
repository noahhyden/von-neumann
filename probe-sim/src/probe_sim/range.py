"""Operational range: how far from the Sun the probe can still self-replicate."""

from __future__ import annotations

from closure_sim.models import Factory, ReplicationParams
from closure_sim.replication import reaches_target
from pydantic import BaseModel

from probe_sim.environment import SOLAR_CONSTANT_1AU_W_M2, SolarArray


def available_power_kw(
    array: SolarArray,
    distance_au: float,
    solar_constant: float = SOLAR_CONSTANT_1AU_W_M2,
) -> float:
    """Electrical power (kW) the array delivers at a heliocentric distance (AU)."""
    return array.power_w(distance_au, solar_constant) / 1000.0


def is_viable_at(
    array: SolarArray,
    factory: Factory,
    rep: ReplicationParams,
    distance_au: float,
    *,
    solar_constant: float = SOLAR_CONSTANT_1AU_W_M2,
) -> bool:
    """True if the probe reaches its target output at this heliocentric distance."""
    power_kw = available_power_kw(array, distance_au, solar_constant)
    if power_kw <= 0:
        return False
    params = rep.model_copy(update={"available_power_kw": power_kw})
    # reaches_target is the cheap, timeline-free equivalent of `simulate(...).time_to_target_days is not None` (issue #38 Phase 2): this is a bisection hot path, so skipping the per-day SimStep grid is ~36x faster.
    return reaches_target(factory, params)


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
    solar_constant: float = SOLAR_CONSTANT_1AU_W_M2,
) -> RangeResult:
    """Max heliocentric distance (AU) at which the probe still reaches its target."""
    if not is_viable_at(array, factory, rep, lo_au, solar_constant=solar_constant):
        return RangeResult(
            operational_range_au=None, saturated=False, lo_au=lo_au, hi_au=hi_au
        )
    if is_viable_at(array, factory, rep, hi_au, solar_constant=solar_constant):
        return RangeResult(
            operational_range_au=hi_au, saturated=True, lo_au=lo_au, hi_au=hi_au
        )

    lo, hi = lo_au, hi_au
    while hi - lo > tol_au:
        mid = 0.5 * (lo + hi)
        if is_viable_at(array, factory, rep, mid, solar_constant=solar_constant):
            lo = mid
        else:
            hi = mid
    return RangeResult(
        operational_range_au=lo, saturated=False, lo_au=lo_au, hi_au=hi_au
    )
