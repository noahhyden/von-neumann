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

import math

from swarm.models import (
    C_PC_PER_YEAR,
    HOP_BIN_EDGES,
    KM_S_TO_PC_YR,
    Probe,
    SwarmParams,
    SwarmResult,
    SwarmState,
    SwarmStep,
)
from swarm.rng import next_float, seed_state


def _reflect(x: float, L: float) -> float:
    """Reflect a coordinate into ``[0, L]`` (triangle wave), preserving the star count and box.

    Reflecting rather than clipping keeps every scattered star inside the box, so a clumpy field
    has EXACTLY the same star count and mean density ``N/L^3`` as the uniform one - the fair-comparison
    invariant. Pure and deterministic.
    """
    if L <= 0.0:
        return 0.0
    period = 2.0 * L
    m = x - period * math.floor(x / period)  # x mod period, in [0, period)
    return m if m <= L else period - m


def _normal_pair(rng: int) -> tuple[float, float, int]:
    """Two independent standard normals from the seeded uniform stream (Box-Muller).

    Consumes exactly two uniforms and returns two normals in a fixed order, so the per-star draw
    count is constant (never a state-dependent carry-over) and the field stays a pure function of
    (params, seed) - the CLAUDE.md 7 determinism rule a future TS port must match.
    """
    u1, rng = next_float(rng)
    u2, rng = next_float(rng)
    u1 = u1 if u1 > 1e-12 else 1e-12  # guard log(0); deterministic clamp
    r = math.sqrt(-2.0 * math.log(u1))
    return r * math.cos(2.0 * math.pi * u2), r * math.sin(2.0 * math.pi * u2), rng


def _thomas_positions(params: SwarmParams, rng: int) -> tuple[list[float], list[float], list[float], int]:
    """Thomas (Neyman-Scott) cluster process: ``n_clumps`` centres, stars scattered Gaussian around them.

    Parent centres are uniform in the box; each star is assigned to a parent round-robin by index
    (deterministic, no RNG, so clumps are equal-sized) and placed at ``parent + sigma * N(0,1)`` per
    axis, reflected into the box. ``sigma = clump_sigma_frac * L``: small -> tight clumps and voids;
    large -> the field relaxes to uniform (the correctness limit). Fixed 4 uniforms/star (2 pairs,
    3 used) keeps the draw count constant.
    """
    L = params.box_side_pc
    n_clumps = max(1, int(params.n_clumps or 1))
    sigma = params.clump_sigma_frac * L
    cx: list[float] = []
    cy: list[float] = []
    cz: list[float] = []
    for _ in range(n_clumps):
        a, rng = next_float(rng)
        b, rng = next_float(rng)
        c, rng = next_float(rng)
        cx.append(a * L)
        cy.append(b * L)
        cz.append(c * L)
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for i in range(params.n_stars):
        p = i % n_clumps  # round-robin: deterministic, equal-size clumps, consumes no RNG
        z0, z1, rng = _normal_pair(rng)
        z2, _z3, rng = _normal_pair(rng)  # draw 4 normals (fixed count); use 3, one axis each
        xs.append(_reflect(cx[p] + sigma * z0, L))
        ys.append(_reflect(cy[p] + sigma * z1, L))
        zs.append(_reflect(cz[p] + sigma * z2, L))
    return xs, ys, zs, rng


def _hop_bin(d: float) -> int:
    """Index of hop length ``d`` (pc) into ``HOP_BIN_EDGES`` (0 = underflow .. len = overflow)."""
    k = 0
    for e in HOP_BIN_EDGES:
        if d >= e:
            k += 1
        else:
            break
    return k


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
    if params.n_clumps is not None and int(params.n_clumps) >= 1:
        # Clumpy (Thomas cluster process) field. A brand-new config with no committed baseline;
        # the uniform default below is left byte-for-byte unchanged so all prior runs are untouched.
        xs, ys, zs, rng = _thomas_positions(params, rng)
    else:
        xs = []
        ys = []
        zs = []
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


def _believes_settled_at(
    s: SwarmState, px: float, py: float, pz: float, i: int, year: float, coordination: str
) -> bool:
    """Does an observer at point ``(px,py,pz)`` in ``year`` know star ``i`` is settled?

    The light-speed-limited coordination gate (FRONTIER #1). A settled star is a beacon
    emitting "I'm settled" at ``settled_year[i]``; the news reaches the observer only after the
    light-travel time ``dist/c``. Under ``"lightspeed"``/``"inflight"`` the observer believes
    ``i`` settled iff the beacon has had time to arrive; under ``"instant"`` (perfect global
    info) this collapses to ``settled_year[i] >= 0`` - bit-identical to slices 1-3. Pure
    function of state (positions + settled_year + the sourced ``C_PC_PER_YEAR``); no RNG.
    """
    if s.settled_year[i] < 0.0:
        return False
    if coordination == "instant":
        return True
    dx = s.xs[i] - px
    dy = s.ys[i] - py
    dz = s.zs[i] - pz
    d = (dx * dx + dy * dy + dz * dz) ** 0.5
    return s.settled_year[i] + d / C_PC_PER_YEAR <= year


