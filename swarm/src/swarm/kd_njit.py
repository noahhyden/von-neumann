"""The nearest-believed-unsettled k-d tree query, jitted with numba (#27 Part 4).

A numba-compiled version of `sim._nearest_unsettled_at`, called into via a thin
Python wrapper that unpacks `SwarmState` into flat numpy arguments. The jitted
function must reproduce the pure-Python argmin **bit-identically**: same DFS
traversal order, same `(distance^2, lowest-index)` tie-break, same
`settled_year + d/c <= year` gate. Determinism-preserving flags:

    @njit(cache=True, fastmath=False, parallel=False, nogil=False)

fastmath=False forbids float re-association; the distance sum stays `dx*dx +
dy*dy + dz*dz` in that exact order. The DFS stack is a preallocated int32
numpy array with a counter (bit-identical push/pop to the list version).

`_believes_settled_at` is inlined here; the algebra is short (four adds and one
sqrt) and jit inlining costs zero in return performance for the branch it
saves.

Environment override: setting `SWARM_NO_NJIT=1` forces the pure-Python fallback
(`sim._nearest_unsettled_at_python`), useful for debugging and for
environments where numba is unavailable.
"""

from __future__ import annotations

import numpy as np

try:
    from numba import njit
    HAS_NJIT = True
except ImportError:  # numba is a dev-optional dep; downstream consumers (spine, mission)
    HAS_NJIT = False  # fall back to the pure-Python path in sim._nearest_unsettled_at.
    def njit(*args, **kwargs):  # no-op decorator so the def below still compiles
        def _wrap(fn):
            return fn
        return _wrap

from swarm.models import C_PC_PER_YEAR as _C_PC_PER_YEAR


@njit(cache=True, fastmath=False, parallel=False, nogil=False)
def nearest_unsettled_njit(
    px: float,
    py: float,
    pz: float,
    year: float,
    is_instant: bool,
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    settled_year: np.ndarray,
    kd_root: int,
    kd_axis: np.ndarray,
    kd_split: np.ndarray,
    kd_lo: np.ndarray,
    kd_hi: np.ndarray,
    kd_bxmin: np.ndarray,
    kd_bxmax: np.ndarray,
    kd_bymin: np.ndarray,
    kd_bymax: np.ndarray,
    kd_bzmin: np.ndarray,
    kd_bzmax: np.ndarray,
    kd_nuns: np.ndarray,
    kd_tsmax: np.ndarray,
    kd_bucket_flat: np.ndarray,
    kd_bucket_offsets: np.ndarray,
    exclude: np.ndarray,
    n_excludes: int,
) -> int:
    """Return the star index of the nearest believed-unsettled star, or -1 if none.

    Bit-identical to the pure-Python `_nearest_unsettled_at`. `exclude` is a
    small int32 array of length `n_excludes` (typical 0-2, capped by the fleet
    growth cap upstream).
    """
    if kd_root < 0:
        return -1
    c = _C_PC_PER_YEAR
    best = -1
    best_d2 = np.inf
    # Preallocate a stack big enough for a balanced tree of up to ~2^30 nodes.
    # Depth is 2 * log2(n_nodes); 128 is safe for any n we'll ever run.
    stack = np.empty(128, dtype=np.int32)
    stack[0] = kd_root
    sp = 1
    while sp > 0:
        sp -= 1
        node = stack[sp]
        # dlo^2: nearest-point-of-box lower bound.
        dlo2 = 0.0
        t = kd_bxmin[node] - px
        if t > 0.0:
            dlo2 = t * t
        else:
            t = px - kd_bxmax[node]
            if t > 0.0:
                dlo2 = t * t
        t = kd_bymin[node] - py
        if t > 0.0:
            dlo2 += t * t
        else:
            t = py - kd_bymax[node]
            if t > 0.0:
                dlo2 += t * t
        t = kd_bzmin[node] - pz
        if t > 0.0:
            dlo2 += t * t
        else:
            t = pz - kd_bzmax[node]
            if t > 0.0:
                dlo2 += t * t
        if dlo2 > best_d2:
            continue
        if kd_nuns[node] == 0:
            if is_instant:
                continue
            # dhi^2: farthest corner. If tsmax + dhi/c <= year, whole box believed-settled.
            a = px - kd_bxmin[node]
            b = px - kd_bxmax[node]
            a2 = a * a
            b2 = b * b
            dhi2 = a2 if a2 > b2 else b2
            a = py - kd_bymin[node]
            b = py - kd_bymax[node]
            a2 = a * a
            b2 = b * b
            dhi2 += a2 if a2 > b2 else b2
            a = pz - kd_bzmin[node]
            b = pz - kd_bzmax[node]
            a2 = a * a
            b2 = b * b
            dhi2 += a2 if a2 > b2 else b2
            if kd_tsmax[node] + (dhi2 ** 0.5) / c <= year:
                continue
        ax = kd_axis[node]
        if ax == -1:
            # Leaf: scan bucket.
            start = kd_bucket_offsets[node]
            end = kd_bucket_offsets[node + 1]
            for k in range(start, end):
                i = kd_bucket_flat[k]
                # exclude check
                skipped = False
                for j in range(n_excludes):
                    if exclude[j] == i:
                        skipped = True
                        break
                if skipped:
                    continue
                # believes_settled_at gate inlined.
                sy_i = settled_year[i]
                if sy_i >= 0.0:
                    if is_instant:
                        continue
                    dx = xs[i] - px
                    dy = ys[i] - py
                    dz = zs[i] - pz
                    d = (dx * dx + dy * dy + dz * dz) ** 0.5
                    if sy_i + d / c <= year:
                        continue
                # Compute d2 for the tie-break argmin.
                dx = xs[i] - px
                dy = ys[i] - py
                dz = zs[i] - pz
                d2 = dx * dx + dy * dy + dz * dz
                if d2 < best_d2 or (d2 == best_d2 and best >= 0 and i < best):
                    best_d2 = d2
                    best = i
        else:
            # Internal: DFS the nearer child first (pushed last so popped first).
            p_ax = px if ax == 0 else (py if ax == 1 else pz)
            if p_ax < kd_split[node]:
                stack[sp] = kd_hi[node]
                sp += 1
                stack[sp] = kd_lo[node]
                sp += 1
            else:
                stack[sp] = kd_lo[node]
                sp += 1
                stack[sp] = kd_hi[node]
                sp += 1
    return best
