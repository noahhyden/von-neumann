"""Microbench: nearest_unsettled_flat query latency at large N.

Isolates the query kernel (no build, no event loop overhead) at a single N.
The whole-fill bench (`bench_flat_run_fill.py`) is the wall-clock number that
matters for the paper; this file is here to record the query-only floor and
to make it easy to A/B new codegen tweaks against a stable baseline.

Historical numbers (single-thread on the k02 dev machine, min of 5 runs):

    N=32768, 10000 queries, all-unsettled state:
      main (pre p2 codegen tuning):    529k qps
      after restructure + x86-64-v3:   557k qps   (~4% - noise floor)

The 4% number is deliberately called out as small: the p2 substrate's payoff
is at the WHOLE-FILL level, not the query kernel. See `swarm/rust/README.md`
"The SIMD-leaf-scan finding" for why an explicit AVX2 leaf scan was rejected
as a net loss at KD_LEAF = 8.

Run: `uv run --extra dev python -O experiments/bench_flat_kdtree_leaf.py`
"""

from __future__ import annotations

import time

import numpy as np

from swarm import models
from swarm.rng import seed_state
from swarm.sim import _generate_galaxy

import swarm_rust


def main() -> None:
    params = models.SwarmParams(n_stars=32768, coordination="lightspeed")
    xs, ys, zs, _sp, _rng = _generate_galaxy(params, seed_state(42))
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    zs = np.asarray(zs, dtype=np.float64)
    flat = swarm_rust.build_flat_kdtree(xs, ys, zs)
    sy_p = np.full(len(xs), -1.0, dtype=np.float64)
    excl = np.zeros(4, dtype=np.int32)

    rng = np.random.default_rng(101)
    queries = rng.random((10_000, 3)) * params.box_side_pc
    n_q = len(queries)

    for i in range(100):  # warmup
        swarm_rust.nearest_unsettled_flat(
            queries[i, 0], queries[i, 1], queries[i, 2], 1e7, False,
            flat["xs_p"], flat["ys_p"], flat["zs_p"], sy_p, flat["star_perm"],
            flat["axis"], flat["split"],
            flat["bxmin"], flat["bxmax"], flat["bymin"], flat["bymax"],
            flat["bzmin"], flat["bzmax"], flat["nuns"], flat["tsmax"],
            excl, 0,
        )

    runs = []
    for _ in range(5):
        t0 = time.perf_counter()
        for i in range(n_q):
            swarm_rust.nearest_unsettled_flat(
                queries[i, 0], queries[i, 1], queries[i, 2], 1e7, False,
                flat["xs_p"], flat["ys_p"], flat["zs_p"], sy_p, flat["star_perm"],
                flat["axis"], flat["split"],
                flat["bxmin"], flat["bxmax"], flat["bymin"], flat["bymax"],
                flat["bzmin"], flat["bzmax"], flat["nuns"], flat["tsmax"],
                excl, 0,
            )
        runs.append(time.perf_counter() - t0)
    runs.sort()
    print(f"flat_nn_impl at N=32768, {n_q} queries (all-unsettled):")
    print(f"  min: {runs[0]:.4f}s ({n_q / runs[0]:.0f} qps)")
    print(f"  med: {runs[2]:.4f}s")
    print(f"  max: {runs[-1]:.4f}s")


if __name__ == "__main__":
    main()
