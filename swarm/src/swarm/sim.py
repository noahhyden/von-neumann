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

import bisect
import heapq
import math
import os
from dataclasses import dataclass

import numpy as np

from swarm.models import (
    C_PC_PER_YEAR,
    HOP_BIN_EDGES,
    KM_S_TO_PC_YR,
    WALL_BIN_EDGES_NN,
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


def _wall_bin(s: SwarmState, params: SwarmParams, star: int) -> int:
    """Bin star ``star`` by its distance to the nearest box wall, in mean-NN-distance units.

    Pure geometry (no RNG, no decision), so it cannot perturb the fold. The mean nearest-neighbour
    distance ``E[NN] = 0.55396 * rho^(-1/3)`` (Clark & Evans 1954) is fixed by density, so the bins
    are comparable across N. Used only by the finite-size edge test (M1): a star deep in the bulk
    lands in a high bin, one hugging a wall in bin 0.
    """
    L = params.box_side_pc
    wall = min(s.xs[star], L - s.xs[star], s.ys[star], L - s.ys[star], s.zs[star], L - s.zs[star])
    d_nn = 0.55396 * params.density_stars_per_pc3 ** (-1.0 / 3.0)
    r = wall / d_nn if d_nn > 0.0 else 0.0
    k = 0
    for e in WALL_BIN_EDGES_NN:
        if r >= e:
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
    if s.periodic:
        # Minimum-image convention on a torus of period L: the shortest separation wraps the box, so
        # there are no boundary stars. Opt-in (default off); with periodic=False this is a no-op and
        # the fold is bit-identical to the hard-walled model. The belief gate reads the same wrapped
        # distance, so light also travels the minimum image.
        L = s.box_side_pc
        dx -= L * round(dx / L)
        dy -= L * round(dy / L)
        dz -= L * round(dz / L)
    return (dx * dx + dy * dy + dz * dz) ** 0.5


_KD_LEAF = 8  # max stars per leaf bucket: small enough that a leaf scan is cheap, large enough
#               that the tree stays shallow and Python per-node overhead is amortized.


def _build_kdtree(xs: list[float], ys: list[float], zs: list[float]) -> dict:
    """Balanced k-d tree over the fixed star positions (issue #30), returned as flat SoA arrays.

    Median-split on the widest axis of each node's bounding box, recursing until a node holds
    <= ``_KD_LEAF`` stars. Splits break ties by (coordinate, star index) so the tree is a pure,
    deterministic function of the positions (a future TypeScript port builds the same tree). All
    stars start unsettled: ``kd_nuns`` = subtree size, ``kd_tsmax`` = -1. The plain (non-wrapped)
    metric is baked into the bounding boxes, matching target selection (which never uses the
    periodic minimum image). Only the SHAPE of the search changes here, never which star it returns.
    """
    n = len(xs)
    axis: list[int] = []
    split: list[float] = []
    lo: list[int] = []
    hi: list[int] = []
    parent: list[int] = []
    bucket: list[list[int] | None] = []
    bxmin: list[float] = []
    bxmax: list[float] = []
    bymin: list[float] = []
    bymax: list[float] = []
    bzmin: list[float] = []
    bzmax: list[float] = []
    nuns: list[int] = []
    tsmax: list[float] = []
    star_leaf = [0] * n
    coords = (xs, ys, zs)

    def new_node() -> int:
        axis.append(-1)
        split.append(0.0)
        lo.append(-1)
        hi.append(-1)
        parent.append(-1)
        bucket.append(None)
        bxmin.append(0.0)
        bxmax.append(0.0)
        bymin.append(0.0)
        bymax.append(0.0)
        bzmin.append(0.0)
        bzmax.append(0.0)
        nuns.append(0)
        tsmax.append(-1.0)
        return len(axis) - 1

    def build(idx: list[int]) -> int:
        node = new_node()
        i0 = idx[0]
        xmn = xmx = xs[i0]
        ymn = ymx = ys[i0]
        zmn = zmx = zs[i0]
        for i in idx:
            xi = xs[i]
            if xi < xmn:
                xmn = xi
            elif xi > xmx:
                xmx = xi
            yi = ys[i]
            if yi < ymn:
                ymn = yi
            elif yi > ymx:
                ymx = yi
            zi = zs[i]
            if zi < zmn:
                zmn = zi
            elif zi > zmx:
                zmx = zi
        bxmin[node] = xmn
        bxmax[node] = xmx
        bymin[node] = ymn
        bymax[node] = ymx
        bzmin[node] = zmn
        bzmax[node] = zmx
        nuns[node] = len(idx)  # all unsettled at build; origin is marked settled afterwards
        if len(idx) <= _KD_LEAF:
            bucket[node] = list(idx)
            for i in idx:
                star_leaf[i] = node
            return node
        ex = xmx - xmn
        ey = ymx - ymn
        ez = zmx - zmn
        ax = 0 if (ex >= ey and ex >= ez) else (1 if ey >= ez else 2)
        c = coords[ax]
        idx.sort(key=lambda i: (c[i], i))  # deterministic: ties broken by star index
        mid = len(idx) // 2
        axis[node] = ax
        split[node] = c[idx[mid]]
        left = build(idx[:mid])
        right = build(idx[mid:])
        parent[left] = node
        parent[right] = node
        lo[node] = left
        hi[node] = right
        return node

    root = build(list(range(n))) if n else -1
    # Flatten bucket (list[list[int] | None]) to (bucket_flat, bucket_offsets) so the njit
    # hot loop reads it as two flat numpy arrays; bit-identical iteration order because we
    # concatenate in node id order and each leaf's bucket in its stored order (issue #27
    # Part 4). Empty for internal nodes; offsets[i+1] - offsets[i] == 0 there.
    n_nodes = len(axis)
    offsets = np.zeros(n_nodes + 1, dtype=np.int32)
    flat_parts: list[int] = []
    for i in range(n_nodes):
        b = bucket[i]
        if b is not None:
            flat_parts.extend(b)
        offsets[i + 1] = len(flat_parts)
    return {
        "root": root,
        "axis": np.asarray(axis, dtype=np.int8),
        "split": np.asarray(split, dtype=np.float64),
        "lo": np.asarray(lo, dtype=np.int32),
        "hi": np.asarray(hi, dtype=np.int32),
        "parent": np.asarray(parent, dtype=np.int32),
        "bucket_flat": np.asarray(flat_parts, dtype=np.int32),
        "bucket_offsets": offsets,
        "bxmin": np.asarray(bxmin, dtype=np.float64),
        "bxmax": np.asarray(bxmax, dtype=np.float64),
        "bymin": np.asarray(bymin, dtype=np.float64),
        "bymax": np.asarray(bymax, dtype=np.float64),
        "bzmin": np.asarray(bzmin, dtype=np.float64),
        "bzmax": np.asarray(bzmax, dtype=np.float64),
        "nuns": np.asarray(nuns, dtype=np.int32),
        "tsmax": np.asarray(tsmax, dtype=np.float64),
        "star_leaf": np.asarray(star_leaf, dtype=np.int32),
    }


def _kd_mark_settled(s: SwarmState, star: int) -> None:
    """Record that ``star`` just settled, updating the subtree aggregates leaf -> root (O(depth)).

    Decrements the unsettled count and raises ``kd_tsmax`` to the star's settled_year along the
    whole path to the root. ``state.year`` is non-decreasing, so a fresh settle always carries the
    largest settled_year in each ancestor subtree - the guarded max keeps that exact regardless.
    Must be called exactly once per star, right after ``settled_year[star]`` is set.
    """
    y = s.settled_year[star]
    nuns = s.kd_nuns
    tsmax = s.kd_tsmax
    parent = s.kd_parent
    node = s.star_leaf[star]
    while node != -1:
        nuns[node] -= 1
        if y > tsmax[node]:
            tsmax[node] = y
        node = parent[node]


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
    sy = float(s.settled_year[i])
    if sy < 0.0:
        return False
    if coordination == "instant":
        return True
    dx = float(s.xs[i]) - px
    dy = float(s.ys[i]) - py
    dz = float(s.zs[i]) - pz
    d = (dx * dx + dy * dy + dz * dz) ** 0.5
    return bool(sy + d / C_PC_PER_YEAR <= year)


def _believes_settled(s: SwarmState, frm: int, i: int, params: SwarmParams) -> bool:
    """Star-based wrapper: the observer sits AT star ``frm`` in ``s.year`` (a decision site).

    "instant"/"lightspeed" decide only at stars, so this is the whole gate for them and is
    bit-identical to the pre-refactor version. "inflight" additionally evaluates the gate at a
    probe's mid-flight position via ``_believes_settled_at`` (see ``_process_learns``).
    """
    return _believes_settled_at(s, s.xs[frm], s.ys[frm], s.zs[frm], i, s.year, params.coordination)


# Module-init: decide which path once. `SWARM_NO_NJIT=1` forces the pure-Python
# reference; if numba is unavailable, kd_njit.HAS_NJIT is False and we also fall
# back. The check runs at import time so per-query calls have zero import cost.
try:
    from swarm.kd_njit import HAS_NJIT as _HAS_NJIT, nearest_unsettled_njit as _NJIT_KERNEL
except ImportError:
    _HAS_NJIT = False
    _NJIT_KERNEL = None

_USE_NJIT = _HAS_NJIT and os.environ.get("SWARM_NO_NJIT") != "1"

_EXCLUDE_SCRATCH = np.zeros(64, dtype=np.int32)  # reused per query to avoid alloc


def _nearest_unsettled_at(
    s: SwarmState, px: float, py: float, pz: float, year: float, coordination: str, exclude: set[int]
) -> int | None:
    """Index of the nearest *believed*-unsettled star to point ``(px,py,pz)`` not in ``exclude``.

    Numba-jitted k-d tree branch-and-bound (#27 Part 4, on top of #30). The jitted hot
    loop is `swarm.kd_njit.nearest_unsettled_njit`; a `SWARM_NO_NJIT=1` env var forces
    the pure-Python fallback below (used for debugging and no-numba environments).
    The two paths are bit-identical: same DFS order (preallocated int32 stack in the
    njit version reproduces list append/pop semantics), same (d^2, lowest-index)
    tie-break, same inlined `_believes_settled_at` gate. See kd_njit.py for the flags.
    """
    if _USE_NJIT:
        # Pack the exclude set into a small numpy array (typical len 0-2 in the powered
        # policy; capped at max_boost_candidates ~30 upstream). Skip work when empty.
        n_ex = len(exclude)
        if n_ex > 0:
            if n_ex > _EXCLUDE_SCRATCH.size:
                raise ValueError(f"exclude set too large ({n_ex} > {_EXCLUDE_SCRATCH.size})")
            for j, e in enumerate(exclude):
                _EXCLUDE_SCRATCH[j] = e
        r = _NJIT_KERNEL(
            px, py, pz, year, coordination == "instant",
            s.xs, s.ys, s.zs, s.settled_year,
            s.kd_root, s.kd_axis, s.kd_split, s.kd_lo, s.kd_hi,
            s.kd_bxmin, s.kd_bxmax, s.kd_bymin, s.kd_bymax, s.kd_bzmin, s.kd_bzmax,
            s.kd_nuns, s.kd_tsmax,
            s.kd_bucket_flat, s.kd_bucket_offsets,
            _EXCLUDE_SCRATCH, n_ex,
        )
        return int(r) if r >= 0 else None
    return _nearest_unsettled_at_python(s, px, py, pz, year, coordination, exclude)


def _nearest_unsettled_at_python(
    s: SwarmState, px: float, py: float, pz: float, year: float, coordination: str, exclude: set[int]
) -> int | None:
    """Pure-Python fallback (bit-identical reference for the njit path)."""
    xs, ys, zs = s.xs, s.ys, s.zs
    axis = s.kd_axis
    split = s.kd_split
    lo = s.kd_lo
    hi = s.kd_hi
    bucket_flat = s.kd_bucket_flat
    bucket_offsets = s.kd_bucket_offsets
    bxmin = s.kd_bxmin
    bxmax = s.kd_bxmax
    bymin = s.kd_bymin
    bymax = s.kd_bymax
    bzmin = s.kd_bzmin
    bzmax = s.kd_bzmax
    nuns = s.kd_nuns
    tsmax = s.kd_tsmax
    instant = coordination == "instant"
    c = C_PC_PER_YEAR
    best = -1
    best_d2 = float("inf")
    stack = [s.kd_root]
    while stack:
        node = stack.pop()
        # Distance lower bound dlo^2: nearest point of the box to (px,py,pz), clamped per axis.
        dlo2 = 0.0
        t = bxmin[node] - px
        if t > 0.0:
            dlo2 = t * t
        else:
            t = px - bxmax[node]
            if t > 0.0:
                dlo2 = t * t
        t = bymin[node] - py
        if t > 0.0:
            dlo2 += t * t
        else:
            t = py - bymax[node]
            if t > 0.0:
                dlo2 += t * t
        t = bzmin[node] - pz
        if t > 0.0:
            dlo2 += t * t
        else:
            t = pz - bzmax[node]
            if t > 0.0:
                dlo2 += t * t
        if dlo2 > best_d2:
            continue  # nothing in this box can beat or tie the best (equality would fall through)
        if nuns[node] == 0:
            if instant:
                continue  # every star settled == every star believed-settled (c -> infinity)
            # dhi = farthest corner of the box; if that beacon has arrived, all have.
            a = px - bxmin[node]
            b = px - bxmax[node]
            a2 = a * a
            b2 = b * b
            dhi2 = a2 if a2 > b2 else b2
            a = py - bymin[node]
            b = py - bymax[node]
            a2 = a * a
            b2 = b * b
            dhi2 += a2 if a2 > b2 else b2
            a = pz - bzmin[node]
            b = pz - bzmax[node]
            a2 = a * a
            b2 = b * b
            dhi2 += a2 if a2 > b2 else b2
            if tsmax[node] + dhi2 ** 0.5 / c <= year:
                continue  # whole box believed-settled; skip
        ax = axis[node]
        if ax == -1:
            start = int(bucket_offsets[node])
            end = int(bucket_offsets[node + 1])
            for k in range(start, end):
                i = int(bucket_flat[k])
                if i in exclude or _believes_settled_at(s, px, py, pz, i, year, coordination):
                    continue
                dx = xs[i] - px
                dy = ys[i] - py
                dz = zs[i] - pz
                d2 = dx * dx + dy * dy + dz * dz
                if d2 < best_d2 or (d2 == best_d2 and best >= 0 and i < best):
                    best_d2 = d2
                    best = i
        else:
            p_ax = px if ax == 0 else (py if ax == 1 else pz)
            if p_ax < split[node]:
                stack.append(int(hi[node]))  # far child pushed first -> popped last
                stack.append(int(lo[node]))
            else:
                stack.append(int(lo[node]))
                stack.append(int(hi[node]))
    return best if best >= 0 else None


def _nearest_unsettled(s: SwarmState, frm: int, exclude: set[int], params: SwarmParams) -> int | None:
    return _nearest_unsettled_at(s, s.xs[frm], s.ys[frm], s.zs[frm], s.year, params.coordination, exclude)


def _nearest_k_unsettled_at(
    s: SwarmState, px: float, py: float, pz: float, year: float, coordination: str, k: int, exclude: set[int]
) -> list[int]:
    """The ``k`` nearest *believed*-unsettled stars to a point (deterministic order by (distance, index)).

    k-d tree branch-and-bound (issue #30), the k-nearest analogue of _nearest_unsettled_at. Keeps
    the current k best as a (d2, index)-sorted list; the distance prune skips a subtree whose
    nearest point is strictly farther than the current k-th best, and the belief prune skips a
    provably fully-believed-settled subtree (same news-in-transit-safe rule). Equality descends, so
    a same-distance lower-index star still displaces the k-th. The result is bit-identical to the
    linear scan's ``sorted(all_candidates)[:k]``: no pruned star could enter the top-k, and every
    survivor is tested with the exact belief gate and squared distance.
    """
    xs, ys, zs = s.xs, s.ys, s.zs
    axis = s.kd_axis
    split = s.kd_split
    lo = s.kd_lo
    hi = s.kd_hi
    bucket_flat = s.kd_bucket_flat
    bucket_offsets = s.kd_bucket_offsets
    bxmin = s.kd_bxmin
    bxmax = s.kd_bxmax
    bymin = s.kd_bymin
    bymax = s.kd_bymax
    bzmin = s.kd_bzmin
    bzmax = s.kd_bzmax
    nuns = s.kd_nuns
    tsmax = s.kd_tsmax
    instant = coordination == "instant"
    c = C_PC_PER_YEAR
    bestk: list[tuple[float, int]] = []  # k smallest (d2, index) so far, sorted ascending
    thresh = float("inf")  # d2 of the current k-th best (inf until we hold k)
    stack = [s.kd_root]
    while stack:
        node = stack.pop()
        dlo2 = 0.0
        t = bxmin[node] - px
        if t > 0.0:
            dlo2 = t * t
        else:
            t = px - bxmax[node]
            if t > 0.0:
                dlo2 = t * t
        t = bymin[node] - py
        if t > 0.0:
            dlo2 += t * t
        else:
            t = py - bymax[node]
            if t > 0.0:
                dlo2 += t * t
        t = bzmin[node] - pz
        if t > 0.0:
            dlo2 += t * t
        else:
            t = pz - bzmax[node]
            if t > 0.0:
                dlo2 += t * t
        if dlo2 > thresh:
            continue  # box cannot enter the top-k (equality descends)
        if nuns[node] == 0:
            if instant:
                continue
            a = px - bxmin[node]
            b = px - bxmax[node]
            a2 = a * a
            b2 = b * b
            dhi2 = a2 if a2 > b2 else b2
            a = py - bymin[node]
            b = py - bymax[node]
            a2 = a * a
            b2 = b * b
            dhi2 += a2 if a2 > b2 else b2
            a = pz - bzmin[node]
            b = pz - bzmax[node]
            a2 = a * a
            b2 = b * b
            dhi2 += a2 if a2 > b2 else b2
            if tsmax[node] + dhi2 ** 0.5 / c <= year:
                continue
        ax = axis[node]
        if ax == -1:
            start = int(bucket_offsets[node])
            end = int(bucket_offsets[node + 1])
            for k_idx in range(start, end):
                i = int(bucket_flat[k_idx])
                if i in exclude or _believes_settled_at(s, px, py, pz, i, year, coordination):
                    continue
                dx = xs[i] - px
                dy = ys[i] - py
                dz = zs[i] - pz
                d2 = dx * dx + dy * dy + dz * dz
                # Insert if we still need candidates, or (d2, i) ranks ahead of the current k-th -
                # the full-tuple compare lets a same-distance lower-index star displace it exactly
                # as sorted(all_candidates)[:k] would.
                if len(bestk) < k or (d2, i) < bestk[-1]:
                    bisect.insort(bestk, (d2, i))
                    if len(bestk) > k:
                        bestk.pop()
                    if len(bestk) == k:
                        thresh = bestk[-1][0]
        else:
            p_ax = px if ax == 0 else (py if ax == 1 else pz)
            if p_ax < split[node]:
                stack.append(int(hi[node]))
                stack.append(int(lo[node]))
            else:
                stack.append(int(lo[node]))
                stack.append(int(hi[node]))
    return [i for _, i in bestk]


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
        _add_probe(s, params, Probe(
            id=s.next_probe_id,
            target=target,
            arrive_year=s.year + params.settle_time_years + travel,
            speed_pc_yr=departing,
            hop_len_pc=hop,
            from_x=s.xs[star], from_y=s.ys[star], from_z=s.zs[star],
            launch_year=s.year + params.settle_time_years,
        ))
        s.next_probe_id += 1
        s.total_launched += 1
        # Read-only observability: mean effective launch speed (touches no RNG, no decision).
        s.launch_speed_sum_pc_yr += departing
        s.launch_count += 1


def _add_probe(s: SwarmState, params: SwarmParams, p: Probe) -> None:
    """Register a launched / re-targeted probe: live set, event heap, and (inflight) target index.

    The heap key is the probe's actionable time now (arrival, or - if it is already doomed at birth
    under inflight - its mid-flight learning time), so a lazy pop later validates against exactly
    this value. Re-targets reuse the id, so this simply overwrites the live entry and pushes a fresh
    heap key; the probe's previous (now stale) heap entry is discarded when it surfaces.
    """
    s.probes[p.id] = p
    heapq.heappush(s.ev_heap, (_actionable_year(s, params, p), p.id))
    if params.coordination == "inflight":
        s.by_target.setdefault(p.target, []).append(p.id)


def _on_settled(s: SwarmState, params: SwarmParams, star: int) -> None:
    """Reschedule the probes still heading to a star that was just claimed (inflight decrease-key).

    Their target is now settled (ground truth), so under inflight each acquires an earlier
    actionable time (the beacon overtakes it mid-flight); push that so the heap surfaces it before
    its arrival. No-op unless inflight - the other modes act only at stars, so a claimed target
    changes nothing until the probe arrives. The star settles exactly once, so this runs once per
    star; the list is then cleared (any later probe born toward this settled star schedules its own
    learning time at birth via _add_probe).
    """
    if params.coordination != "inflight":
        return
    lst = s.by_target.get(star)
    if not lst:
        return
    for pid in lst:
        q = s.probes.get(pid)
        if q is not None and q.target == star:  # still live and still heading here
            heapq.heappush(s.ev_heap, (_actionable_year(s, params, q), pid))
    s.by_target[star] = []


def _next_valid_event(state: SwarmState, params: SwarmParams) -> float | None:
    """Peek the earliest VALID actionable time on the heap, discarding stale entries (issue #27).

    A heap entry is stale if its probe is gone (already processed) or its stored key no longer
    equals the probe's current actionable time (an inflight decrease-key superseded it). Returns
    None only when no live probe remains. O(log P) amortized - each entry is discarded at most once.
    """
    heap = state.ev_heap
    while heap:
        key, pid = heap[0]
        p = state.probes.get(pid)
        if p is None or _actionable_year(state, params, p) != key:
            heapq.heappop(heap)
            continue
        return key
    return None


def _pop_due(state: SwarmState, params: SwarmParams, cutoff: float) -> list[Probe]:
    """Pop every live probe whose CURRENT actionable time is <= ``cutoff`` (pre-processing state).

    Exactly reproduces the old ``[p for p in probes if _actionable_year(p) <= cutoff]`` scan: every
    live probe has a valid heap entry keyed at its actionable time, so all due probes surface here;
    stale and duplicate (same-id) entries are filtered. The batch order is irrelevant - the caller
    re-sorts by (arrive_year, id) - so the result is identical regardless of heap tie ordering.
    """
    batch: list[Probe] = []
    seen: set[int] = set()
    heap = state.ev_heap
    while heap and heap[0][0] <= cutoff:
        key, pid = heapq.heappop(heap)
        p = state.probes.get(pid)
        if p is None or pid in seen:
            continue
        if _actionable_year(state, params, p) != key:
            continue  # stale entry (superseded or already re-targeted)
        seen.add(pid)
        batch.append(p)
    return batch


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
    # Convert positions and per-star arrays to numpy so the njit kernel reads them
    # directly (#27 Part 4). No behaviour change; numpy fixed-index assignment matches
    # Python list assignment element-wise.
    xs_np = np.asarray(xs, dtype=np.float64)
    ys_np = np.asarray(ys, dtype=np.float64)
    zs_np = np.asarray(zs, dtype=np.float64)
    star_speed_np = np.asarray(star_speed, dtype=np.float64)
    settled = np.full(n, -1.0, dtype=np.float64)
    settled[origin] = 0.0
    v_max = params.probe_speed_pc_per_year
    kd = _build_kdtree(xs, ys, zs)  # dynamic nearest-over-the-unsettled-set index (issue #30)
    state = SwarmState(
        rng=rng, year=0.0, xs=xs_np, ys=ys_np, zs=zs_np, star_speed_pc_yr=star_speed_np,
        settled_year=settled,
        origin=origin, probes={}, next_probe_id=0, total_launched=0, max_speed_pc_yr=v_max,
        box_side_pc=L, periodic=params.periodic,
        settled_count=1, front_radius=0.0,  # origin only; d(origin, origin) = 0 (issue #27)
        kd_root=kd["root"], kd_axis=kd["axis"], kd_split=kd["split"], kd_lo=kd["lo"], kd_hi=kd["hi"],
        kd_parent=kd["parent"], kd_bucket_flat=kd["bucket_flat"], kd_bucket_offsets=kd["bucket_offsets"],
        kd_bxmin=kd["bxmin"], kd_bxmax=kd["bxmax"],
        kd_bymin=kd["bymin"], kd_bymax=kd["bymax"], kd_bzmin=kd["bzmin"], kd_bzmax=kd["bzmax"],
        kd_nuns=kd["nuns"], kd_tsmax=kd["tsmax"], star_leaf=kd["star_leaf"],
    )
    _kd_mark_settled(state, origin)  # origin is settled at year 0; fold its aggregates in
    # Seed probes leave the homeworld at powered cruise, taking the homeworld's slingshot.
    _launch_from(state, origin, params, v_max)
    return state


def _process_arrivals(state: SwarmState, params: SwarmParams, arrivals: list[Probe]) -> None:
    """Settle-or-waste the given arrivals (already sorted by (arrive_year, id)) at ``state.year``.

    Shared by both stepping schemes: a probe arriving at an already-settled star re-targets
    (the cost of stale info); the first to reach an unsettled star settles it and launches
    its offspring. Reads GROUND TRUTH on arrival - what the probe finds, not what it believed.
    """
    # Remove the arriving probes from the live set up front (as the old list rebuild did), so the
    # settlement sweep below never reschedules a probe that is itself arriving this event. Launches
    # and re-targets re-add via _add_probe. O(len(arrivals)), not O(P).
    for p in arrivals:
        state.probes.pop(p.id, None)

    state.total_arrivals += len(arrivals)
    for p in arrivals:
        if state.settled_year[p.target] < 0.0:
            # First to arrive: settle it and spread (slingshot off it, boosting offspring).
            state.settled_year[p.target] = state.year
            _kd_mark_settled(state, p.target)  # remove from the unsettled set (issue #30)
            # Maintain the running count + front radius here (the sole settle site besides the
            # origin), so the per-event snapshot is O(1) instead of an O(N) rescan (issue #27).
            state.settled_count += 1
            d_origin = _dist(state, p.target, state.origin)
            if d_origin > state.front_radius:
                state.front_radius = d_origin
            _on_settled(state, params, p.target)  # inflight: reschedule probes now doomed by this claim
            state.settle_hop_sum_pc += p.hop_len_pc  # winning-trip hop length (read-only)
            state.settle_hop_count += 1
            state.settle_hop_hist[_hop_bin(p.hop_len_pc)] += 1  # won arrivals by hop-length bin
            state.settle_wall_hist[_wall_bin(state, params, p.target)] += 1  # won, by wall-distance bin
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
            state.wasted_wall_hist[_wall_bin(state, params, p.target)] += 1  # wasted, by wall-distance bin
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
                _add_probe(state, params, Probe(
                    id=p.id, target=target, arrive_year=state.year + travel,
                    speed_pc_yr=p.speed_pc_yr, retargets=p.retargets + 1, hop_len_pc=hop,
                    from_x=state.xs[p.target], from_y=state.ys[p.target], from_z=state.zs[p.target],
                    launch_year=state.year,
                ))


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
    """Earliest actionable time over all in-flight probes (arrival or mid-flight learning).

    O(log P) via the event heap (issue #27), replacing the old O(P) min-scan. Bit-identical: the
    heap holds every live probe's actionable time, and stale entries are pruned before the min.
    """
    return _next_valid_event(state, params)


def _process_learns(state: SwarmState, params: SwarmParams, learns: list[Probe]) -> None:
    """Redirect each mid-flight learner at ``state.year`` (inflight only).

    Each learner's target was claimed by another probe; the beacon has now overtaken it. It
    aborts the doomed hop at its current (interpolated) position and re-aims at cruise speed -
    so it never completes the wasted arrival and never brakes at the claimed star. The partial
    distance already flown is charged as redundant travel; NO wasted-rendezvous energy is
    charged (it did not decelerate). Retires if the re-target cap is hit or nothing is believed
    unsettled from here.
    """
    for p in learns:
        state.probes.pop(p.id, None)  # remove the learners up front (as the old list rebuild did)
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
        _add_probe(state, params, Probe(
            id=p.id, target=target, arrive_year=state.year + travel,
            speed_pc_yr=p.speed_pc_yr, retargets=p.retargets + 1, hop_len_pc=hop,
            from_x=px, from_y=py, from_z=pz, launch_year=state.year,
        ))


def _resolve_events(state: SwarmState, params: SwarmParams, cutoff: float) -> None:
    """Process every probe whose actionable time is <= ``cutoff``, at ``state.year == cutoff``.

    Splits them into arrivals (settle-or-waste at a star) and, under inflight, mid-flight
    learns (redirects). Arrivals run first so ground-truth settlements are visible; a probe
    doomed by one of those settlements has ``_learn_year > cutoff`` and is handled next event.
    For "instant"/"lightspeed" there are never any learns, so this is bit-identical to the
    old arrivals-only path.
    """
    _resolve_batch(state, params, _pop_due(state, params, cutoff))


def _resolve_batch(state: SwarmState, params: SwarmParams, batch: list[Probe]) -> None:
    """Split a due batch into arrivals and (inflight) mid-flight learns, sort, and process.

    Classification reads the state BEFORE anything in the batch is processed (as the old scan did),
    so a probe doomed by a settlement within this same batch is still handled as an arrival here and
    picks up its learning time only on the next event. Arrivals run first (ground-truth settlements
    become visible), then learns. Both are sorted by (arrive_year, id), so the outcome does not
    depend on the order the heap popped them.
    """
    arrivals: list[Probe] = []
    learns: list[Probe] = []
    inflight = params.coordination == "inflight"
    for p in batch:
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


@dataclass(frozen=True)
class _InvariantSnapshot:
    """Small pre-step snapshot for the invariant verifier. See REFERENCES.md."""

    year: float
    settled_count: int
    front_radius: float
    total_launched: int
    settled_year: tuple[float, ...]  # tuple copy - immutable, cheap to compare


def _snapshot_invariant_state(state: SwarmState) -> _InvariantSnapshot:
    return _InvariantSnapshot(
        year=state.year,
        settled_count=state.settled_count,
        front_radius=state.front_radius,
        total_launched=state.total_launched,
        settled_year=tuple(state.settled_year),
    )


def _verify_step_invariants(before: _InvariantSnapshot, after: SwarmState) -> None:
    """Assert the documented step invariants on (before-snapshot -> after). See REFERENCES.md.

    Called by `step` / `step_event` under `if __debug__:` and directly by negative tests.
    Raises AssertionError with an [inv:...] tag on the first violation.
    """
    assert after.year >= before.year, (
        f"[inv:sw-year-monotone] year_new={after.year} < year_old={before.year}"
    )
    assert after.settled_count >= before.settled_count, (
        f"[inv:sw-settled-monotone] count_new={after.settled_count} < count_old={before.settled_count}"
    )
    assert after.front_radius >= before.front_radius, (
        f"[inv:sw-front-monotone] front_new={after.front_radius} < front_old={before.front_radius}"
    )
    assert after.total_launched >= before.total_launched, (
        f"[inv:sw-launched-monotone] launched_new={after.total_launched} < old={before.total_launched}"
    )
    # Latch: once settled, never unsettled.
    for i, y_before in enumerate(before.settled_year):
        if y_before >= 0.0:
            assert after.settled_year[i] >= 0.0, (
                f"[inv:sw-settled-latch] star {i}: settled_year {y_before} -> {after.settled_year[i]}"
            )
    # Uniqueness: no Probe.id appears twice among in-flight probes.
    ids = [p.id for p in after.probes.values()]
    assert len(set(ids)) == len(ids), "[inv:sw-probe-ids-unique] duplicate Probe.id in state.probes"


def step(state: SwarmState, params: SwarmParams) -> SwarmState:
    """Advance one FIXED timestep of ``dt_years``. Mutates and returns ``state``.

    Processes every probe that has arrived by the new ``year`` together, in deterministic
    order. Simple and cheap, but if ``dt`` exceeds the hop time it batches many launches into
    one step (they all decide from the same snapshot), which over-synchronizes races and
    inflates the coordination tax - use ``stepping="event"`` in the boosted regime. (inflight
    mid-flight learning is event-exact only under ``stepping="event"``; in fixed mode it is
    resolved at the step boundary, so run the floor bracket in event mode.)
    """
    if __debug__:
        snap = _snapshot_invariant_state(state)
    state.year += params.dt_years
    _resolve_events(state, params, state.year)
    if __debug__:
        _verify_step_invariants(snap, state)
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
    if __debug__:
        snap = _snapshot_invariant_state(state)
    state.year = next_year
    _resolve_events(state, params, next_year)
    if __debug__:
        _verify_step_invariants(snap, state)
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
    # O(1): read the incrementally maintained count + front radius (issue #27), not an O(N) rescan.
    n = s.settled_count
    return SwarmStep(
        year=s.year, n_settled=n, fraction_settled=n / n_stars,
        in_flight=len(s.probes), front_radius_pc=s.front_radius,
    )


def simulate_swarm(
    params: SwarmParams, *, seed: int = 0x9E3779B9, record_steps: bool = True
) -> SwarmResult:
    """Run the settlement front to completion (or ``max_years``) and summarize.

    ``record_steps`` controls only whether the per-event ``SwarmStep`` trace is retained
    (one snapshot per event, ~millions at N=200k in event mode). It is a memory knob, NOT
    a physics knob: every reported number is maintained on incremental ``state`` counters,
    so the aggregates are bit-identical with it on or off. Set it ``False`` for large
    ensembles that only read the summary (the paired/single sweeps in ``experiments/``);
    leave it ``True`` (the default) when a caller walks ``result.steps`` (the concurrency
    sweep, the tests). When ``False`` the trace holds only the initial snapshot.
    """
    state = initial_state(params, seed=seed)
    n_stars = len(state.xs)
    steps = [_snapshot(state, n_stars)]
    # t100 is a fragile tail statistic (the last few stars dominate it); we also record
    # earlier coverage fractions so the penalty can be reported where it is more robust.
    pcts = (25, 50, 75, 90, 99, 100)
    thresholds = {p: None for p in pcts}  # type: dict[int, float | None]

    def record_thresholds() -> None:
        frac = state.settled_count / n_stars * 100.0  # O(1): maintained counter (issue #27)
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
            state.year = ne
            _resolve_batch(state, params, _pop_due(state, params, ne))
            if record_steps:
                steps.append(_snapshot(state, n_stars))
            record_thresholds()
    else:
        n_steps = int(round(params.max_years / params.dt_years))
        for _ in range(n_steps):
            if not state.probes:
                break  # front has stalled or the reachable field is exhausted
            step(state, params)
            if record_steps:
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
        settle_wall_hist=list(state.settle_wall_hist),
        wasted_wall_hist=list(state.wasted_wall_hist),
        steps=steps,
    )
