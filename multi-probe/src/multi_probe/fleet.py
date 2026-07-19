"""The deterministic multi-probe fold: a small fleet that copies and disperses.

`step(state, params, dt)` is a pure function - active probes build local structure at a
rate their local sunlight allows (reusing probe-sim's inverse-square power), and when
one has built a copy's worth of structure *and* the fleet still has imported vitamins,
it spawns a child that travels outward and later becomes active. `simulate_fleet` folds
`step` over time from a seed.

Two ceilings emerge, both physical, neither hard-coded:
  * the **electronics wall**, re-instantiated at fleet scale - children need imported,
    non-replicable vitamins, so a finite vitamin pool caps the fleet (closure-sim's
    lesson, now spatial); and
  * a **spatial power wall** - children disperse outward, sunlight falls as 1/d², so
    far-flung probes build too slowly to ever copy.

Randomness (optional transit-time jitter) is a seeded generator threaded through the
state (CLAUDE.md §7): fix the seed → bit-exact replay → exact `speculate`. With jitter
= 0 the run is fully deterministic and independent of the seed. Zero pimas imports.
"""

from __future__ import annotations

from closure_sim.closure import compute_closure
from closure_sim.models import Factory
from probe_sim.environment import SolarArray

from multi_probe.models import (
    FleetParams,
    FleetResult,
    FleetState,
    FleetStep,
    Probe,
    ProbeStatus,
    RegimeCount,
)
from multi_probe.rng import next_float, seed_state


def params_from_factory(factory: Factory, **overrides: float | int) -> FleetParams:
    """Derive the sourced fields (seed mass, closure, local build energy) from a real BOM.

    ``e_local`` is the mass-weighted energy to build a kilogram of *local* structure,
    exactly closure-sim's ``e_local`` (local build energy ÷ local mass). Array size,
    power split, and fleet knobs take documented defaults; override any by keyword.
    """
    if factory.replication is None:
        raise ValueError("factory needs replication params (for seed_mass_kg)")
    report = compute_closure(factory)
    if report.local_mass_kg <= 0:
        raise ValueError("factory has no locally-producible mass")
    e_local = report.local_build_energy_kwh / report.local_mass_kg
    base: dict[str, float | int] = {
        "seed_mass_kg": factory.replication.seed_mass_kg,
        "closure_ratio": report.closure_ratio,
        "e_local_kwh_per_kg": e_local,
        "local_build_rate_kg_per_day": factory.replication.local_build_rate_kg_per_day,
        # array sized to deliver ~4 MW at 1 AU with 30% cells (same basis as mission):
        # 4e6 / (1360.8 * 0.30) ≈ 9798 m^2. [ESTIMATE] efficiency; see REFERENCES.md.
        "array_area_m2": 9798.0,
        "array_efficiency": 0.30,
        "manufacturing_fraction": 0.70,
    }
    base.update(overrides)
    return FleetParams(**base)


def build_rate_kg_per_day(params: FleetParams, distance_au: float) -> float:
    """Local build rate at a distance = min(machinery throughput, energy cap).

    Exactly closure-sim's ``min(alpha*F, energy_cap)`` for a *fixed-size* probe: the
    machinery can build at most ``local_build_rate_kg_per_day`` (alpha*F for F ≈ seed
    mass, which does not grow - a probe makes copies, it doesn't expand itself), and
    the solar power sets a second ceiling. Near the Sun the machinery binds (a probe
    can't use all its power); far out, 1/d² power falls below the machinery rate and
    the energy cap binds - the spatial power wall.
    """
    array = SolarArray(area_m2=params.array_area_m2, efficiency=params.array_efficiency)
    manufacturing_w = array.power_w(distance_au) * params.manufacturing_fraction
    manufacturing_kwh_per_day = manufacturing_w / 1000.0 * 24.0
    energy_cap = manufacturing_kwh_per_day / params.e_local_kwh_per_kg
    return min(params.local_build_rate_kg_per_day, energy_cap)


