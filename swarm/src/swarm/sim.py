"""The deterministic swarm fold - slice 1: a settlement front through a star field.

A homeworld launches interstellar probes; each travels to a target star (chosen by
policy), settles it on arrival, and launches ``offspring`` new probes. The reachable
field fills from the origin outward - the "exploration timescale" question of Nicholson
& Forgan (2013). Three policies (their three scenarios): ``powered`` (constant cruise
speed, nearest unsettled), ``slingshot_nearest`` (accumulate a gravitational-assist
boost at each star, nearest target), and ``slingshot_maxboost`` (target the star giving
the biggest boost). Slingshots extract energy from the stars' galactic motion, so
boosted probes far outrun the powered cruise - the paper's headline. Modelling
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
    feature does not perturb the position RNG stream - the ``powered`` policy stays
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


def _believes_settled(s: SwarmState, frm: int, i: int, params: SwarmParams) -> bool:
    """Does a decider AT star ``frm`` in year ``s.year`` know star ``i`` is settled?

    The light-speed-limited coordination gate (FRONTIER #1). A settled star is a beacon
    emitting "I'm settled" at ``settled_year[i]``; the news reaches ``frm`` only after the
    light-travel time ``dist/c``. So under ``coordination="lightspeed"`` a decider believes
    ``i`` settled iff the beacon has had time to arrive. Under ``"instant"`` (the paper's
    perfect-global-info assumption) this collapses to ``settled_year[i] >= 0`` - bit-identical
    to slices 1-3. This is a pure function of state already present (positions + settled_year
    + year + the sourced ``C_PC_PER_YEAR``); it adds no RNG and can't desync from truth.

    Observer is the decision star ``frm`` (decisions happen only at stars), so news a probe
    passes THROUGH mid-flight is ignored - a conservative simplification that undercounts
    knowledge (documented in REFERENCES.md); mobile-relay gossip is a deferred sibling.
    """
    if s.settled_year[i] < 0.0:
        return False
    if params.coordination == "instant":
        return True
    return s.settled_year[i] + _dist(s, frm, i) / C_PC_PER_YEAR <= s.year


def _nearest_unsettled(s: SwarmState, frm: int, exclude: set[int], params: SwarmParams) -> int | None:
    """Index of the nearest *believed*-unsettled star to ``frm`` not in ``exclude``.

    O(N) scan; deterministic tie-break by lowest index. "Believed" = the light-speed gate
    (`_believes_settled`); under ``coordination="instant"`` this is exactly the old nearest-
    unsettled. (Spatial hashing to make this O(1)-ish is the scale slice.)
    """
    best: int | None = None
    best_d2 = float("inf")
    fx, fy, fz = s.xs[frm], s.ys[frm], s.zs[frm]
    for i in range(len(s.xs)):
        if i in exclude or _believes_settled(s, frm, i, params):
            continue
        dx = s.xs[i] - fx
        dy = s.ys[i] - fy
        dz = s.zs[i] - fz
        d2 = dx * dx + dy * dy + dz * dz
        if d2 < best_d2:
            best_d2 = d2
            best = i
    return best


def _nearest_k_unsettled(s: SwarmState, frm: int, exclude: set[int], k: int, params: SwarmParams) -> list[int]:
    """The ``k`` nearest *believed*-unsettled stars to ``frm`` (deterministic order by (distance, index))."""
    fx, fy, fz = s.xs[frm], s.ys[frm], s.zs[frm]
    cands: list[tuple[float, int]] = []
    for i in range(len(s.xs)):
        if i in exclude or _believes_settled(s, frm, i, params):
            continue
        dx = s.xs[i] - fx
        dy = s.ys[i] - fy
        dz = s.zs[i] - fz
        cands.append((dx * dx + dy * dy + dz * dz, i))
    cands.sort()
    return [i for _, i in cands[:k]]


def _select_target(s: SwarmState, frm: int, exclude: set[int], params: SwarmParams) -> int | None:
    """Pick the next star per policy, reading the decider's *belief* of what's unsettled.

    powered / slingshot_nearest → nearest believed-unsettled star. slingshot_maxboost → among
    the nearest ``max_boost_candidates`` believed-unsettled stars, the one whose slingshot
    gives the largest boost. In this scalar model the boost grows with the destination star's
    speed, so max-boost = highest star speed among the candidates (tie-break lowest index). We
    scan only the nearest K (not the whole field) so a max-boost probe doesn't fly across the
    galaxy for a marginally bigger kick - a documented [ESTIMATE] bound.
    """
    if params.policy == "slingshot_maxboost":
        cand = _nearest_k_unsettled(s, frm, exclude, params.max_boost_candidates, params)
        if not cand:
            return None
        best = cand[0]
        for i in cand[1:]:
            if s.star_speed_pc_yr[i] > s.star_speed_pc_yr[best]:
                best = i
        return best
    return _nearest_unsettled(s, frm, exclude, params)


def _boosted_speed(current_pc_yr: float, star_speed_pc_yr: float, params: SwarmParams) -> float:
    """Galactic-frame speed after a slingshot off a star of the given speed.

    Powered policy: no slingshot, always the cruise speed. Otherwise (N&F Eq. 3–4): the
    max single-encounter gain is Δv_max = u_esc² / (u_esc²/(2u_i) + u_i), with u_i the
    probe's speed relative to the star. We take the boost-optimal (head-on) geometry,
    u_i ≈ current + star speed, and add Δv_max to the galactic speed - a documented
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
        hop = _dist(s, star, target)
        travel = hop / departing
        s.probes.append(
            Probe(
                id=s.next_probe_id,
                target=target,
                arrive_year=s.year + params.settle_time_years + travel,
                speed_pc_yr=departing,
                hop_len_pc=hop,
            )
        )
        s.next_probe_id += 1
        s.total_launched += 1
        # Read-only observability: mean effective launch speed (touches no RNG, no decision).
        s.launch_speed_sum_pc_yr += departing
        s.launch_count += 1


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


def _process_arrivals(state: SwarmState, params: SwarmParams, arrivals: list[Probe]) -> None:
    """Settle-or-waste the given arrivals (already sorted by (arrive_year, id)) at ``state.year``.

    Shared by both stepping schemes: a probe arriving at an already-settled star re-targets
    (the cost of stale info); the first to reach an unsettled star settles it and launches
    its offspring. Reads GROUND TRUTH on arrival - what the probe finds, not what it believed.
    """
    arrived_ids = {p.id for p in arrivals}
    # Keep non-arrived probes; launches and re-targets append into this same list.
    state.probes = [p for p in state.probes if p.id not in arrived_ids]

    state.total_arrivals += len(arrivals)
    for p in arrivals:
        if state.settled_year[p.target] < 0.0:
            # First to arrive: settle it and spread (slingshot off it, boosting offspring).
            state.settled_year[p.target] = state.year
            state.settle_hop_sum_pc += p.hop_len_pc  # winning-trip hop length (read-only)
            state.settle_hop_count += 1
            _launch_from(state, p.target, params, p.speed_pc_yr)
        else:
            # Raced and lost: a wasted trip (the cost of stale info). Re-target (by policy,
            # from this arrival star's belief), keeping this probe's speed - up to the cap.
            state.wasted_arrivals += 1
            state.wasted_hop_sum_pc += p.hop_len_pc  # wasted-trip hop length (read-only)
            state.wasted_hop_count += 1
            # The retarget cap only bites under lightspeed, where stale views cause bounce
            # chains; instant races resolve to a truly-unsettled star, so re-targeting is
            # unbounded there - keeping the perfect-info baseline bit-identical.
            if params.coordination == "lightspeed" and p.retargets >= params.max_retargets:
                continue  # bounce chain exhausted → retire the probe as wasted
            target = _select_target(state, p.target, set(), params)
            if target is not None:
                state.retarget_count += 1
                hop = _dist(state, p.target, target)
                travel = hop / p.speed_pc_yr
                state.probes.append(
                    Probe(
                        id=p.id, target=target, arrive_year=state.year + travel,
                        speed_pc_yr=p.speed_pc_yr, retargets=p.retargets + 1, hop_len_pc=hop,
                    )
                )


def step(state: SwarmState, params: SwarmParams) -> SwarmState:
    """Advance one FIXED timestep of ``dt_years``. Mutates and returns ``state``.

    Processes every probe that has arrived by the new ``year`` together, in deterministic
    order. Simple and cheap, but if ``dt`` exceeds the hop time it batches many launches into
    one step (they all decide from the same snapshot), which over-synchronizes races and
    inflates the coordination tax - use ``stepping="event"`` in the boosted regime.
    """
    state.year += params.dt_years
    arrivals = sorted(
        (p for p in state.probes if p.arrive_year <= state.year),
        key=lambda p: (p.arrive_year, p.id),
    )
    if not arrivals:
        return state
    _process_arrivals(state, params, arrivals)
    return state


def step_event(state: SwarmState, params: SwarmParams) -> SwarmState:
    """Advance to the NEXT probe arrival (event-driven, dt-independent). Mutates ``state``.

    Jumps ``year`` to the earliest ``arrive_year`` and processes exactly the probes arriving
    then (ties broken by id). This is the exact continuum (dt -> 0) limit: launches are
    staggered at their true times and ground truth updates between events, so no fixed-step
    over-synchronization. No-op when there are no probes.
    """
    if not state.probes:
        return state
    next_year = min(p.arrive_year for p in state.probes)
    state.year = next_year
    arrivals = sorted(
        (p for p in state.probes if p.arrive_year <= next_year),
        key=lambda p: (p.arrive_year, p.id),
    )
    _process_arrivals(state, params, arrivals)
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
    # t100 is a fragile tail statistic (the last few stars dominate it); we also record
    # earlier coverage fractions so the penalty can be reported where it is more robust.
    pcts = (25, 50, 75, 90, 99, 100)
    thresholds = {p: None for p in pcts}  # type: dict[int, float | None]

    def record_thresholds() -> None:
        frac = state.n_settled() / n_stars * 100.0
        for pct in pcts:
            if thresholds[pct] is None and frac >= pct:
                thresholds[pct] = state.year

    record_thresholds()
    if params.stepping == "event":
        # Event-driven: one step per arrival, jumping to the next event; dt-independent.
        while state.probes:
            if min(p.arrive_year for p in state.probes) > params.max_years:
                break
            step_event(state, params)
            steps.append(_snapshot(state, n_stars))
            record_thresholds()
    else:
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
        t25_years=thresholds[25],
        t75_years=thresholds[75],
        t99_years=thresholds[99],
        front_radius_pc=_front_radius(state),
        max_probe_speed_km_s=state.max_speed_pc_yr / KM_S_TO_PC_YR,
        policy=params.policy,
        coordination=params.coordination,
        total_arrivals=state.total_arrivals,
        wasted_arrivals=state.wasted_arrivals,
        retarget_count=state.retarget_count,
        mean_launch_speed_km_s=(
            state.launch_speed_sum_pc_yr / state.launch_count / KM_S_TO_PC_YR
            if state.launch_count else 0.0
        ),
        mean_settle_hop_pc=(
            state.settle_hop_sum_pc / state.settle_hop_count if state.settle_hop_count else 0.0
        ),
        mean_wasted_hop_pc=(
            state.wasted_hop_sum_pc / state.wasted_hop_count if state.wasted_hop_count else 0.0
        ),
        steps=steps,
    )
