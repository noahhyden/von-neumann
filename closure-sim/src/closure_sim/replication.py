"""Discrete-time self-replication simulator (whole-copy replication model).

Model
-----
State is installed factory mass ``F`` (kg), all of it productive. Productivity
``alpha = K0 / seed_mass`` (kg local output per day per kg of factory) is fixed by
the seed, so local production ``alpha * F`` scales with the factory — the source of
exponential growth.

Building new factory mass needs inputs in ratio ``C : (1 - C)`` (local : vitamin),
where ``C`` is mass closure. That gives three ceilings on the growth rate dF/dt:

    material path : (alpha * F) / C          -> scales with F  -> exponential
    energy path   : energy_cap / C           -> constant       -> linear
    resupply path : R / (1 - C)              -> constant       -> linear

with ``energy_cap = available_power_per_day / e_local`` (e_local = energy per kg of
*locally produced* material) and ``R`` the vitamin resupply rate. The binding
(smallest) path sets dF/dt each step, which is exactly the regime.

Key limiting behaviours, all emergent (not hardcoded):
  * C -> 1: resupply path -> infinity, growth stays exponential forever.
  * C -> 0: nothing is made locally; growth is pure linear resupply at rate R.
  * R = 0 with C < 1: no vitamins, growth pins to zero — the factory is stuck.
  * Making chips locally raises e_local sharply, which can move the bottleneck to
    energy rather than removing it.
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel

from .closure import compute_closure
from .models import Factory, ReplicationParams


class Regime(str, Enum):
    MATERIAL = "material-limited"
    ENERGY = "energy-limited"
    RESUPPLY = "resupply-limited"


class SimStep(BaseModel):
    day: float
    factory_mass_kg: float
    installed_capacity_kg_per_day: float  # alpha * F (what is installed)
    output_kg_per_day: float  # min(alpha * F, energy_cap) (what it can run)
    growth_rate_kg_per_day: float  # dF/dt at this step
    regime: Regime


class RegimeSpan(BaseModel):
    regime: Regime
    start_day: float
    end_day: float


class SimResult(BaseModel):
    factory_name: str
    closure_ratio: float
    productivity_per_day: float  # alpha
    energy_cap_kg_per_day: float  # local production cap from available power
    resupply_ceiling_kg_per_day: float  # R / (1 - C), the linear growth ceiling
    analytic_doubling_time_days: float | None  # ln2 * C / alpha (material regime)
    empirical_doubling_time_days: float | None  # first doubling of factory mass
    time_to_target_days: float | None  # first day output >= target (None = never)
    final_factory_mass_kg: float
    final_output_kg_per_day: float
    target_output_kg_per_day: float
    regime_timeline: list[RegimeSpan]
    steps: list[SimStep]


def _binding_rate(
    F: float,
    alpha: float,
    closure: float,
    energy_cap: float,
    resupply_rate: float,
) -> tuple[float, Regime]:
    """Return (dF/dt, binding regime) for the current factory mass."""
    local_production = min(alpha * F, energy_cap)

    # Vitamin (resupply) path.
    if closure >= 1.0:
        resupply_path = math.inf  # full closure: vitamins never bind
    elif resupply_rate <= 0.0:
        resupply_path = 0.0  # no vitamins arriving -> cannot grow (unless C == 1)
    else:
        resupply_path = resupply_rate / (1.0 - closure)

    # Local-material path.
    if closure <= 0.0:
        local_path = math.inf  # no local content needed; resupply alone drives growth
    else:
        local_path = local_production / closure

    rate = min(local_path, resupply_path)

    if resupply_path < local_path:
        regime = Regime.RESUPPLY
    elif alpha * F <= energy_cap:
        regime = Regime.MATERIAL
    else:
        regime = Regime.ENERGY
    return rate, regime


def _compress_timeline(steps: list[SimStep]) -> list[RegimeSpan]:
    spans: list[RegimeSpan] = []
    for s in steps:
        if spans and spans[-1].regime == s.regime:
            spans[-1].end_day = s.day
        else:
            spans.append(RegimeSpan(regime=s.regime, start_day=s.day, end_day=s.day))
    return spans


def _interpolate_crossing(
    prev_day: float, prev_val: float, day: float, val: float, target: float
) -> float:
    """Linearly interpolate the day at which a rising series crosses ``target``."""
    if val == prev_val:
        return day
    frac = (target - prev_val) / (val - prev_val)
    return prev_day + frac * (day - prev_day)


def simulate(
    factory: Factory, params: ReplicationParams | None = None
) -> SimResult:
    """Run the replication sim. ``params`` overrides ``factory.replication``."""
    rep = params or factory.replication
    if rep is None:
        raise ValueError(
            f"factory {factory.name!r} has no replication params; pass `params=`"
        )

    report = compute_closure(factory)
    C = report.closure_ratio
    local_mass = factory.local_mass_kg

    alpha = rep.local_build_rate_kg_per_day / rep.seed_mass_kg

    # Energy per kg of *locally produced* material (vitamins arrive pre-made).
    if local_mass > 0:
        e_local = report.local_build_energy_kwh / local_mass
    else:
        e_local = math.inf
    energy_cap = (
        rep.available_power_kwh_per_day / e_local if e_local > 0 else math.inf
    )

    resupply_ceiling = (
        math.inf if C >= 1.0 else rep.resupply_rate_kg_per_day / (1.0 - C)
    )

    analytic_doubling = (
        math.log(2) * C / alpha if (C > 0 and alpha > 0) else None
    )

    F = rep.seed_mass_kg
    F0 = F
    target = rep.target_output_kg_per_day

    steps: list[SimStep] = []
    time_to_target: float | None = None
    empirical_doubling: float | None = None

    n_steps = int(math.ceil(rep.duration_days / rep.dt_days))
    prev_day = 0.0
    prev_output = min(alpha * F, energy_cap)
    prev_mass = F

    for i in range(n_steps + 1):
        day = i * rep.dt_days
        rate, regime = _binding_rate(F, alpha, C, energy_cap, resupply_rate=rep.resupply_rate_kg_per_day)
        installed = alpha * F
        output = min(installed, energy_cap)

        steps.append(
            SimStep(
                day=day,
                factory_mass_kg=F,
                installed_capacity_kg_per_day=installed,
                output_kg_per_day=output,
                growth_rate_kg_per_day=rate,
                regime=regime,
            )
        )

        if time_to_target is None and output >= target:
            time_to_target = (
                0.0
                if i == 0
                else _interpolate_crossing(prev_day, prev_output, day, output, target)
            )
        if empirical_doubling is None and F >= 2 * F0:
            empirical_doubling = (
                0.0
                if i == 0
                else _interpolate_crossing(prev_day, prev_mass, day, F, 2 * F0)
            )

        prev_day, prev_output, prev_mass = day, output, F

        # Euler step (forward). dt small enough for the regimes we report.
        F = F + rate * rep.dt_days

    return SimResult(
        factory_name=factory.name,
        closure_ratio=C,
        productivity_per_day=alpha,
        energy_cap_kg_per_day=energy_cap,
        resupply_ceiling_kg_per_day=resupply_ceiling,
        analytic_doubling_time_days=analytic_doubling,
        empirical_doubling_time_days=empirical_doubling,
        time_to_target_days=time_to_target,
        final_factory_mass_kg=F,
        final_output_kg_per_day=min(alpha * F, energy_cap),
        target_output_kg_per_day=target,
        regime_timeline=_compress_timeline(steps),
        steps=steps,
    )
