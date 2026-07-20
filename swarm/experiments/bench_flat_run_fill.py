"""Live verification: `run_fill_flat` wall-clock vs `run_fill` (pointer tree) at p2 N.

Follows the same "does it actually go faster" step as `bench_flat_kdtree.py`, but for the
whole event loop rather than the query alone. Both paths return byte-identical aggregates
(`tests/test_flat_run_fill_oracle.py`); this script is only about wall-clock.

Run: `uv run --extra dev python -O experiments/bench_flat_run_fill.py`
"""

from __future__ import annotations

import os
import time
from dataclasses import fields

from swarm import SwarmParams, simulate_swarm


# p2 N, and one canonical coordination mode per row for the paper's headline configs.
CONFIGS = [
    (1024, "lightspeed"),
    (4096, "lightspeed"),
    (4096, "inflight"),
    (32768, "lightspeed"),
    (32768, "inflight"),
]
SEED = 42


def bench_one(n: int, coord: str) -> dict:
    params = SwarmParams(
        n_stars=n, policy="powered", coordination=coord,
        stepping="event", probe_speed_c=0.2, speed_cap_c=0.4,
    )
    # Force pointer path.
    os.environ["SWARM_NO_RUST_FLAT"] = "1"
    t0 = time.perf_counter()
    r_ptr = simulate_swarm(params, seed=SEED, record_steps=False)
    t_ptr = time.perf_counter() - t0

    # Flat path.
    os.environ.pop("SWARM_NO_RUST_FLAT", None)
    t0 = time.perf_counter()
    r_flat = simulate_swarm(params, seed=SEED, record_steps=False)
    t_flat = time.perf_counter() - t0

    # Correctness sanity: both paths agree on the paper-visible aggregates.
    for f in fields(r_ptr):
        assert getattr(r_ptr, f.name) == getattr(r_flat, f.name), (
            f"aggregate {f.name!r} differs: pointer={getattr(r_ptr, f.name)!r} "
            f"flat={getattr(r_flat, f.name)!r}"
        )
    return {
        "n": n, "coord": coord,
        "pointer_s": t_ptr, "flat_s": t_flat,
        "speedup": t_ptr / t_flat if t_flat > 0 else float("inf"),
    }


def main() -> None:
    print(f"{'N':>7} {'coord':>10} {'pointer(s)':>12} {'flat(s)':>10} {'speedup':>10}")
    print("-" * 55)
    for n, coord in CONFIGS:
        r = bench_one(n, coord)
        print(f"{r['n']:>7} {r['coord']:>10} {r['pointer_s']:>11.3f}s {r['flat_s']:>9.3f}s {r['speedup']:>9.2f}x")


if __name__ == "__main__":
    main()
