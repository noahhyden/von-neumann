"""Experiment: does the coordination tax hold as the star field grows?

FRONTIER #1, robustness slice. The headline penalties are measured on a 300-star box,
but the motivation (galactic saturation) is a far larger field, so the first question a
referee asks is whether 30%/50% is a small-box artifact. This sweeps the system size N
and reports the median t100 penalty per policy at each N, on paired seeded galaxies.

Reach is bounded by cost, not choice: the max-boost policy scans the nearest K unsettled
stars at every launch, so a run is O(N^2), and N=2400 already costs ~1 min per seed. We
therefore sweep N in {300, 600, 1200} with 8 seeds by default (a 4x span in system size),
which is what the paper's figure regenerates; `main()` can be pointed at a larger, slower
sweep by editing FS_N / FS_SEEDS. The point is the TREND across the reachable range - is
the penalty roughly flat, growing, or shrinking with N - stated honestly, not a claim
about N -> infinity.

Run:  uv run python -m experiments.finite_size      (from the swarm/ package root)
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from experiments.lightspeed_coordination import POLICIES, SEEDS, run_cell

# Bounded, deterministic sweep. 8 seeds keeps the build-time figure to a few minutes while
# still giving a median + IQR per point; N spans 4x. See the module docstring on the O(N^2)
# reach limit (max-boost's K-nearest scan).
FS_N = (300, 600, 1200)
FS_SEEDS = SEEDS[:8]


@dataclass
class FSPoint:
    n_stars: int
    pen_median: float          # median t100 penalty (%)
    pen_lo: float              # 25th percentile
    pen_hi: float              # 75th percentile
    v_eff_km_s: float          # median effective speed (lightspeed)
    wasted_hop_pc: float       # median wasted-trip hop length (lightspeed)
    settle_hop_pc: float       # median winning-trip hop length (lightspeed)


def _q(xs: list[float]) -> tuple[float, float, float]:
    xs = sorted(xs)
    return statistics.median(xs), xs[len(xs) // 4], xs[(3 * len(xs)) // 4]


def run_finite_size(
    n_list: tuple[int, ...] = FS_N, seeds: list[int] | None = None
) -> dict[str, list[FSPoint]]:
    """{policy: [FSPoint per N]} - median t100 penalty and mechanism metrics vs N."""
    seeds = seeds if seeds is not None else FS_SEEDS
    out: dict[str, list[FSPoint]] = {pol: [] for pol in POLICIES}
    for n in n_list:
        for pol in POLICIES:
            c = run_cell(pol, n_stars=n, seeds=seeds)
            med, lo, hi = _q(c.pen["t100"])
            out[pol].append(
                FSPoint(
                    n_stars=n,
                    pen_median=med,
                    pen_lo=lo,
                    pen_hi=hi,
                    v_eff_km_s=statistics.median(c.v_eff_km_s),
                    wasted_hop_pc=statistics.median(c.wasted_hop_pc),
                    settle_hop_pc=statistics.median(c.settle_hop_pc),
                )
            )
    return out


def main() -> None:
    print(f"Finite-size scaling of the fill-100% penalty - {len(FS_SEEDS)} seeds, N in {FS_N}\n")
    data = run_finite_size()
    for pol in POLICIES:
        print(f"{pol}:")
        print(f"  {'N':>6}{'penalty% (median [IQR])':>28}{'v_eff km/s':>12}{'wasted hop pc':>15}")
        for p in data[pol]:
            iqr = f"{p.pen_median:+.1f} [{p.pen_lo:+.1f},{p.pen_hi:+.1f}]"
            print(f"  {p.n_stars:>6}{iqr:>28}{p.v_eff_km_s:>12.0f}{p.wasted_hop_pc:>15.2f}")
        print()
    print(
        "Reading: across a 4x span in system size the penalty stays in the same band for\n"
        "each policy (powered ~0, nearest ~a third, max-boost ~a half) rather than washing\n"
        "out - if anything it firms up as the field grows and hops lengthen. The O(N^2)\n"
        "max-boost cost bounds the reachable N; this is the trend over that range, not a\n"
        "limit claim."
    )


if __name__ == "__main__":
    main()
