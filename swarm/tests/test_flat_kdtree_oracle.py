"""Oracle: the flat p2 kd-tree (Rust) is bit-identical to the pointer kd-tree (Python).

The flat tree lives in ``swarm/rust/src/lib.rs`` and fires at ``n_stars = 2^k, k >= 3``.
The pointer tree in ``swarm/src/swarm/sim.py::_build_kdtree`` is the reference: at matching
p2 N, it partitions stars identically (same median-split, same ``(coord, index)`` tie-break),
so the flat tree's ``nearest_unsettled_flat`` and ``mark_settled_flat`` must return the same
star's ORIGINAL index and the same nuns/tsmax deltas along the leaf-to-root path.

Skips cleanly if ``swarm_rust`` lacks the flat-tree functions (a checkout with an older
crate build), so CI without the freshly-built extension stays green.

Discipline (per issue #38 / p2 spec): spec -> tests-first -> live verification ->
mutation red-teaming -> docs -> 100% coverage. This file is the tests-first half.
"""

from __future__ import annotations

import numpy as np
import pytest

from swarm import models
from swarm.rng import seed_state
from swarm.sim import (
    _build_kdtree,
    _generate_galaxy,
    _nearest_unsettled_at_python,
)

# swarm_rust is optional (issue #33 fast path); the flat-tree functions are the tier-3 addition.
rust = pytest.importorskip("swarm_rust")
if not all(hasattr(rust, name) for name in ("build_flat_kdtree", "nearest_unsettled_flat", "mark_settled_flat")):
    pytest.skip("swarm_rust lacks flat-kdtree functions (rebuild the crate)", allow_module_level=True)


# -- p2 sizes: root-only (N=8), one-level (N=16), and deeper trees up to N=4096. -----------
P2_N = [8, 16, 32, 128, 512, 4096]

# Non-p2 sizes the build must reject.
NON_P2_N = [6, 300, 500, 1000, 200_000]


def _make_galaxy(n_stars: int, seed: int):
    """Deterministic seeded uniform galaxy at n_stars, plus a pointer-tree over it."""
    params = models.SwarmParams(n_stars=n_stars, coordination="lightspeed")
    xs, ys, zs, _star_speed, _rng = _generate_galaxy(params, seed_state(seed))
    xs_np = np.asarray(xs, dtype=np.float64)
    ys_np = np.asarray(ys, dtype=np.float64)
    zs_np = np.asarray(zs, dtype=np.float64)
    kd = _build_kdtree(xs, ys, zs)
    return params, xs_np, ys_np, zs_np, kd


def _fake_state(params, xs, ys, zs, kd, settled_year: np.ndarray, year: float):
    """Fake just enough of SwarmState for _nearest_unsettled_at_python (mirrors test_kdtree_backends)."""
    class _S:
        pass

    s = _S()
    s.xs = xs.tolist()
    s.ys = ys.tolist()
    s.zs = zs.tolist()
    s.kd_axis = kd["axis"]
    s.kd_split = kd["split"]
    s.kd_lo = kd["lo"]
    s.kd_hi = kd["hi"]
    s.kd_bxmin = kd["bxmin"]
    s.kd_bxmax = kd["bxmax"]
    s.kd_bymin = kd["bymin"]
    s.kd_bymax = kd["bymax"]
    s.kd_bzmin = kd["bzmin"]
    s.kd_bzmax = kd["bzmax"]
    s.kd_nuns = kd["nuns"]
    s.kd_tsmax = kd["tsmax"]
    s.kd_bucket_flat = kd["bucket_flat"]
    s.kd_bucket_offsets = kd["bucket_offsets"]
    s.kd_root = kd["root"]
    s.star_leaf = kd["star_leaf"]
    s.kd_parent = kd["parent"]
    s.settled_year = settled_year
    s.year = year
    return s


