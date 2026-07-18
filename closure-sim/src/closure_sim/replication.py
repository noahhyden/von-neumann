"""Self-replication simulator (whole-copy replication model).

The factory mass obeys a continuous ODE, dF/dt = binding-rate(F), integrated by
the shared adaptive solver `vn_core.ode` (issue #38) and sampled on a daily grid
for reporting. It was previously stepped by hand with forward Euler at a guessed
dt; that biased the exponential-growth regime and is what this module no longer
does.

Model
-----
State is installed factory mass ``F`` (kg), all of it productive. Productivity
``alpha = K0 / seed_mass`` (kg local output per day per kg of factory) is fixed by
the seed, so local production ``alpha * F`` scales with the factory - the source of
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
  * R = 0 with C < 1: no vitamins, growth pins to zero - the factory is stuck.
  * Making chips locally raises e_local sharply, which can move the bottleneck to
    energy rather than removing it.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel
from vn_core.ode import solve

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


@dataclass(frozen=True)
class _Setup:
    """The derived quantities a replication run needs, shared by every entry point.

    Extracted so ``simulate`` (full telemetry) and ``reaches_target`` (cheap
    boolean) compute the closure, productivity, and ceilings exactly once and the
    same way - no drift between the two paths.
    """

    closure: float
    alpha: float
    energy_cap: float
    resupply_ceiling: float
    analytic_doubling: float | None
    seed_mass_kg: float
    target: float
    resupply_rate: float


def _prepare(factory: Factory, rep: ReplicationParams) -> _Setup:
    """Compute the closure/productivity/ceilings for a factory + params."""
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
    analytic_doubling = math.log(2) * C / alpha if (C > 0 and alpha > 0) else None

    return _Setup(
        closure=C,
        alpha=alpha,
        energy_cap=energy_cap,
        resupply_ceiling=resupply_ceiling,
        analytic_doubling=analytic_doubling,
        seed_mass_kg=rep.seed_mass_kg,
        target=rep.target_output_kg_per_day,
        resupply_rate=rep.resupply_rate_kg_per_day,
    )


def _make_rhs(s: _Setup) -> Callable[[float, list[float]], list[float]]:
    """Build the ODE right-hand side dF/dt = binding-rate(F) for a prepared setup."""

    def _dF_dt(_t: float, y: list[float]) -> list[float]:
        rate, _ = _binding_rate(
            y[0], s.alpha, s.closure, s.energy_cap, resupply_rate=s.resupply_rate
        )
        return [rate]

    return _dF_dt


def simulate(
    factory: Factory, params: ReplicationParams | None = None
) -> SimResult:
    """Run the replication sim. ``params`` overrides ``factory.replication``."""
    rep = params or factory.replication
    if rep is None:
        raise ValueError(
            f"factory {factory.name!r} has no replication params; pass `params=`"
        )

    s = _prepare(factory, rep)
    C = s.closure
    alpha = s.alpha
    energy_cap = s.energy_cap
    resupply_ceiling = s.resupply_ceiling
    analytic_doubling = s.analytic_doubling
    F0 = s.seed_mass_kg
    F = F0
    target = s.target

    steps: list[SimStep] = []
    time_to_target: float | None = None
    empirical_doubling: float | None = None

    n_steps = int(math.ceil(rep.duration_days / rep.dt_days))
    days = [i * rep.dt_days for i in range(n_steps + 1)]

    # Integrate dF/dt = binding-rate(F) with the shared adaptive solver instead of
    # a hand-rolled forward-Euler step (issue #38). Euler at a guessed dt biased
    # exponential growth low, so the *empirical* doubling time drifted from the
    # analytic one purely as a step-size artefact; RK45 to a tolerance removes
    # that. `dt_days` now sets only the reporting cadence (the sample grid the
    # timeline and crossings are read off), not the integration accuracy. The
    # rate has kinks where the binding regime switches; the adaptive stepper
    # simply shortens its step across them.
    #
    # This full-telemetry path samples every day for the SimStep timeline; callers
    # that only need "does it reach target?" should use reaches_target(), which
    # skips the grid and is ~36x cheaper (issue #38 Phase 2).
    if days[-1] > 0.0:
        traj = solve(_make_rhs(s), [F0], (0.0, days[-1]), t_eval=days, rtol=1e-8, atol=1e-9)
        if not traj.success:
            raise RuntimeError(f"replication integration failed: {traj.message}")
        masses = [row[0] for row in traj.y]
    else:
        masses = [F0]  # zero-length run: only the seed state exists

    prev_day = 0.0
    prev_output = min(alpha * F0, energy_cap)
    prev_mass = F0

    for i, day in enumerate(days):
        F = masses[i]
        rate, regime = _binding_rate(
            F, alpha, C, energy_cap, resupply_rate=rep.resupply_rate_kg_per_day
        )
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

    F = masses[-1]

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


def reaches_target(
    factory: Factory, params: ReplicationParams | None = None
) -> bool:
    """Does the factory's output ever reach its target? A cheap viability check.

    Equivalent to ``simulate(factory, params).time_to_target_days is not None`` but
    ~36x cheaper (issue #38 Phase 2): it skips the per-day SimStep timeline and
    lets the solver take its natural adaptive steps instead of forcing a step per
    reporting day.

    Correct by monotonicity: dF/dt = binding-rate(F) >= 0, so factory mass F is
    non-decreasing, so output = min(alpha*F, energy_cap) is non-decreasing. Output
    therefore reaches the target iff it has reached it by the final time - the
    whole trajectory reduces to one endpoint comparison, no timeline needed. Use
    this in bisection / Monte Carlo hot paths (e.g. probe-sim's operational
    range); use ``simulate`` when you actually need the timeline.
    """
    rep = params or factory.replication
    if rep is None:
        raise ValueError(
            f"factory {factory.name!r} has no replication params; pass `params=`"
        )

    s = _prepare(factory, rep)
    # Integrate to the same endpoint simulate() uses so the two agree exactly.
    n_steps = int(math.ceil(rep.duration_days / rep.dt_days))
    t_end = n_steps * rep.dt_days
    if t_end <= 0.0:
        f_final = s.seed_mass_kg
    else:
        traj = solve(_make_rhs(s), [s.seed_mass_kg], (0.0, t_end), rtol=1e-8, atol=1e-9)
        if not traj.success:
            raise RuntimeError(f"replication integration failed: {traj.message}")
        f_final = traj.y_final[0]

    output_final = min(s.alpha * f_final, s.energy_cap)
    return output_final >= s.target
