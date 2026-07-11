"""N vs wall-time microbenchmark for the swarm fold (issue #27, item 2 acceptance).

Times a single seeded run at a geometric ladder of star counts and reports the wall time, a
per-1000-stars figure, and the local scaling exponent (slope of log t vs log N between adjacent
points). Run it before and after a change to see the effect on scale; nothing here writes a
committed artifact, so it is a stopwatch, not a result.

This is a WALL-CLOCK aid only. The fold is deterministic (CLAUDE.md 7), so timing never changes a
number - which is exactly why it is safe to time whatever hardware is handy (see docs/HARDWARE.md).

What the numbers show (and do not): issue #27 removed the O(N)/O(P) per-event scans (cell-list
nearest-neighbour, event heap, incremental snapshot), but a single run stayed empirically ~O(N^2),
because a wasted probe re-targets from deep inside the already-settled core and the nearest
*believed*-unsettled star from there sits out at the front - a genuinely NON-LOCAL query the flat
cell list answered by expanding rings out to the front (O(core)). Issue #30 replaced the cell list
with a k-d tree over the unsettled set (sim._nearest_unsettled_at): per-node unsettled-count and
latest-settle-year aggregates let a query PRUNE whole subtrees that are provably fully
believed-settled - including the light-delayed "beacon still in transit" case - so it reaches the
front in O(log N + local). The per-query examination is now near-CONSTANT (a few leaves, ~tens of
candidates) instead of growing with the core. The residual mild super-linearity is not the index:
it is (i) the model's own arrival count, which grows ~N^0.09 per star as a larger field breeds more
stale-view races, and (ii) the O(log N) tree descent. The local exponent settles well below the old
~2 (toward ~1 as N grows and the polylog flattens), and the finite_size sweep now reaches N=200,000.

Run:  uv run python -m experiments.scaling_benchmark
      uv run python -m experiments.scaling_benchmark 500 1000 2000 4000 8000
"""

from __future__ import annotations

import math
import sys
import time

from swarm import SwarmParams, simulate_swarm

SEED = 0x9E3779B9

# Two representative regimes: the finite-size sweep's worst case (fast, lightspeed, lots of
# re-targeting) and the powered baseline. Both are event mode (the mode every measurement uses).
REGIMES = {
    "powered_lambda0.2_lightspeed": dict(policy="powered", probe_speed_c=0.2, speed_cap_c=0.4,
                                         stepping="event", coordination="lightspeed"),
    "powered_cruise_instant": dict(policy="powered", stepping="event"),
}


def bench(ns: list[int]) -> None:
    for label, cfg in REGIMES.items():
        print(f"\n{label}:")
        print(f"  {'N':>8}{'wall_s':>12}{'ms/1k_stars':>14}{'exponent':>11}")
        prev: tuple[int, float] | None = None
        for n in ns:
            t0 = time.perf_counter()
            r = simulate_swarm(SwarmParams(n_stars=n, **cfg), seed=SEED)
            dt = time.perf_counter() - t0
            assert r.final_settled == n, f"expected a full fill, got {r.final_settled}/{n}"
            exp = ""
            if prev is not None:
                exp = f"{math.log(dt / prev[1]) / math.log(n / prev[0]):.2f}"
            print(f"  {n:>8}{dt:>12.3f}{dt / n * 1e6:>14.2f}{exp:>11}")
            prev = (n, dt)


def main(argv: list[str]) -> None:
    ns = [int(a) for a in argv] if argv else [500, 1000, 2000, 4000, 8000]
    print(f"Swarm scaling microbenchmark (seed={SEED:#x}); exponent = local slope of log t vs log N")
    bench(ns)


if __name__ == "__main__":
    main(sys.argv[1:])