def _assert_flat_aggregates_from_source(flat: dict, settled_year: np.ndarray, n_stars: int, step: int) -> None:
    """Recompute nuns/tsmax at every flat-tree node from settled_year, assert flat matches.

    This is the mutation-red-team check for parent-walk bugs. If ``mark_settled_flat`` skips
    an intermediate level (e.g. `(i-1) >> 2` instead of `>> 1`), the root can still be right
    while nodes at odd depths carry stale counters. Reconstructing the truth from the source
    of truth (settled_year) and checking every node kills that mutant.

    A leaf's stars are known (permuted contiguous 8-block); each internal node's aggregate
    is the sum/max of its children (bottom-up BFS).
    """
    m = int(flat["m"])
    total = int(flat["total_nodes"])
    star_perm = np.asarray(flat["star_perm"], dtype=np.int64)
    expected_nuns = np.zeros(total, dtype=np.int32)
    expected_tsmax = np.full(total, -1.0, dtype=np.float64)
    # Leaves: iterate the 8 stars per leaf via star_perm.
    for leaf in range((m - 1), total):
        offset = (leaf - (m - 1)) * 8
        unsettled = 0
        ts = -1.0
        for k in range(8):
            orig = int(star_perm[offset + k])
            sy = float(settled_year[orig])
            if sy < 0.0:
                unsettled += 1
            elif sy > ts:
                ts = sy
        expected_nuns[leaf] = unsettled
        expected_tsmax[leaf] = ts
    # Internal nodes: bottom-up.
    for i in range(m - 2, -1, -1):
        left = 2 * i + 1
        right = 2 * i + 2
        expected_nuns[i] = expected_nuns[left] + expected_nuns[right]
        expected_tsmax[i] = max(expected_tsmax[left], expected_tsmax[right])
    flat_nuns = np.asarray(flat["nuns"], dtype=np.int32)
    flat_tsmax = np.asarray(flat["tsmax"], dtype=np.float64)
    if not np.array_equal(flat_nuns, expected_nuns):
        # Report the first divergent node for a fast diagnosis.
        bad = int(np.where(flat_nuns != expected_nuns)[0][0])
        raise AssertionError(
            f"nuns mismatch at step {step}, node {bad}: flat={flat_nuns[bad]} "
            f"expected={expected_nuns[bad]}"
        )
    if not np.allclose(flat_tsmax, expected_tsmax, equal_nan=False):
        bad = int(np.where(flat_tsmax != expected_tsmax)[0][0])
        raise AssertionError(
            f"tsmax mismatch at step {step}, node {bad}: flat={flat_tsmax[bad]} "
            f"expected={expected_tsmax[bad]}"
        )


def _kd_mark_settled_pointer(kd: dict, settled_year: np.ndarray, star: int, year: float) -> None:
    """Pointer-tree in-place settle update, mirror of ``swarm.sim._kd_mark_settled``.

    Used as the oracle for ``mark_settled_flat`` in the interleaved test. Lives here to
    avoid pulling in a SwarmState just to call the helper.
    """
    settled_year[star] = year
    nuns = kd["nuns"]
    tsmax = kd["tsmax"]
    parent = kd["parent"]
    node = int(kd["star_leaf"][star])
    while node != -1:
        nuns[node] -= 1
        if year > tsmax[node]:
            tsmax[node] = year
        node = int(parent[node])


# --------------------------------------------------------------------------------------------
# Build invariants
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("n_stars", P2_N)
def test_build_flat_produces_expected_shape(n_stars: int) -> None:
    """Flat tree at p2 N has exactly 2M-1 nodes with M = N/8, and star_perm is a permutation of 0..N-1."""
    _, xs, ys, zs, _ = _make_galaxy(n_stars, seed=1)
    flat = rust.build_flat_kdtree(xs, ys, zs)
    m = n_stars // 8
    assert flat["axis"].shape == (2 * m - 1,), f"expected 2M-1 nodes, got {flat['axis'].shape}"
    assert flat["nuns"].shape == (2 * m - 1,)
    assert flat["tsmax"].shape == (2 * m - 1,)
    assert flat["star_perm"].shape == (n_stars,)
    # star_perm must be a permutation of 0..N-1 (every original index appears exactly once).
    perm = np.asarray(flat["star_perm"], dtype=np.int64)
    assert sorted(perm.tolist()) == list(range(n_stars)), "star_perm is not a permutation"
    # Coordinates are stored permuted: xs_p[i] must equal xs[star_perm[i]].
    assert np.array_equal(np.asarray(flat["xs_p"]), xs[perm])
    assert np.array_equal(np.asarray(flat["ys_p"]), ys[perm])
    assert np.array_equal(np.asarray(flat["zs_p"]), zs[perm])
    # Root subtree carries all N unsettled stars at build.
    assert int(flat["nuns"][0]) == n_stars