def _believes_settled(s: SwarmState, frm: int, i: int, params: SwarmParams) -> bool:
    """Star-based wrapper: the observer sits AT star ``frm`` in ``s.year`` (a decision site).

    "instant"/"lightspeed" decide only at stars, so this is the whole gate for them and is
    bit-identical to the pre-refactor version. "inflight" additionally evaluates the gate at a
    probe's mid-flight position via ``_believes_settled_at`` (see ``_process_learns``).
    """
    return _believes_settled_at(s, s.xs[frm], s.ys[frm], s.zs[frm], i, s.year, params.coordination)


def _nearest_unsettled_at(
    s: SwarmState, px: float, py: float, pz: float, year: float, coordination: str, exclude: set[int]
) -> int | None:
    """Index of the nearest *believed*-unsettled star to point ``(px,py,pz)`` not in ``exclude``.

    O(N) scan; deterministic tie-break by lowest index. (Spatial hashing to make this
    O(1)-ish is the scale slice.)
    """
    best: int | None = None
    best_d2 = float("inf")
    for i in range(len(s.xs)):
        if i in exclude or _believes_settled_at(s, px, py, pz, i, year, coordination):
            continue
        dx = s.xs[i] - px
        dy = s.ys[i] - py
        dz = s.zs[i] - pz
        d2 = dx * dx + dy * dy + dz * dz
        if d2 < best_d2:
            best_d2 = d2
            best = i
    return best


def _nearest_unsettled(s: SwarmState, frm: int, exclude: set[int], params: SwarmParams) -> int | None:
    return _nearest_unsettled_at(s, s.xs[frm], s.ys[frm], s.zs[frm], s.year, params.coordination, exclude)


def _nearest_k_unsettled_at(
    s: SwarmState, px: float, py: float, pz: float, year: float, coordination: str, k: int, exclude: set[int]
) -> list[int]:
    """The ``k`` nearest *believed*-unsettled stars to a point (deterministic order by (distance, index))."""
    cands: list[tuple[float, int]] = []
    for i in range(len(s.xs)):
        if i in exclude or _believes_settled_at(s, px, py, pz, i, year, coordination):
            continue
        dx = s.xs[i] - px
        dy = s.ys[i] - py
        dz = s.zs[i] - pz
        cands.append((dx * dx + dy * dy + dz * dz, i))
    cands.sort()
    return [i for _, i in cands[:k]]


def _select_target_at(
    s: SwarmState, px: float, py: float, pz: float, year: float, params: SwarmParams, exclude: set[int]
) -> int | None:
    """Pick the next star per policy from point ``(px,py,pz)``, reading light-delayed belief.

    powered / slingshot_nearest → nearest believed-unsettled star. slingshot_maxboost → among
    the nearest ``max_boost_candidates`` believed-unsettled stars, the one whose slingshot
    gives the largest boost (highest star speed in this scalar model; tie-break lowest index).
    We scan only the nearest K so a max-boost probe doesn't cross the galaxy for a marginal
    kick - a documented [ESTIMATE] bound.
    """
    if params.policy == "slingshot_maxboost":
        cand = _nearest_k_unsettled_at(s, px, py, pz, year, params.coordination, params.max_boost_candidates, exclude)
        if not cand:
            return None
        best = cand[0]
        for i in cand[1:]:
            if s.star_speed_pc_yr[i] > s.star_speed_pc_yr[best]:
                best = i
        return best
    return _nearest_unsettled_at(s, px, py, pz, year, params.coordination, exclude)


