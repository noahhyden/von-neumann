"""The electronics-wall analysis — the headline insight.

Re-run a scenario with the electronics/compute subsystems toggled from vitamin to
locally-producible, and report how closure, the resupply ceiling, doubling time,
and time-to-target change. This isolates the single biggest closure bottleneck:
the semiconductor supply chain.
"""

from __future__ import annotations

from pydantic import BaseModel

from .closure import compute_closure
from .models import ELECTRONICS_CATEGORIES, Factory, ReplicationParams
from .replication import SimResult, simulate


class WallSide(BaseModel):
    closure_ratio: float
    resupply_ceiling_kg_per_day: float
    energy_cap_kg_per_day: float
    empirical_doubling_time_days: float | None
    time_to_target_days: float | None
    final_output_kg_per_day: float


class ElectronicsWallReport(BaseModel):
    factory_name: str
    electronics_categories: list[str]
    electronics_mass_kg: float
    electronics_mass_share: float
    before: WallSide  # electronics are vitamins (as authored)
    after: WallSide  # electronics produced locally
    time_to_target_delta_days: float | None  # before - after (positive = faster)
    sim_result_before: SimResult
    sim_result_after: SimResult


def _side(result: SimResult) -> WallSide:
    return WallSide(
        closure_ratio=result.closure_ratio,
        resupply_ceiling_kg_per_day=result.resupply_ceiling_kg_per_day,
        energy_cap_kg_per_day=result.energy_cap_kg_per_day,
        empirical_doubling_time_days=result.empirical_doubling_time_days,
        time_to_target_days=result.time_to_target_days,
        final_output_kg_per_day=result.final_output_kg_per_day,
    )


def electronics_wall(
    factory: Factory,
    params: ReplicationParams | None = None,
    electronics_categories: frozenset[str] = ELECTRONICS_CATEGORIES,
) -> ElectronicsWallReport:
    """Compare replication with electronics as vitamins vs produced locally."""
    rep = params or factory.replication
    if rep is None:
        raise ValueError(
            f"factory {factory.name!r} has no replication params; pass `params=`"
        )

    before_result = simulate(factory, rep)

    toggled = factory.model_copy(deep=True)
    elec_mass = 0.0
    for s in toggled.subsystems:
        if s.category in electronics_categories:
            s.producible_locally = True
            elec_mass += s.mass_kg
    after_result = simulate(toggled, rep)

    before, after = _side(before_result), _side(after_result)
    delta = None
    if before.time_to_target_days is not None and after.time_to_target_days is not None:
        delta = before.time_to_target_days - after.time_to_target_days

    report = compute_closure(factory)
    return ElectronicsWallReport(
        factory_name=factory.name,
        electronics_categories=sorted(electronics_categories),
        electronics_mass_kg=elec_mass,
        electronics_mass_share=elec_mass / report.total_mass_kg
        if report.total_mass_kg
        else 0.0,
        before=before,
        after=after,
        time_to_target_delta_days=delta,
        sim_result_before=before_result,
        sim_result_after=after_result,
    )