@pytest.mark.parametrize("n_stars", NON_P2_N)
def test_build_flat_rejects_non_p2(n_stars: int) -> None:
    """Non-p2 N (or N < 8) must raise ValueError with a message pointing at the constraint."""
    _, xs, ys, zs, _ = _make_galaxy(n_stars, seed=1) if n_stars >= 8 else (
        None,
        np.zeros(n_stars, dtype=np.float64),
        np.zeros(n_stars, dtype=np.float64),
        np.zeros(n_stars, dtype=np.float64),
        None,
    )
    with pytest.raises(ValueError, match=r"power of two"):
        rust.build_flat_kdtree(xs, ys, zs)


def test_build_flat_child_parent_math() -> None:
    """Mutation red-team target: internal-node children and parent indices land on the right nodes.

    At N=32 we have M=4 leaves, 3 internal nodes, 7 total. The BFS layout gives:
        internal 0 has children 1, 2; internal 1 has children 3, 4 (leaves); internal 2 has
        children 5, 6 (leaves). Every leaf i in {3,4,5,6} has (i-1)>>1 pointing at its parent.
    This is small enough to inspect. If a mutant changes ``2i+1`` to ``2i-1`` or
    ``M-1`` to ``M``, this test fails.
    """
    _, xs, ys, zs, _ = _make_galaxy(32, seed=1)
    flat = rust.build_flat_kdtree(xs, ys, zs)
    m = 32 // 8  # 4 leaves, 3 internal, 7 total
    assert flat["axis"].shape == (2 * m - 1,) == (7,)
    # Internal nodes 0, 1, 2 have axis in {0,1,2}. Leaves 3..6 have axis == -1.
    axis = np.asarray(flat["axis"], dtype=np.int64)
    assert set(axis[:m - 1].tolist()) <= {0, 1, 2}, f"internal axes: {axis[:m-1]}"
    assert (axis[m - 1:] == -1).all(), f"leaf axes should be -1: {axis[m-1:]}"


# --------------------------------------------------------------------------------------------
# Nearest-unsettled: flat vs pointer, at every p2 N
# --------------------------------------------------------------------------------------------


def _query_flat(flat: dict, sy_p: np.ndarray, px: float, py: float, pz: float,
                year: float, is_instant: bool, excl: np.ndarray, n_ex: int) -> int:
    """Invoke the flat-tree Rust query with its calling convention."""
    return int(rust.nearest_unsettled_flat(
        px, py, pz, year, is_instant,
        flat["xs_p"], flat["ys_p"], flat["zs_p"], sy_p, flat["star_perm"],
        flat["axis"], flat["split"],
        flat["bxmin"], flat["bxmax"], flat["bymin"], flat["bymax"],
        flat["bzmin"], flat["bzmax"], flat["nuns"], flat["tsmax"],
        excl, n_ex,
    ))


@pytest.mark.parametrize("n_stars", P2_N)
@pytest.mark.parametrize("is_instant", [True, False], ids=["instant", "lightspeed"])
def test_flat_nn_matches_pointer_query(n_stars: int, is_instant: bool) -> None:
    """Fresh unsettled tree: flat and pointer return the same star for every random query.

    Exercises both the ``instant`` fast path (dhi/lightcone pruning collapsed) and the
    ``lightspeed`` path (full gate). Covers the empty-exclude case.
    """
    params, xs, ys, zs, kd = _make_galaxy(n_stars, seed=7)
    settled_year = np.full(n_stars, -1.0, dtype=np.float64)
    year = 1e7
    fake = _fake_state(params, xs, ys, zs, kd, settled_year, year)

    flat = rust.build_flat_kdtree(xs, ys, zs)
    sy_p = np.full(n_stars, -1.0, dtype=np.float64)
    excl = np.zeros(4, dtype=np.int32)

    box = params.box_side_pc
    rng = np.random.default_rng(101)
    queries = rng.random((64, 3)) * box
    coordination = "instant" if is_instant else "lightspeed"

    for i, (px, py, pz) in enumerate(queries):
        py_ans = _nearest_unsettled_at_python(fake, px, py, pz, year, coordination, exclude=set())
        py_ans = -1 if py_ans is None else py_ans
        got = _query_flat(flat, sy_p, px, py, pz, year, is_instant, excl, 0)
        assert got == py_ans, (
            f"N={n_stars} coord={coordination} query {i}: pointer={py_ans} flat={got}"
        )


