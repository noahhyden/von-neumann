"""The deterministic swarm fold — slice 1: a settlement front through a star field.

A homeworld launches interstellar probes; each travels to a target star (chosen by
policy), settles it on arrival, and launches ``offspring`` new probes. The reachable
field fills from the origin outward — the "exploration timescale" question of Nicholson
& Forgan (2013). Three policies (their three scenarios): ``powered`` (constant cruise
speed, nearest unsettled), ``slingshot_nearest`` (accumulate a gravitational-assist
boost at each star, nearest target), and ``slingshot_maxboost`` (target the star giving
the biggest boost). Slingshots extract energy from the stars' galactic motion, so
boosted probes far outrun the powered cruise — the paper's headline. Modelling
simplifications (scalar speeds, boost-optimal geometry, star velocities from an
[ESTIMATE] rotation figure) are documented in REFERENCES.md; the light-speed-limited
coordination extension is still future work (FRONTIER issue).

Fixed-step and fully seeded (CLAUDE.md §7): the star field, arrivals, and target choices
are all deterministic given (params, seed), so `speculate` and replay are exact and a
future TypeScript SoA port can match bit-for-bit. Zero pimas imports.
"""

from __future__ import annotations

from swarm.models import C_PC_PER_YEAR, KM_S_TO_PC_YR, Probe, SwarmParams, SwarmResult, SwarmState, SwarmStep
from swarm.rng import next_float, seed_state