def time_to_build_one_copy_days(params: FleetParams, distance_au: float) -> float:
    """Days for one probe to build one copy's worth of *local* structure at a distance.

    ``= local_per_child / build_rate``, where ``local_per_child = closure_ratio *
    seed_mass_kg`` (the locally-produced mass in one copy) and ``build_rate`` is the
    regime-limited rate above. This is the fleet's fundamental replication cadence - the
    time between a probe's copies - and, evaluated at 1 AU, it is the swarm's per-star
    *manufacturing dwell* (``settle_time_years``): the time a freshly settled probe spends
    building offspring before they depart. It is the same closure-sim physics, re-used at a
    third scale; it introduces no new number. Returns ``inf`` if the local build rate is
    zero (the probe can never copy - the spatial power wall at that distance).
    """
    local_per_child = params.closure_ratio * params.seed_mass_kg
    rate = build_rate_kg_per_day(params, distance_au)
    return local_per_child / rate if rate > 0.0 else float("inf")


def initial_state(params: FleetParams, *, seed: int) -> FleetState:
    """The landed seed probes at t=0, active at the start distance, with the vitamin pool."""
    probes = [
        Probe(
            id=i,
            distance_au=params.start_distance_au,
            status=ProbeStatus.ACTIVE,
            arrival_day=0.0,
        )
        for i in range(params.n_seed_probes)
    ]
    return FleetState(
        rng=seed_state(seed),
        day=0.0,
        probes=probes,
        vitamin_pool_kg=params.vitamin_pool_kg,
        next_id=params.n_seed_probes,
    )


def _verify_step_invariants(
    before: FleetState, after: FleetState, *, params: FleetParams, dt: float
) -> None:
    """Assert the documented step invariants on (before -> after). See REFERENCES.md.

    Called by `step` under `if __debug__:` and directly by negative tests.
    Raises AssertionError with an [inv:...] tag on the first violation.
    """
    # Structural / bound checks first: conservation below depends on them being intact.
    assert abs(after.day - (before.day + dt)) <= 1e-9 * max(1.0, abs(before.day + dt)), (
        f"[inv:mp-day] day_new={after.day} != day_old+dt={before.day + dt}"
    )
    assert len(after.probes) <= params.max_probes, (
        f"[inv:mp-cap] len(probes)={len(after.probes)} > max_probes={params.max_probes}"
    )
    assert after.vitamin_pool_kg >= 0.0, "[inv:mp-vitamin-nonneg] pool_new < 0"
    before_by_id = {p.id: p for p in before.probes}
    after_by_id = {p.id: p for p in after.probes}
    for pid, p_before in before_by_id.items():
        assert pid in after_by_id, f"[inv:mp-status-transitions] probe id={pid} vanished"
        p_after = after_by_id[pid]
        if p_before.status == ProbeStatus.ACTIVE:
            assert p_after.status == ProbeStatus.ACTIVE, (
                f"[inv:mp-status-transitions] probe id={pid} ACTIVE->{p_after.status}"
            )
        assert p_after.children >= p_before.children, (
            f"[inv:mp-children-monotone] probe id={pid} children {p_before.children}->{p_after.children}"
        )
    n_new = len(after.probes) - len(before.probes)
    assert after.next_id >= before.next_id, (
        f"[inv:mp-next-id-monotone] next_id_new={after.next_id} < next_id_old={before.next_id}"
    )
    assert after.next_id - before.next_id == n_new, (
        f"[inv:mp-next-id-monotone] delta_next_id={after.next_id - before.next_id} != N_newborn={n_new}"
    )
    v_per_child = (1.0 - params.closure_ratio) * params.seed_mass_kg
    expected_pool = before.vitamin_pool_kg - n_new * v_per_child
    tol = max(1e-9 * before.vitamin_pool_kg, 1e-9)
    assert abs(after.vitamin_pool_kg - expected_pool) <= tol, (
        f"[inv:mp-vitamin-conservation] pool_new={after.vitamin_pool_kg} "
        f"expected={expected_pool} (n_new={n_new} v_per_child={v_per_child})"
    )


