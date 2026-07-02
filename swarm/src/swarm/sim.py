"""The deterministic swarm fold — slice 1: a settlement front through a star field.

A homeworld launches interstellar probes; each cruises at a fraction of c to the
nearest unsettled star, settles it on arrival, and launches ``offspring`` new probes
from it. The reachable field fills from the origin outward — the "exploration
timescale" question of Nicholson & Forgan (2013), here with straight-line constant-speed
travel (their gravitational slingshots, moving stars, and the max-boost policies are
later slices, as is the light-speed-limited-coordination extension).

Fixed-step and fully seeded (CLAUDE.md §7): the star field, arrivals, and target choices
are all deterministic given (params, seed), so `speculate` and replay are exact and a
future TypeScript SoA port can match bit-for-bit. Zero pimas imports.
"""

from __future__ import annotations

from swarm.models import Probe, SwarmParams, SwarmResult, SwarmState, SwarmStep
from swarm.rng import next_float, seed_state


def _generate_galaxy(params: SwarmParams, rng: int) -> tuple[list[float], list[float], list[float], int]:
    """Seeded uniform star field in a cube of side ``box_side_pc`` (slice-1 simplification.

    A real galaxy is a disk with a radial density gradient; a uniform cube is the
    minimal field that exercises the front dynamics. The disk model is a later slice.
    """
    L = params.box_side_pc
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for _ in range(params.n_stars):
        x, rng = next_float(rng)
        y, rng = next_float(rng)
        z, rng = next_float(rng)
        xs.append(x * L)
        ys.append(y * L)
        zs.append(z * L)
    return xs, ys, zs, rng


def _dist(s: SwarmState, a: int, b: int) -> float:
    dx = s.xs[a] - s.xs[b]
    dy = s.ys[a] - s.ys[b]
    dz = s.zs[a] - s.zs[b]
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _nearest_unsettled(s: SwarmState, frm: int, exclude: set[int]) -> int | None:
    """Index of the nearest unsettled star to ``frm`` not in ``exclude``.

    O(N) scan; deterministic tie-break by lowest index. (Spatial hashing to make this
    O(1)-ish is the scale slice; at slice-1 sizes the linear scan is fine.)
    """
    best: int | None = None
    best_d2 = float("inf")
    fx, fy, fz = s.xs[frm], s.ys[frm], s.zs[frm]
    for i in range(len(s.xs)):
        if s.settled_year[i] >= 0.0 or i in exclude:
            continue
        dx = s.xs[i] - fx
        dy = s.ys[i] - fy
        dz = s.zs[i] - fz
        d2 = dx * dx + dy * dy + dz * dz
        if d2 < best_d2:
            best_d2 = d2
            best = i
    return best


def _launch_from(s: SwarmState, star: int, params: SwarmParams) -> None:
    """Launch up to ``offspring`` probes from ``star`` toward distinct nearest unsettled stars."""
    speed = params.probe_speed_pc_per_year
    chosen: set[int] = set()
    for _ in range(params.offspring_per_settlement):
        target = _nearest_unsettled(s, star, chosen)
        if target is None:
            break
        chosen.add(target)
        travel = _dist(s, star, target) / speed
        s.probes.append(
            Probe(id=s.next_probe_id, target=target, arrive_year=s.year + params.settle_time_years + travel)
        )
        s.next_probe_id += 1
        s.total_launched += 1


def initial_state(params: SwarmParams, *, seed: int) -> SwarmState:
    """Seeded galaxy with the homeworld (star nearest the box centre) settled at year 0."""
    xs, ys, zs, rng = _generate_galaxy(params, seed_state(seed))
    n = len(xs)
    L = params.box_side_pc
    cx = cy = cz = L / 2.0
    origin = min(
        range(n),
        key=lambda i: (xs[i] - cx) ** 2 + (ys[i] - cy) ** 2 + (zs[i] - cz) ** 2,
    )
    settled = [-1.0] * n
    settled[origin] = 0.0
    state = SwarmState(
        rng=rng, year=0.0, xs=xs, ys=ys, zs=zs, settled_year=settled,
        origin=origin, probes=[], next_probe_id=0, total_launched=0,
    )
    _launch_from(state, origin, params)
    return state


def step(state: SwarmState, params: SwarmParams) -> SwarmState:
    """Advance one fixed timestep. Mutates and returns ``state`` (single-owner fold).

    Arrivals are processed in deterministic order (arrive_year, id). A probe arriving at
    an already-settled star re-targets to the nearest unsettled star and keeps going;
    the first to reach an unsettled star settles it and launches its offspring.
    """
    state.year += params.dt_years
    arrivals = sorted(
        (p for p in state.probes if p.arrive_year <= state.year),
        key=lambda p: (p.arrive_year, p.id),
    )
    if not arrivals:
        return state

    arrived_ids = {p.id for p in arrivals}
    speed = params.probe_speed_pc_per_year
    # Keep non-arrived probes; launches and re-targets append into this same list.
    state.probes = [p for p in state.probes if p.id not in arrived_ids]

    for p in arrivals:
        if state.settled_year[p.target] < 0.0:
            # First to arrive: settle it and spread.
            state.settled_year[p.target] = state.year
            _launch_from(state, p.target, params)
        else:
            # Raced and lost: re-target this probe to the nearest unsettled star.
            target = _nearest_unsettled(state, p.target, set())
            if target is not None:
                travel = _dist(state, p.target, target) / speed
                state.probes.append(Probe(id=p.id, target=target, arrive_year=state.year + travel))

    return state


def _front_radius(s: SwarmState) -> float:
    r = 0.0
    for i in range(len(s.xs)):
        if s.settled_year[i] >= 0.0:
            d = _dist(s, i, s.origin)
            if d > r:
                r = d
    return r


def _snapshot(s: SwarmState, n_stars: int) -> SwarmStep:
    n = s.n_settled()
    return SwarmStep(
        year=s.year, n_settled=n, fraction_settled=n / n_stars,
        in_flight=len(s.probes), front_radius_pc=_front_radius(s),
    )


def simulate_swarm(params: SwarmParams, *, seed: int = 0x9E3779B9) -> SwarmResult:
    """Run the settlement front to completion (or ``max_years``) and summarize."""
    state = initial_state(params, seed=seed)
    n_stars = len(state.xs)
    steps = [_snapshot(state, n_stars)]
    thresholds = {50: None, 90: None, 100: None}  # type: dict[int, float | None]

    def record_thresholds() -> None:
        frac = state.n_settled() / n_stars * 100.0
        for pct in (50, 90, 100):
            if thresholds[pct] is None and frac >= pct:
                thresholds[pct] = state.year

    record_thresholds()
    n_steps = int(round(params.max_years / params.dt_years))
    for _ in range(n_steps):
        if not state.probes:
            break  # front has stalled or the reachable field is exhausted
        step(state, params)
        steps.append(_snapshot(state, n_stars))
        record_thresholds()

    return SwarmResult(
        n_stars=n_stars,
        final_settled=state.n_settled(),
        total_probes_launched=state.total_launched,
        t50_years=thresholds[50],
        t90_years=thresholds[90],
        t100_years=thresholds[100],
        front_radius_pc=_front_radius(state),
        steps=steps,
    )