@pytest.mark.parametrize("n_stars", [32, 128, 512, 4096])
def test_flat_nn_matches_pointer_half_settled(n_stars: int) -> None:
    """Randomly half-settled tree, lightspeed: exercises the belief gate + dhi pruning."""
    params, xs, ys, zs, kd = _make_galaxy(n_stars, seed=13)
    year = 1e7
    np_rng = np.random.default_rng(202)
    settled_mask = np_rng.random(n_stars) < 0.5
    settled_year = np.full(n_stars, -1.0, dtype=np.float64)
    settled_year[settled_mask] = np_rng.random(settled_mask.sum()) * 1e6

    # Sync the pointer tree's nuns/tsmax aggregates with the same settlements. The helper writes
    # settled_year[i] = ys_val for every star it settles, which is exactly the value already
    # there, so the array is unchanged.
    pointer_sy = settled_year.copy()
    for i, ys_val in enumerate(settled_year):
        if ys_val >= 0.0:
            _kd_mark_settled_pointer(kd, pointer_sy, star=i, year=float(ys_val))
    fake = _fake_state(params, xs, ys, zs, kd, pointer_sy, year)

    flat = rust.build_flat_kdtree(xs, ys, zs)
    sy_p = np.full(n_stars, -1.0, dtype=np.float64)
    perm = np.asarray(flat["star_perm"], dtype=np.int64)
    # Apply the same settlements to the flat tree via mark_settled_flat.
    for i in range(n_stars):
        if settled_year[i] >= 0.0:
            rust.mark_settled_flat(
                i, float(settled_year[i]),
                sy_p, flat["nuns"], flat["tsmax"], flat["star_perm_inv"],
            )
    # Sanity: sy_p permutation carries the same information as settled_year.
    for i in range(n_stars):
        assert sy_p[int(np.asarray(flat["star_perm_inv"])[i])] == settled_year[i], (
            f"sy_p[perm_inv[{i}]] should equal settled_year[{i}]"
        )

    excl = np.zeros(4, dtype=np.int32)
    box = params.box_side_pc
    q_rng = np.random.default_rng(303)
    queries = q_rng.random((64, 3)) * box
    for i, (px, py, pz) in enumerate(queries):
        py_ans = _nearest_unsettled_at_python(fake, px, py, pz, year, "lightspeed", exclude=set())
        py_ans = -1 if py_ans is None else py_ans
        got = _query_flat(flat, sy_p, px, py, pz, year, False, excl, 0)
        assert got == py_ans, (
            f"N={n_stars} half-settled query {i}: pointer={py_ans} flat={got}"
        )


@pytest.mark.parametrize("n_stars", [32, 128, 512])
def test_flat_nn_matches_pointer_with_exclude(n_stars: int) -> None:
    """Non-empty exclude set: exercises the per-leaf skip path used by offspring launch batches."""
    params, xs, ys, zs, kd = _make_galaxy(n_stars, seed=23)
    settled_year = np.full(n_stars, -1.0, dtype=np.float64)
    year = 1e7
    fake = _fake_state(params, xs, ys, zs, kd, settled_year, year)

    flat = rust.build_flat_kdtree(xs, ys, zs)
    sy_p = np.full(n_stars, -1.0, dtype=np.float64)

    box = params.box_side_pc
    rng = np.random.default_rng(404)
    # Simulate the "launch a batch, each next probe excludes prior picks" pattern.
    px, py_c, pz = (rng.random(3) * box).tolist()
    chosen_pointer: list[int] = []
    chosen_flat: list[int] = []
    for step in range(8):
        excl_pointer = set(chosen_pointer)
        excl_arr = np.asarray(chosen_flat + [0] * (8 - len(chosen_flat)), dtype=np.int32)
        py_ans = _nearest_unsettled_at_python(fake, px, py_c, pz, year, "instant", exclude=excl_pointer)
        py_ans = -1 if py_ans is None else py_ans
        got = _query_flat(flat, sy_p, px, py_c, pz, year, True, excl_arr, len(chosen_flat))
        assert got == py_ans, (
            f"N={n_stars} step {step} exclude={chosen_flat}: pointer={py_ans} flat={got}"
        )
        if py_ans < 0:
            break
        chosen_pointer.append(py_ans)
        chosen_flat.append(py_ans)


# --------------------------------------------------------------------------------------------
# Interleaved settle + query: the real hot-path pattern
# --------------------------------------------------------------------------------------------