def step(state: FleetState, params: FleetParams, dt: float) -> FleetState:
    """Advance the whole fleet by ``dt`` days. Pure: returns a new state.

    Iterates probes in id order so RNG draws (and therefore the whole run) are
    deterministic given the seed.
    """
    local_per_child = params.closure_ratio * params.seed_mass_kg
    vitamins_per_child = (1.0 - params.closure_ratio) * params.seed_mass_kg
    new_day = state.day + dt

    rng = state.rng
    pool = state.vitamin_pool_kg
    next_id = state.next_id
    count = len(state.probes)  # traveling + active, for the cap

    updated: list[Probe] = []
    newborns: list[Probe] = []

    for p in state.probes:
        if p.status != ProbeStatus.ACTIVE:
            updated.append(p)  # traveling probes just wait (arrival handled below)
            continue

        built = p.built_kg + build_rate_kg_per_day(params, p.distance_au) * dt
        children = p.children

        while built >= local_per_child and count < params.max_probes and pool >= vitamins_per_child:
            built -= local_per_child
            pool -= vitamins_per_child
            count += 1
            children += 1
            child_distance = min(p.distance_au * params.dispersal_factor, params.max_distance_au)
            transit = params.transit_days
            if params.transit_jitter_frac > 0.0:
                u, rng = next_float(rng)
                transit = params.transit_days * (1.0 + params.transit_jitter_frac * (2.0 * u - 1.0))
            newborns.append(
                Probe(
                    id=next_id,
                    distance_au=child_distance,
                    status=ProbeStatus.TRAVELING,
                    arrival_day=new_day + transit,
                    built_kg=0.0,
                    children=0,
                )
            )
            next_id += 1

        updated.append(Probe(p.id, p.distance_au, p.status, p.arrival_day, built, children))

    # Arrivals: traveling probes whose ETA has passed become active.
    all_probes = updated + newborns
    arrived: list[Probe] = []
    for p in all_probes:
        if p.status == ProbeStatus.TRAVELING and p.arrival_day <= new_day:
            arrived.append(Probe(p.id, p.distance_au, ProbeStatus.ACTIVE, p.arrival_day, p.built_kg, p.children))
        else:
            arrived.append(p)

    new_state = FleetState(rng=rng, day=new_day, probes=arrived, vitamin_pool_kg=pool, next_id=next_id)
    if __debug__:
        _verify_step_invariants(state, new_state, params=params, dt=dt)
    return new_state


def _snapshot(state: FleetState) -> FleetStep:
    dists = [p.distance_au for p in state.probes]
    active = state.active()
    return FleetStep(
        day=state.day,
        population=len(state.probes),
        active=len(active),
        total_built_kg=sum(p.built_kg for p in state.probes),
        vitamin_pool_kg=state.vitamin_pool_kg,
        mean_distance_au=sum(dists) / len(dists) if dists else 0.0,
        max_distance_au=max(dists) if dists else 0.0,
    )


def simulate_fleet(
    params: FleetParams,
    *,
    seed: int = 0x9E3779B9,
    duration_days: float = 3650.0,
    dt_days: float = 1.0,
) -> FleetResult:
    """Fold ``step`` over time from a seed and summarize the run."""
    if dt_days <= 0:
        raise ValueError("dt_days must be positive")
    state = initial_state(params, seed=seed)
    initial_pop = len(state.probes)
    steps = [_snapshot(state)]
    doubling_time: float | None = None

    n = int(round(duration_days / dt_days))
    for _ in range(n):
        state = step(state, params, dt_days)
        snap = _snapshot(state)
        steps.append(snap)
        if doubling_time is None and snap.population >= 2 * initial_pop:
            doubling_time = snap.day

    vitamins_per_child = (1.0 - params.closure_ratio) * params.seed_mass_kg
    total_children = sum(p.children for p in state.probes)
    dists = [p.distance_au for p in state.probes]

    # Which ceiling is binding at the end (independent booleans).
    vitamin_limited = state.vitamin_pool_kg < vitamins_per_child
    cap_limited = len(state.probes) >= params.max_probes
    local_per_child = params.closure_ratio * params.seed_mass_kg
    power_limited = any(
        build_rate_kg_per_day(params, p.distance_au) * duration_days < local_per_child
        for p in state.active()
    )

    return FleetResult(
        final_population=len(state.probes),
        final_active=len(state.active()),
        total_children=total_children,
        vitamins_consumed_kg=params.vitamin_pool_kg - state.vitamin_pool_kg,
        vitamins_remaining_kg=state.vitamin_pool_kg,
        doubling_time_days=doubling_time,
        binding=RegimeCount(
            vitamin_limited=vitamin_limited,
            power_limited=power_limited,
            cap_limited=cap_limited,
        ),
        mean_distance_au=sum(dists) / len(dists) if dists else 0.0,
        max_distance_au=max(dists) if dists else 0.0,
        steps=steps,
    )
