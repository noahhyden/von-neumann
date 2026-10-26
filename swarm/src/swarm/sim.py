"""The deterministic swarm fold - slice 1: a settlement front through a star field."""

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
    """Reflect a coordinate into ``[0, L]`` (triangle wave), preserving the star count and box."""
    if L <= 0.0:
        return 0.0
    period = 2.0 * L
    m = x - period * math.floor(x / period)  # x mod period, in [0, period)
    return m if m <= L else period - m


def _normal_pair(rng: int) -> tuple[float, float, int]:
    """Two independent standard normals from the seeded uniform stream (Box-Muller)."""
    u1, rng = next_float(rng)
    u2, rng = next_float(rng)
    u1 = u1 if u1 > 1e-12 else 1e-12  # guard log(0); deterministic clamp
    r = math.sqrt(-2.0 * math.log(u1))
    return r * math.cos(2.0 * math.pi * u2), r * math.sin(2.0 * math.pi * u2), rng


def _thomas_positions(params: SwarmParams, rng: int) -> tuple[list[float], list[float], list[float], int]:
    """Thomas (Neyman-Scott) cluster process: ``n_clumps`` centres, stars scattered Gaussian around them."""
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
    """Bin star ``star`` by its distance to the nearest box wall, in mean-NN-distance units."""
    L = params.box_side_pc
    x = s.xs[star]
    y = s.ys[star]
    z = s.zs[star]
    wall = min(x, L - x, y, L - y, z, L - z)
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
    """Seeded uniform star field + per-star speeds in a cube of side ``box_side_pc``."""
    L = params.box_side_pc
    if params.n_clumps is not None and int(params.n_clumps) >= 1:
        # Clumpy (Thomas cluster process) field.
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
        # Minimum-image convention on a torus of period L: the shortest separation wraps the box, so there are no boundary stars.
        L = s.box_side_pc
        dx -= L * round(dx / L)
        dy -= L * round(dy / L)
        dz -= L * round(dz / L)
    return (dx * dx + dy * dy + dz * dz) ** 0.5


_KD_LEAF = 8  # max stars per leaf bucket: small enough that a leaf scan is cheap, large enough
#               that the tree stays shallow and Python per-node overhead is amortized.


def _build_kdtree(xs: list[float], ys: list[float], zs: list[float]) -> dict:
    """Balanced k-d tree over the fixed star positions (issue #30), returned as flat SoA arrays."""
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
    """Record that ``star`` just settled, updating the subtree aggregates leaf -> root (O(depth))."""
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
    """Does an observer at point ``(px,py,pz)`` in ``year`` know star ``i`` is settled?"""
    sy = float(s.settled_year[i])  # numpy scalar -> Python float
    if sy < 0.0:
        return False
    if coordination == "instant":
        return True
    dx = s.xs[i] - px  # tuples of Python floats since #27 Part 4 speed-up
    dy = s.ys[i] - py
    dz = s.zs[i] - pz
    d = (dx * dx + dy * dy + dz * dz) ** 0.5
    return sy + d / C_PC_PER_YEAR <= year


def _believes_settled(s: SwarmState, frm: int, i: int, params: SwarmParams) -> bool:
    """Star-based wrapper: the observer sits AT star ``frm`` in ``s.year`` (a decision site)."""
    return _believes_settled_at(s, s.xs[frm], s.ys[frm], s.zs[frm], i, s.year, params.coordination)


# Module-init: pick the nearest-unsettled backend once at import time (issue #33), preferring Rust, then numba, then pure Python (SWARM_NO_RUST / SWARM_NO_NJIT skip a tier).
try:
    from swarm.kd_njit import HAS_NJIT as _HAS_NJIT, nearest_unsettled_njit as _NJIT_KERNEL
except ImportError:
    _HAS_NJIT = False
    _NJIT_KERNEL = None

try:
    import swarm_rust as _swarm_rust  # type: ignore[import-not-found]
    _HAS_RUST = True
    _RUST_KERNEL = _swarm_rust.nearest_unsettled
    # Tier 2: the whole-fill loop (powered, instant/lightspeed/inflight, event stepping); optional and version-guarded against an older crate build.
    _RUST_FILL = getattr(_swarm_rust, "run_fill", None)
    # Tier 3 (issue #38 p2 substrate): the flat p2 kd-tree fill loop, byte-identical to Tier 2 and preferred when n_stars is a power of two >= 8.
    _RUST_FILL_FLAT = getattr(_swarm_rust, "run_fill_flat", None)
    _RUST_BUILD_FLAT = getattr(_swarm_rust, "build_flat_kdtree", None)