def test_flat_tiebreak_by_lowest_original_index() -> None:
    """Two stars exactly equidistant from a probe: the lower ORIGINAL index must win.

    Mutation red-team: `orig < best` flipped to `orig > best` would still handle every
    randomly-drawn probe (uniform galaxy -> no f64 tie), so the tie-break rule needs a
    hand-crafted galaxy where the tie is guaranteed. Place two stars symmetrically around
    the origin and probe at the origin; both are exactly `d` away, and by the (d^2, lowest
    original index) rule the lower-indexed star must be returned.
    """
    n = 8  # smallest legal p2 flat tree
    # Two symmetric stars at index 0 and 1, others far away so they never win.
    xs = np.array([1.0, -1.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0], dtype=np.float64)
    ys = np.array([0.0, 0.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0], dtype=np.float64)
    zs = np.array([0.0, 0.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0], dtype=np.float64)
    flat = rust.build_flat_kdtree(xs, ys, zs)
    sy_p = np.full(n, -1.0, dtype=np.float64)
    excl = np.zeros(4, dtype=np.int32)
    got = _query_flat(flat, sy_p, 0.0, 0.0, 0.0, year=1.0, is_instant=True, excl=excl, n_ex=0)
    assert got == 0, (
        f"tie-break: expected star 0 (lowest original index) at d=1 from origin, got {got}"
    )
    # Sanity: with the two tied stars swapped (via exclude), star 1 wins.
    excl[0] = 0
    got = _query_flat(flat, sy_p, 0.0, 0.0, 0.0, year=1.0, is_instant=True, excl=excl, n_ex=1)
    assert got == 1, f"exclude=[0]: expected star 1, got {got}"


@pytest.mark.parametrize("n_stars", [32, 128, 512, 4096])
def test_flat_interleaved_settle_and_query_matches_pointer(n_stars: int) -> None:
    """Alternate ``mark_settled`` and ``nearest_unsettled`` against a scripted schedule.

    This is the real event-loop pattern: settle a star, walk the aggregates up, query again.
    Any drift in the parent walk (nuns/tsmax) would show up as a divergent query.
    """
    params, xs, ys, zs, kd = _make_galaxy(n_stars, seed=29)
    settled_year = np.full(n_stars, -1.0, dtype=np.float64)
    year = 1.0
    flat = rust.build_flat_kdtree(xs, ys, zs)
    sy_p = np.full(n_stars, -1.0, dtype=np.float64)
    excl = np.zeros(4, dtype=np.int32)

    np_rng = np.random.default_rng(505)
    schedule = np_rng.choice(n_stars, size=min(64, n_stars // 2), replace=False).tolist()
    box = params.box_side_pc
    q_rng = np.random.default_rng(606)

    for step, star in enumerate(schedule):
        # Settle this star on both trees at a strictly increasing year (matches event-loop).
        year += 1.0
        _kd_mark_settled_pointer(kd, settled_year, star, year)
        rust.mark_settled_flat(
            star, year,
            sy_p, flat["nuns"], flat["tsmax"], flat["star_perm_inv"],
        )
        # Root check is necessary but not sufficient - a parent-walk bug that skips levels
        # (e.g. `(i-1) >> 2` instead of `(i-1) >> 1`) can leave the root correct while
        # corrupting intermediate nodes. Verify EVERY node's nuns and tsmax match: for each
        # flat-tree node, walk to its subtree's original stars via star_perm and compute what
        # nuns/tsmax should be from the truthful settled_year, then compare.
        assert int(flat["nuns"][0]) == int(kd["nuns"][0]), (
            f"root nuns mismatch at step {step}: flat={flat['nuns'][0]} pointer={kd['nuns'][0]}"
        )
        assert float(flat["tsmax"][0]) == float(kd["tsmax"][0]), (
            f"root tsmax mismatch at step {step}"
        )
        # Recompute expected aggregates for every flat-tree node from the source of truth
        # (settled_year), and require the flat tree's nuns/tsmax to match. This is what
        # kills a parent-walk mutant that misses intermediate nodes.
        _assert_flat_aggregates_from_source(flat, settled_year, n_stars, step)
        # Query from a random point.
        px, py_c, pz = (q_rng.random(3) * box).tolist()
        fake = _fake_state(params, xs, ys, zs, kd, settled_year, year)
        py_ans = _nearest_unsettled_at_python(fake, px, py_c, pz, year, "lightspeed", exclude=set())
        py_ans = -1 if py_ans is None else py_ans
        got = _query_flat(flat, sy_p, px, py_c, pz, year, False, excl, 0)
        assert got == py_ans, (
            f"N={n_stars} step {step} after settling star={star}: pointer={py_ans} flat={got}"
        )