def _generate_galaxy(
    params: SwarmParams, rng: int
) -> tuple[list[float], list[float], list[float], list[float], int]:
    """Seeded uniform star field + per-star speeds in a cube of side ``box_side_pc``.

    A real galaxy is a disk with a radial density gradient; a uniform cube is the
    minimal field that exercises the front dynamics. Star SPEEDS (magnitudes only, in
    pc/yr) are drawn in a SECOND pass after all positions, so adding the slingshot
    feature does not perturb the position RNG stream — the ``powered`` policy stays
    bit-identical to before. Speeds ~ galactic rotation ± dispersion [ESTIMATE]; the
    paper defers the actual shear/dispersion setup to Forgan+2012 (see REFERENCES.md).
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
    # Second pass: star speed magnitudes (does not touch the position stream above).
    base = params.star_speed_km_s * KM_S_TO_PC_YR
    disp = params.star_speed_dispersion_km_s * KM_S_TO_PC_YR
    star_speed: list[float] = []
    for _ in range(params.n_stars):
        u, rng = next_float(rng)
        star_speed.append(max(0.0, base + disp * (2.0 * u - 1.0)))
    return xs, ys, zs, star_speed, rng


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


def _nearest_k_unsettled(s: SwarmState, frm: int, exclude: set[int], k: int) -> list[int]:
    """The ``k`` nearest unsettled stars to ``frm`` (deterministic order by (distance, index))."""
    fx, fy, fz = s.xs[frm], s.ys[frm], s.zs[frm]
    cands: list[tuple[float, int]] = []
    for i in range(len(s.xs)):
        if s.settled_year[i] >= 0.0 or i in exclude:
            continue
        dx = s.xs[i] - fx
        dy = s.ys[i] - fy
        dz = s.zs[i] - fz
        cands.append((dx * dx + dy * dy + dz * dz, i))
    cands.sort()
    return [i for _, i in cands[:k]]


def _select_target(s: SwarmState, frm: int, exclude: set[int], params: SwarmParams) -> int | None:
    """Pick the next star per policy.

    powered / slingshot_nearest → nearest unsettled star. slingshot_maxboost → among the
    nearest ``max_boost_candidates`` unsettled stars, the one whose slingshot gives the
    largest boost. In this scalar model the boost grows with the destination star's speed,
    so max-boost = highest star speed among the candidates (tie-break lowest index). We
    scan only the nearest K (not the whole field) so a max-boost probe doesn't fly across
    the galaxy for a marginally bigger kick — a documented [ESTIMATE] bound.
    """
    if params.policy == "slingshot_maxboost":
        cand = _nearest_k_unsettled(s, frm, exclude, params.max_boost_candidates)
        if not cand:
            return None
        best = cand[0]
        for i in cand[1:]:
            if s.star_speed_pc_yr[i] > s.star_speed_pc_yr[best]:
                best = i
        return best
    return _nearest_unsettled(s, frm, exclude)


def _boosted_speed(current_pc_yr: float, star_speed_pc_yr: float, params: SwarmParams) -> float:
    """Galactic-frame speed after a slingshot off a star of the given speed.

    Powered policy: no slingshot, always the cruise speed. Otherwise (N&F Eq. 3–4): the
    max single-encounter gain is Δv_max = u_esc² / (u_esc²/(2u_i) + u_i), with u_i the
    probe's speed relative to the star. We take the boost-optimal (head-on) geometry,
    u_i ≈ current + star speed, and add Δv_max to the galactic speed — a documented
    [ESTIMATE] (we track scalar speeds, not full velocity vectors / true geometry). Eq. 4
    self-limits: Δv_max peaks near u_i ≈ u_esc and falls off for fast probes, so speed
    doesn't run away; a ``speed_cap_c`` ceiling backstops it anyway.
    """
    if params.policy == "powered":
        return params.probe_speed_pc_per_year
    u_esc = params.escape_velocity_km_s * KM_S_TO_PC_YR
    u_i = current_pc_yr + star_speed_pc_yr
    dv_max = u_esc * u_esc / (u_esc * u_esc / (2.0 * u_i) + u_i)  # N&F Eq. 4
    return min(current_pc_yr + dv_max, params.speed_cap_c * C_PC_PER_YEAR)


def _launch_from(s: SwarmState, star: int, params: SwarmParams, incoming_speed: float) -> None:
    """Slingshot off ``star`` and launch up to ``offspring`` probes toward new targets.

    The arriving probe's speed (``incoming_speed``) is boosted by this star's slingshot;
    the offspring depart at that boosted speed (replicate-in-transit: children inherit the
    parent's velocity), and pick targets by policy.
    """
    departing = _boosted_speed(incoming_speed, s.star_speed_pc_yr[star], params)
    if departing > s.max_speed_pc_yr:
        s.max_speed_pc_yr = departing
    chosen: set[int] = set()
    for _ in range(params.offspring_per_settlement):
        target = _select_target(s, star, chosen, params)
        if target is None:
            break
        chosen.add(target)
        travel = _dist(s, star, target) / departing
        s.probes.append(
            Probe(
                id=s.next_probe_id,
                target=target,
                arrive_year=s.year + params.settle_time_years + travel,
                speed_pc_yr=departing,
            )
        )
        s.next_probe_id += 1
        s.total_launched += 1


def initial_state(params: SwarmParams, *, seed: int) -> SwarmState:
    """Seeded galaxy with the homeworld (star nearest the box centre) settled at year 0."""
    xs, ys, zs, star_speed, rng = _generate_galaxy(params, seed_state(seed))
    n = len(xs)
    L = params.box_side_pc
    cx = cy = cz = L / 2.0
    origin = min(
        range(n),
        key=lambda i: (xs[i] - cx) ** 2 + (ys[i] - cy) ** 2 + (zs[i] - cz) ** 2,
    )
    settled = [-1.0] * n
    settled[origin] = 0.0
    v_max = params.probe_speed_pc_per_year
    state = SwarmState(
        rng=rng, year=0.0, xs=xs, ys=ys, zs=zs, star_speed_pc_yr=star_speed, settled_year=settled,
        origin=origin, probes=[], next_probe_id=0, total_launched=0, max_speed_pc_yr=v_max,
    )
    # Seed probes leave the homeworld at powered cruise, taking the homeworld's slingshot.
    _launch_from(state, origin, params, v_max)
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
    # Keep non-arrived probes; launches and re-targets append into this same list.
    state.probes = [p for p in state.probes if p.id not in arrived_ids]

    for p in arrivals:
        if state.settled_year[p.target] < 0.0:
            # First to arrive: settle it and spread (slingshot off it, boosting offspring).
            state.settled_year[p.target] = state.year
            _launch_from(state, p.target, params, p.speed_pc_yr)
        else:
            # Raced and lost: re-target (by policy), keeping this probe's current speed.
            target = _select_target(state, p.target, set(), params)
            if target is not None:
                travel = _dist(state, p.target, target) / p.speed_pc_yr
                state.probes.append(
                    Probe(id=p.id, target=target, arrive_year=state.year + travel, speed_pc_yr=p.speed_pc_yr)
                )

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
        max_probe_speed_km_s=state.max_speed_pc_yr / KM_S_TO_PC_YR,
        policy=params.policy,
        steps=steps,
    )