except ImportError:
    _HAS_RUST = False
    _RUST_KERNEL = None
    _RUST_FILL = None
    _RUST_FILL_FLAT = None
    _RUST_BUILD_FLAT = None

_USE_RUST = _HAS_RUST and os.environ.get("SWARM_NO_RUST") != "1"
_USE_NJIT = (not _USE_RUST) and _HAS_NJIT and os.environ.get("SWARM_NO_NJIT") != "1"
_USE_FAST = _USE_RUST or _USE_NJIT
_FAST_KERNEL = _RUST_KERNEL if _USE_RUST else _NJIT_KERNEL

_EXCLUDE_SCRATCH = np.zeros(64, dtype=np.int32)  # reused per query to avoid alloc


def _nearest_unsettled_at(
    s: SwarmState, px: float, py: float, pz: float, year: float, coordination: str, exclude: set[int]
) -> int | None:
    """Index of the nearest *believed*-unsettled star to point ``(px,py,pz)`` not in ``exclude``."""
    if _USE_FAST:
        # Pack the exclude set into a small numpy array (typical len 0-2 in the powered policy; capped at max_boost_candidates ~30 upstream).
        n_ex = len(exclude)
        if n_ex > 0:
            if n_ex > _EXCLUDE_SCRATCH.size:
                raise ValueError(f"exclude set too large ({n_ex} > {_EXCLUDE_SCRATCH.size})")
            for j, e in enumerate(exclude):
                _EXCLUDE_SCRATCH[j] = e
        r = _FAST_KERNEL(
            px, py, pz, year, coordination == "instant",
            *s._njit_args,
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
    """The ``k`` nearest *believed*-unsettled stars to a point (deterministic order by (distance, index))."""
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
    """Pick the next star per policy from point ``(px,py,pz)``, reading light-delayed belief."""
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
    """Galactic-frame speed after a slingshot off a star of the given speed."""
    if params.policy == "powered":
        return params.probe_speed_pc_per_year
    u_esc = params.escape_velocity_km_s * KM_S_TO_PC_YR
    u_i = current_pc_yr + star_speed_pc_yr
    dv_max = u_esc * u_esc / (u_esc * u_esc / (2.0 * u_i) + u_i)  # N&F Eq. 4
    return min(current_pc_yr + dv_max, params.speed_cap_c * C_PC_PER_YEAR)


def _launch_from(s: SwarmState, star: int, params: SwarmParams, incoming_speed: float) -> None:
    """Slingshot off ``star`` and launch up to ``offspring`` probes toward new targets."""
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
    """Register a launched / re-targeted probe: live set, event heap, and (inflight) target index."""
    s.probes[p.id] = p
    heapq.heappush(s.ev_heap, (_actionable_year(s, params, p), p.id))
    if params.coordination == "inflight":
        s.by_target.setdefault(p.target, []).append(p.id)


def _on_settled(s: SwarmState, params: SwarmParams, star: int) -> None:
    """Reschedule the probes still heading to a star that was just claimed (inflight decrease-key)."""
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
    """Peek the earliest VALID actionable time on the heap, discarding stale entries (issue #27)."""
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
    """Pop every live probe whose CURRENT actionable time is <= ``cutoff`` (pre-processing state)."""
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
    # Two representations of the fixed star field: tuples for the per-arrival hot Python
    xs_t = tuple(xs)
    ys_t = tuple(ys)
    zs_t = tuple(zs)
    star_speed_t = tuple(star_speed)
    xs_np = np.asarray(xs, dtype=np.float64)
    ys_np = np.asarray(ys, dtype=np.float64)
    zs_np = np.asarray(zs, dtype=np.float64)
    settled = np.full(n, -1.0, dtype=np.float64)
    settled[origin] = 0.0
    v_max = params.probe_speed_pc_per_year
    kd = _build_kdtree(xs, ys, zs)  # dynamic nearest-over-the-unsettled-set index (issue #30)
    state = SwarmState(
        rng=rng, year=0.0, xs=xs_t, ys=ys_t, zs=zs_t, star_speed_pc_yr=star_speed_t,
        settled_year=settled,
        origin=origin, probes={}, next_probe_id=0, total_launched=0, max_speed_pc_yr=v_max,
        box_side_pc=L, periodic=params.periodic,
        settled_count=1, front_radius=0.0,  # origin only; d(origin, origin) = 0 (issue #27)
        xs_np=xs_np, ys_np=ys_np, zs_np=zs_np,
        kd_root=kd["root"], kd_axis=kd["axis"], kd_split=kd["split"], kd_lo=kd["lo"], kd_hi=kd["hi"],
        kd_parent=kd["parent"], kd_bucket_flat=kd["bucket_flat"], kd_bucket_offsets=kd["bucket_offsets"],
        kd_bxmin=kd["bxmin"], kd_bxmax=kd["bxmax"],
        kd_bymin=kd["bymin"], kd_bymax=kd["bymax"], kd_bzmin=kd["bzmin"], kd_bzmax=kd["bzmax"],
        kd_nuns=kd["nuns"], kd_tsmax=kd["tsmax"], star_leaf=kd["star_leaf"],
    )
    # Cache the njit-arg tuple: 1 attribute lookup + tuple unpack per query instead of ~20 attribute chains (issue #27 speed-up on top of Part 4).
    state._njit_args = (
        state.xs_np, state.ys_np, state.zs_np, state.settled_year,
        state.kd_root, state.kd_axis, state.kd_split, state.kd_lo, state.kd_hi,
        state.kd_bxmin, state.kd_bxmax, state.kd_bymin, state.kd_bymax, state.kd_bzmin, state.kd_bzmax,
        state.kd_nuns, state.kd_tsmax,
        state.kd_bucket_flat, state.kd_bucket_offsets,
    )
    _kd_mark_settled(state, origin)  # origin is settled at year 0; fold its aggregates in
    # Seed probes leave the homeworld at powered cruise, taking the homeworld's slingshot.
    _launch_from(state, origin, params, v_max)
    return state


def _process_arrivals(state: SwarmState, params: SwarmParams, arrivals: list[Probe]) -> None:
    """Settle-or-waste the given arrivals (already sorted by (arrive_year, id)) at ``state.year``."""
    # Remove the arriving probes from the live set up front (as the old list rebuild did), so the
    probes = state.probes
    for p in arrivals:
        probes.pop(p.id, None)

    # Hoist per-call constants and state fields so the per-arrival loop makes local lookups instead of attribute chains (issue #27 speed-up; identical semantics).
    state.total_arrivals += len(arrivals)
    xs = state.xs
    ys = state.ys
    zs = state.zs
    settled_year = state.settled_year
    year = state.year
    origin = state.origin
    front_radius = state.front_radius
    settle_hop_hist = state.settle_hop_hist
    settle_wall_hist = state.settle_wall_hist
    wasted_hop_hist = state.wasted_hop_hist
    wasted_wall_hist = state.wasted_wall_hist
    wasted_s_hist = state.wasted_s_hist
    hop_edges = HOP_BIN_EDGES
    wall_edges = WALL_BIN_EDGES_NN
    box_side = params.box_side_pc
    d_nn = 0.55396 * params.density_stars_per_pc3 ** (-1.0 / 3.0)
    inv_d_nn = 1.0 / d_nn if d_nn > 0.0 else 0.0
    max_retargets = params.max_retargets
    periodic = state.periodic

    for p in arrivals:
        target = p.target
        hop_len = p.hop_len_pc
        v = p.speed_pc_yr
        # Inline hop_bin (was a per-arrival function call).
        hb = 0
        for e in hop_edges:
            if hop_len >= e:
                hb += 1
            else:
                break
        # Inline wall_bin.
        x = xs[target]; y = ys[target]; z = zs[target]
        wall = x if x < box_side - x else box_side - x
        yy = y if y < box_side - y else box_side - y
        if yy < wall:
            wall = yy
        zz = z if z < box_side - z else box_side - z
        if zz < wall:
            wall = zz
        r = wall * inv_d_nn
        wb = 0
        for e in wall_edges:
            if r >= e:
                wb += 1
            else:
                break

        if settled_year[target] < 0.0:
            # First to arrive: settle it and spread (slingshot off it, boosting offspring).
            settled_year[target] = year
            _kd_mark_settled(state, target)  # remove from the unsettled set (issue #30)
            # Maintain the running count + front radius here (the sole settle site besides the
            state.settled_count += 1
            # Inline _dist to origin (no periodic wrap for origin distance is used elsewhere; keep periodic handling for correctness).
            dx = x - xs[origin]
            dy = y - ys[origin]
            dz = z - zs[origin]
            if periodic:
                dx -= box_side * round(dx / box_side)
                dy -= box_side * round(dy / box_side)
                dz -= box_side * round(dz / box_side)
            d_origin = (dx * dx + dy * dy + dz * dz) ** 0.5
            if d_origin > front_radius:
                front_radius = d_origin
                state.front_radius = d_origin
            _on_settled(state, params, target)  # inflight: reschedule probes now doomed by this claim
            state.settle_hop_sum_pc += hop_len
            state.settle_hop_count += 1
            settle_hop_hist[hb] += 1
            settle_wall_hist[wb] += 1
            state.settle_v_sum_pc_yr += v
            state.settle_v2_sum += v * v
            _launch_from(state, target, params, v)
        else:
            # Raced and lost: a wasted trip (the cost of stale info).
            state.wasted_arrivals += 1
            state.wasted_hop_sum_pc += hop_len
            state.wasted_hop_count += 1
            wasted_hop_hist[hb] += 1
            wasted_wall_hist[wb] += 1
            state.wasted_travel_pc += hop_len
            state.wasted_v_sum_pc_yr += v
            state.wasted_v2_sum += v * v
            # Normalized claim margin: s = (settled_year[target] - launch) / (arrive - launch).
            _span = p.arrive_year - p.launch_year
            if _span > 0.0:
                _s = (settled_year[target] - p.launch_year) / _span
                if _s < 0.0:
                    _sb = 0
                elif _s >= 1.0:
                    _sb = 31
                else:
                    _sb = int(_s * 32.0)
                wasted_s_hist[_sb] += 1
            # Retire a probe after too many lost races (a bounce-chain bound, bookkeeping not physics, applied to instant and lightspeed alike).
            if p.retargets >= max_retargets:
                continue  # bounce chain exhausted → retire the probe as wasted
            new_target = _select_target(state, target, set(), params)
            if new_target is not None:
                state.retarget_count += 1
                hop = _dist(state, target, new_target)
                travel = hop / v
                # In-place reuse: this probe was already popped from state.probes (top of
                p.target = new_target
                p.arrive_year = year + travel
                p.speed_pc_yr = v
                p.retargets = p.retargets + 1
                p.hop_len_pc = hop
                p.from_x = x
                p.from_y = y
                p.from_z = z
                p.launch_year = year
                _add_probe(state, params, p)


def _learn_year(p: Probe, settled_year: list[float]) -> float:
    """Year the beacon from ``p``'s (already-settled) target overtakes ``p`` in flight."""
    v_over_c = p.speed_pc_yr / C_PC_PER_YEAR
    return (settled_year[p.target] + v_over_c * p.arrive_year) / (1.0 + v_over_c)


def _is_doomed(state: SwarmState, p: Probe) -> bool:
    """``p``'s target has been claimed by another probe (ground truth), so ``p`` will waste."""
    return state.settled_year[p.target] >= 0.0


def _actionable_year(state: SwarmState, params: SwarmParams, p: Probe) -> float:
    """When ``p`` next acts: its mid-flight learning time if doomed under inflight, else arrival."""
    if params.coordination == "inflight" and _is_doomed(state, p):
        tl = _learn_year(p, state.settled_year)
        if tl < p.arrive_year:
            return tl
    return p.arrive_year


def _next_event_year(state: SwarmState, params: SwarmParams) -> float | None:
    """Earliest actionable time over all in-flight probes (arrival or mid-flight learning)."""
    return _next_valid_event(state, params)


def _process_learns(state: SwarmState, params: SwarmParams, learns: list[Probe]) -> None:
    """Redirect each mid-flight learner at ``state.year`` (inflight only)."""
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
        # In-place reuse (as in _process_arrivals): the learner was popped up top and its old
        p.target = target
        p.arrive_year = state.year + travel
        p.retargets = p.retargets + 1
        p.hop_len_pc = hop
        p.from_x = px
        p.from_y = py
        p.from_z = pz
        p.launch_year = state.year
        _add_probe(state, params, p)


def _resolve_events(state: SwarmState, params: SwarmParams, cutoff: float) -> None:
    """Process every probe whose actionable time is <= ``cutoff``, at ``state.year == cutoff``."""
    _resolve_batch(state, params, _pop_due(state, params, cutoff))


def _resolve_batch(state: SwarmState, params: SwarmParams, batch: list[Probe]) -> None:
    """Split a due batch into arrivals and (inflight) mid-flight learns, sort, and process."""
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
    """Assert the documented step invariants on (before-snapshot -> after)."""
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
    """Advance one FIXED timestep of ``dt_years``."""
    if __debug__:
        snap = _snapshot_invariant_state(state)
    state.year += params.dt_years
    _resolve_events(state, params, state.year)
    if __debug__:
        _verify_step_invariants(snap, state)
    return state


def step_event(state: SwarmState, params: SwarmParams) -> SwarmState:
    """Advance to the NEXT event (arrival, or inflight mid-flight learning)."""
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


def _rust_fill_supported(params: SwarmParams) -> bool:
    """Whether the Rust whole-fill loop (Tier 2) covers this config."""
    return (
        _RUST_FILL is not None
        and os.environ.get("SWARM_NO_RUST") != "1"
        and os.environ.get("SWARM_NO_RUST_FILL") != "1"
        and params.policy == "powered"
        and params.coordination in ("instant", "lightspeed", "inflight")
        and params.stepping == "event"
    )


def _is_power_of_two(n: int) -> bool:
    """True when ``n`` is a power of two (and > 0). Matches the Rust ``is_power_of_two`` gate."""
    return n > 0 and (n & (n - 1)) == 0


def _use_flat_fill(n: int) -> bool:
    """Prefer the flat p2 kd-tree fill (issue #38) at n_stars = 2^k >= 8, when built."""
    return (
        _RUST_FILL_FLAT is not None
        and _RUST_BUILD_FLAT is not None
        and os.environ.get("SWARM_NO_RUST_FLAT") != "1"
        and n >= 8
        and _is_power_of_two(n)
    )


def _simulate_swarm_rust(
    params: SwarmParams, *, seed: int = 0x9E3779B9, record_steps: bool = True
) -> SwarmResult:
    """Rust-accelerated fill for the supported config; bit-identical to the Python fold."""
    xs, ys, zs, star_speed, _rng = _generate_galaxy(params, seed_state(seed))
    n = len(xs)
    L = params.box_side_pc
    cx = cy = cz = L / 2.0
    origin = min(range(n), key=lambda i: (xs[i] - cx) ** 2 + (ys[i] - cy) ** 2 + (zs[i] - cz) ** 2)
    d_nn = 0.55396 * params.density_stars_per_pc3 ** (-1.0 / 3.0)
    inv_d_nn = 1.0 / d_nn if d_nn > 0.0 else 0.0
    xs_np = np.asarray(xs, dtype=np.float64)
    ys_np = np.asarray(ys, dtype=np.float64)
    zs_np = np.asarray(zs, dtype=np.float64)
    hop_edges = np.asarray(HOP_BIN_EDGES, dtype=np.float64)
    wall_edges = np.asarray(WALL_BIN_EDGES_NN, dtype=np.float64)
    if _use_flat_fill(n):
        flat = _RUST_BUILD_FLAT(xs_np, ys_np, zs_np)  # Rust build; returns numpy views
        d = _RUST_FILL_FLAT(
            xs_np, ys_np, zs_np, origin,
            flat["xs_p"], flat["ys_p"], flat["zs_p"], flat["star_perm"], flat["star_perm_inv"],
            flat["axis"], flat["split"],
            flat["bxmin"], flat["bxmax"], flat["bymin"], flat["bymax"], flat["bzmin"], flat["bzmax"],
            flat["nuns"], flat["tsmax"],
            params.coordination == "instant", params.coordination == "inflight", L, params.periodic,
            params.probe_speed_pc_per_year, params.offspring_per_settlement,
            params.settle_time_years, params.max_years, params.max_retargets, inv_d_nn,
            hop_edges, wall_edges,
        )
    else:
        kd = _build_kdtree(xs, ys, zs)  # fresh (nuns = subtree sizes, tsmax = -1); Rust marks origin
        d = _RUST_FILL(
            xs_np, ys_np, zs_np, origin,
            kd["root"], kd["axis"], kd["split"], kd["lo"], kd["hi"], kd["parent"],
            kd["bxmin"], kd["bxmax"], kd["bymin"], kd["bymax"], kd["bzmin"], kd["bzmax"],
            kd["nuns"], kd["tsmax"], kd["star_leaf"], kd["bucket_flat"], kd["bucket_offsets"],
            params.coordination == "instant", params.coordination == "inflight", L, params.periodic,
            params.probe_speed_pc_per_year, params.offspring_per_settlement,
            params.settle_time_years, params.max_years, params.max_retargets, inv_d_nn,
            hop_edges, wall_edges,
        )
    # Single initial snapshot (matches the Python record_steps=False trace: one entry).
    steps = [SwarmStep(year=0.0, n_settled=1, fraction_settled=1 / n,
                       in_flight=d["initial_in_flight"], front_radius_pc=0.0)]
    c2 = C_PC_PER_YEAR * C_PC_PER_YEAR
    return SwarmResult(
        n_stars=n,
        final_settled=d["final_settled"],
        total_probes_launched=d["total_launched"],
        t50_years=d["t50"], t90_years=d["t90"], t100_years=d["t100"],
        t25_years=d["t25"], t75_years=d["t75"], t99_years=d["t99"],
        front_radius_pc=d["front_radius_pc"],
        max_probe_speed_km_s=d["max_speed_pc_yr"] / KM_S_TO_PC_YR,
        policy=params.policy, coordination=params.coordination,
        total_arrivals=d["total_arrivals"], wasted_arrivals=d["wasted_arrivals"],
        retarget_count=d["retarget_count"], wasted_travel_pc=d["wasted_travel_pc"],
        midflight_aborts=d["midflight_aborts"],  # nonzero only under inflight mid-flight relay
        mean_launch_speed_km_s=(
            d["launch_speed_sum_pc_yr"] / d["launch_count"] / KM_S_TO_PC_YR
            if d["launch_count"] else 0.0
        ),
        mean_settle_hop_pc=(
            d["settle_hop_sum_pc"] / d["settle_hop_count"] if d["settle_hop_count"] else 0.0
        ),
        mean_wasted_hop_pc=(
            d["wasted_hop_sum_pc"] / d["wasted_hop_count"] if d["wasted_hop_count"] else 0.0
        ),
        settle_energy_c2=0.5 * d["settle_v2_sum"] / c2,
        wasted_energy_c2=0.5 * d["wasted_v2_sum"] / c2,
        mean_settle_speed_km_s=(
            d["settle_v_sum_pc_yr"] / d["settle_hop_count"] / KM_S_TO_PC_YR
            if d["settle_hop_count"] else 0.0
        ),
        mean_wasted_speed_km_s=(
            d["wasted_v_sum_pc_yr"] / d["wasted_hop_count"] / KM_S_TO_PC_YR
            if d["wasted_hop_count"] else 0.0
        ),
        settle_hop_hist=list(d["settle_hop_hist"]),
        wasted_hop_hist=list(d["wasted_hop_hist"]),
        settle_wall_hist=list(d["settle_wall_hist"]),
        wasted_wall_hist=list(d["wasted_wall_hist"]),
        wasted_s_hist=list(d["wasted_s_hist"]),
        steps=steps,
    )


def simulate_swarm(
    params: SwarmParams, *, seed: int = 0x9E3779B9, record_steps: bool = True
) -> SwarmResult:
    """Run the settlement front and summarize; routes to the Rust fast path when it applies."""
    # The fast path returns only the single initial snapshot, so a caller that walks the full per-event trace (record_steps=True) must use the Python fold.
    if not record_steps and _rust_fill_supported(params):
        return _simulate_swarm_rust(params, seed=seed, record_steps=record_steps)
    return _simulate_swarm_python(params, seed=seed, record_steps=record_steps)


def _simulate_swarm_python(
    params: SwarmParams, *, seed: int = 0x9E3779B9, record_steps: bool = True
) -> SwarmResult:
    """Run the settlement front to completion (or ``max_years``) and summarize."""
    state = initial_state(params, seed=seed)
    n_stars = len(state.xs)
    steps = [_snapshot(state, n_stars)]
    # t100 is a fragile tail statistic (the last few stars dominate it); we also record
    pcts = (25, 50, 75, 90, 99, 100)
    thresholds = {p: None for p in pcts}  # type: dict[int, float | None]

    def record_thresholds() -> None:
        frac = state.settled_count / n_stars * 100.0  # O(1): maintained counter (issue #27)
        for pct in pcts:
            if thresholds[pct] is None and frac >= pct:
                thresholds[pct] = state.year

    record_thresholds()
    if params.stepping == "event":
        # Event-driven: one step per event, jumping to the next event; dt-independent.
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
        wasted_s_hist=list(state.wasted_s_hist),
        steps=steps,
    )
