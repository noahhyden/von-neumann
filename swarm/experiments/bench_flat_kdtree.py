"""Live verification: flat-tree query wall-clock vs the pointer-tree Rust query.

Runs both `swarm_rust.nearest_unsettled` (pointer tree) and
`swarm_rust.nearest_unsettled_flat` (flat tree) on the same seeded galaxy across a
set of p2 N, reporting queries/sec and the speedup. Not a test - pytest tests are
green already; this is the "does the tree we just built actually go faster in
wall-clock?" step of the discipline chain, so the PR body can quote real numbers.

Run: `uv run --extra dev python -O experiments/bench_flat_kdtree.py`
"""

from __future__ import annotations

import time

import numpy as np

from swarm import models
from swarm.rng import seed_state
from swarm.sim import _build_kdtree, _generate_galaxy

import swarm_rust


N_SIZES = [1024, 4096, 32768]
N_QUERIES = 4096  # random query points per size (same on both backends)
SEED = 42


def bench(n_stars: int) -> dict:
    params = models.SwarmParams(n_stars=n_stars, coordination="lightspeed")
    xs_list, ys_list, zs_list, _sp, _rng = _generate_galaxy(params, seed_state(SEED))
    xs = np.asarray(xs_list, dtype=np.float64)
    ys = np.asarray(ys_list, dtype=np.float64)
    zs = np.asarray(zs_list, dtype=np.float64)

    # Pointer-tree build (Python) and flat-tree build (Rust).
    kd = _build_kdtree(xs_list, ys_list, zs_list)
    flat = swarm_rust.build_flat_kdtree(xs, ys, zs)

    # Half-settled random state, same on both trees (via original indices).
    np_rng = np.random.default_rng(101)
    settled_year_pointer = np.full(n_stars, -1.0, dtype=np.float64)
    settled_mask = np_rng.random(n_stars) < 0.5
    settled_year_pointer[settled_mask] = np_rng.random(settled_mask.sum()) * 1e6
    sy_p = np.full(n_stars, -1.0, dtype=np.float64)
    for i in range(n_stars):
        if settled_year_pointer[i] >= 0.0:
            swarm_rust.mark_settled_flat(
                i, float(settled_year_pointer[i]),
                sy_p, flat["nuns"], flat["tsmax"], flat["star_perm_inv"],
            )

    year = 1e7
    box = params.box_side_pc
    q_rng = np.random.default_rng(202)
    queries = q_rng.random((N_QUERIES, 3)) * box
    excl = np.zeros(4, dtype=np.int32)

    # Pointer-tree query bench.
    t0 = time.perf_counter()
    for px, py, pz in queries:
        swarm_rust.nearest_unsettled(
            px, py, pz, year, False,
            xs, ys, zs, settled_year_pointer,
            int(kd["root"]), kd["axis"], kd["split"], kd["lo"], kd["hi"],
            kd["bxmin"], kd["bxmax"], kd["bymin"], kd["bymax"],
            kd["bzmin"], kd["bzmax"], kd["nuns"], kd["tsmax"],
            kd["bucket_flat"], kd["bucket_offsets"],
            excl, 0,
        )
    t_pointer = time.perf_counter() - t0

    # Flat-tree query bench.
    t0 = time.perf_counter()
    for px, py, pz in queries:
        swarm_rust.nearest_unsettled_flat(
            px, py, pz, year, False,
            flat["xs_p"], flat["ys_p"], flat["zs_p"], sy_p, flat["star_perm"],
            flat["axis"], flat["split"],
            flat["bxmin"], flat["bxmax"], flat["bymin"], flat["bymax"],
            flat["bzmin"], flat["bzmax"], flat["nuns"], flat["tsmax"],
            excl, 0,
        )
    t_flat = time.perf_counter() - t0

    return {
        "n_stars": n_stars,
        "n_queries": N_QUERIES,
        "pointer_wall_s": t_pointer,
        "flat_wall_s": t_flat,
        "pointer_qps": N_QUERIES / t_pointer,
        "flat_qps": N_QUERIES / t_flat,
        "speedup": t_pointer / t_flat,
    }


def main() -> None:
    print(f"{'N':>8} {'pointer_qps':>14} {'flat_qps':>14} {'speedup':>10}")
    print("-" * 50)
    for n in N_SIZES:
        r = bench(n)
        print(f"{r['n_stars']:>8} {r['pointer_qps']:>14.0f} {r['flat_qps']:>14.0f} {r['speedup']:>9.2f}x")


if __name__ == "__main__":
    main()