def _select_target(s: SwarmState, frm: int, exclude: set[int], params: SwarmParams) -> int | None:
    """Star-based wrapper: decide AT star ``frm`` in ``s.year``."""
    return _select_target_at(s, s.xs[frm], s.ys[frm], s.zs[frm], s.year, params, exclude)


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
                from_x=s.xs[star], from_y=s.ys[star], from_z=s.zs[star],
                launch_year=s.year + params.settle_time_years,
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
            state.settle_hop_hist[_hop_bin(p.hop_len_pc)] += 1  # won arrivals by hop-length bin
            state.settle_v_sum_pc_yr += p.speed_pc_yr  # winning-trip flight speed (energy weight)
            state.settle_v2_sum += p.speed_pc_yr * p.speed_pc_yr
            _launch_from(state, p.target, params, p.speed_pc_yr)
        else:
            # Raced and lost: a wasted trip (the cost of stale info). Re-target (by policy,
            # from this arrival star's belief), keeping this probe's speed - up to the cap.
            state.wasted_arrivals += 1
            state.wasted_hop_sum_pc += p.hop_len_pc  # wasted-trip hop length (read-only)
            state.wasted_hop_count += 1
            state.wasted_hop_hist[_hop_bin(p.hop_len_pc)] += 1  # wasted arrivals by hop-length bin
            state.wasted_travel_pc += p.hop_len_pc  # a lost full arrival wastes its whole hop
            state.wasted_v_sum_pc_yr += p.speed_pc_yr  # wasted-trip flight speed (energy weight)
            state.wasted_v2_sum += p.speed_pc_yr * p.speed_pc_yr
            # Retire a probe after too many lost races (a bounce-chain bound). Applied to BOTH
            # coordination modes: instant also loses in-transit races and re-targets (a probe
            # aims at a truly-unsettled star but another can settle it before it arrives), so it
            # is NOT bounce-free. Capping only lightspeed would inflate instant's wasted-trip
            # count and bias the paired fuel comparison. Bookkeeping, not physics; the results
            # are shown insensitive to the threshold.
            if p.retargets >= params.max_retargets:
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
                        from_x=state.xs[p.target], from_y=state.ys[p.target], from_z=state.zs[p.target],
                        launch_year=state.year,
                    )
                )


def _learn_year(p: Probe, settled_year: list[float]) -> float:
    """Year the beacon from ``p``'s (already-settled) target overtakes ``p`` in flight.

    ``p`` flies straight at its target star at speed ``v``, so its distance to the target is
    ``d(t) = v*(arrive - t)``. The beacon leaves the target at ``settled_year[target]`` and
    travels at ``c``; it reaches ``p`` when ``settled + d(t)/c = t``. Solving:
    ``t = (settled + (v/c)*arrive) / (1 + v/c)``. Always in ``(settled, arrive)`` - the probe
    learns strictly before it would have arrived, because the beacon (c) closes on it faster
    than it closes on the target (v). Closed form: deterministic, no RNG, no iteration.
    """
    v_over_c = p.speed_pc_yr / C_PC_PER_YEAR
    return (settled_year[p.target] + v_over_c * p.arrive_year) / (1.0 + v_over_c)


def _is_doomed(state: SwarmState, p: Probe) -> bool:
    """``p``'s target has been claimed by another probe (ground truth), so ``p`` will waste."""
    return state.settled_year[p.target] >= 0.0


def _actionable_year(state: SwarmState, params: SwarmParams, p: Probe) -> float:
    """When ``p`` next acts: its mid-flight learning time if doomed under inflight, else arrival.

    Under "inflight" a doomed probe redirects at ``_learn_year`` (< its arrival); everything
    else acts on arrival. Because the loop always advances to the global minimum of this over
    all probes, no learning time is ever skipped, so the mid-flight redirect is event-exact
    (no fixed-step artifact).
    """
    if params.coordination == "inflight" and _is_doomed(state, p):
        tl = _learn_year(p, state.settled_year)
        if tl < p.arrive_year:
            return tl
    return p.arrive_year


def _next_event_year(state: SwarmState, params: SwarmParams) -> float | None:
    """Earliest actionable time over all in-flight probes (arrival or mid-flight learning)."""
    if not state.probes:
        return None
    return min(_actionable_year(state, params, p) for p in state.probes)


def _process_learns(state: SwarmState, params: SwarmParams, learns: list[Probe]) -> None:
    """Redirect each mid-flight learner at ``state.year`` (inflight only).

    Each learner's target was claimed by another probe; the beacon has now overtaken it. It
    aborts the doomed hop at its current (interpolated) position and re-aims at cruise speed -
    so it never completes the wasted arrival and never brakes at the claimed star. The partial
    distance already flown is charged as redundant travel; NO wasted-rendezvous energy is
    charged (it did not decelerate). Retires if the re-target cap is hit or nothing is believed
    unsettled from here.
    """
    learn_ids = {p.id for p in learns}
    state.probes = [p for p in state.probes if p.id not in learn_ids]
    for p in learns:
        # Position when the beacon overtook it: interpolate from the launch point to the target.
        span = p.arrive_year - p.launch_year
        frac = (state.year - p.launch_year) / span if span > 0.0 else 1.0
        frac = 0.0 if frac < 0.0 else (1.0 if frac > 1.0 else frac)
        tx, ty, tz = state.xs[p.target], state.ys[p.target], state.zs[p.target]
        px = p.from_x + (tx - p.from_x) * frac
        py = p.from_y + (ty - p.from_y) * frac
        pz = p.from_z + (tz - p.from_z) * frac
        state.wasted_travel_pc += p.hop_len_pc * frac  # partial redundant travel (not the whole hop)
        state.midflight_aborts += 1
        if p.retargets >= params.max_retargets:
            continue  # bounce chain exhausted -> retire the probe
        target = _select_target_at(state, px, py, pz, state.year, params, set())
        if target is None:
            continue  # nothing believed-unsettled from here -> retire
        state.retarget_count += 1
        dx = state.xs[target] - px
        dy = state.ys[target] - py
        dz = state.zs[target] - pz
        hop = (dx * dx + dy * dy + dz * dz) ** 0.5
        travel = hop / p.speed_pc_yr
        state.probes.append(
            Probe(
                id=p.id, target=target, arrive_year=state.year + travel,
                speed_pc_yr=p.speed_pc_yr, retargets=p.retargets + 1, hop_len_pc=hop,
                from_x=px, from_y=py, from_z=pz, launch_year=state.year,
            )
        )


