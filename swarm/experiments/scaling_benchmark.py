"""N vs wall-time microbenchmark for the swarm fold (issue #27, item 2 acceptance)."""

from __future__ import annotations

import math
import sys
import time

from swarm import SwarmParams, simulate_swarm

SEED = 0x9E3779B9

# Two representative regimes: the finite-size sweep's worst case (fast, lightspeed, lots of re-targeting) and the powered baseline.
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
    from experiments._run import warn_if_no_optimize

    warn_if_no_optimize("experiments.scaling_benchmark")
    main(sys.argv[1:])