def _resolve_events(state: SwarmState, params: SwarmParams, cutoff: float) -> None:
    """Process every probe whose actionable time is <= ``cutoff``, at ``state.year == cutoff``.

    Splits them into arrivals (settle-or-waste at a star) and, under inflight, mid-flight
    learns (redirects). Arrivals run first so ground-truth settlements are visible; a probe
    doomed by one of those settlements has ``_learn_year > cutoff`` and is handled next event.
    For "instant"/"lightspeed" there are never any learns, so this is bit-identical to the
    old arrivals-only path.
    """
    arrivals: list[Probe] = []
    learns: list[Probe] = []
    inflight = params.coordination == "inflight"
    for p in state.probes:
        if _actionable_year(state, params, p) <= cutoff:
            if inflight and _is_doomed(state, p) and _learn_year(p, state.settled_year) < p.arrive_year:
                learns.append(p)
            else:
                arrivals.append(p)
    arrivals.sort(key=lambda p: (p.arrive_year, p.id))
    learns.sort(key=lambda p: (p.arrive_year, p.id))
    if arrivals:
        _process_arrivals(state, params, arrivals)
    if learns:
        _process_learns(state, params, learns)


def step(state: SwarmState, params: SwarmParams) -> SwarmState:
    """Advance one FIXED timestep of ``dt_years``. Mutates and returns ``state``.

    Processes every probe that has arrived by the new ``year`` together, in deterministic
    order. Simple and cheap, but if ``dt`` exceeds the hop time it batches many launches into
    one step (they all decide from the same snapshot), which over-synchronizes races and
    inflates the coordination tax - use ``stepping="event"`` in the boosted regime. (inflight
    mid-flight learning is event-exact only under ``stepping="event"``; in fixed mode it is
    resolved at the step boundary, so run the floor bracket in event mode.)
    """
    state.year += params.dt_years
    _resolve_events(state, params, state.year)
    return state


def step_event(state: SwarmState, params: SwarmParams) -> SwarmState:
    """Advance to the NEXT event (arrival, or inflight mid-flight learning). Mutates ``state``.

    Jumps ``year`` to the earliest actionable time and processes exactly the probes acting then
    (ties broken by id). This is the exact continuum (dt -> 0) limit: launches are staggered at
    their true times, ground truth and beacon-learning update between events, so there is no
    fixed-step over-synchronization. No-op when there are no probes.
    """
    if not state.probes:
        return state
    next_year = _next_event_year(state, params)
    if next_year is None:
        return state
    state.year = next_year
    _resolve_events(state, params, next_year)
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
        # Event-driven: one step per event, jumping to the next event; dt-independent. The event
        # is the earliest arrival OR (inflight) mid-flight learning, so the loop guard uses the
        # same actionable-time helper the step does.
        while state.probes:
            ne = _next_event_year(state, params)
            if ne is None or ne > params.max_years:
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
        wasted_travel_pc=state.wasted_travel_pc,
        midflight_aborts=state.midflight_aborts,
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
        # Newtonian specific kinetic energy (1/2)(v/c)^2 summed over journeys (fraction of c^2).
        settle_energy_c2=0.5 * state.settle_v2_sum / (C_PC_PER_YEAR * C_PC_PER_YEAR),
        wasted_energy_c2=0.5 * state.wasted_v2_sum / (C_PC_PER_YEAR * C_PC_PER_YEAR),
        mean_settle_speed_km_s=(
            state.settle_v_sum_pc_yr / state.settle_hop_count / KM_S_TO_PC_YR
            if state.settle_hop_count else 0.0
        ),
        mean_wasted_speed_km_s=(
            state.wasted_v_sum_pc_yr / state.wasted_hop_count / KM_S_TO_PC_YR
            if state.wasted_hop_count else 0.0
        ),
        settle_hop_hist=list(state.settle_hop_hist),
        wasted_hop_hist=list(state.wasted_hop_hist),
        steps=steps,
    )
