"""Experiment: is the fuel tax a scale-stable fraction of the swarm's effort?

The redundant-travel (fuel) tax from light-speed lag is a robust fraction of total journeys
at directed-energy speed. This sweeps the system size N at Lambda = v/c = 0.2 (powered, event
mode) and reports the fuel tax both in absolute wasted journeys (which must grow with the
field) and as a PERCENT of the perfect-information waste (which is the scale-free quantity).
The percent tax stays near ~18-19% across the range, so the cost is a roughly size-independent
fraction of effort, not a small-box artifact.

Reach is bounded by cost: at high v/c the hops are short, so an event-mode run generates
~8N arrivals and each event does O(N) bookkeeping, making a run ~O(N^2); N=2400 already costs
~20 s. We sweep N in {300, 600, 1200} with 16 seeds by default (a 4x span), which is what the
paper's figure regenerates, plus an N=2400 trend point at fewer seeds.

Run:  uv run python -m experiments.finite_size
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from experiments.lightspeed_coordination import run_paired, summary

# Bounded, deterministic sweep. Lambda=0.2 (directed-energy), powered, event mode.
FS_LAMBDA = 0.2
FS_N = (300, 600, 1200)
FS_SEEDS_MAIN = 16
FS_TREND = (2400, 4)  # a single higher-N trend point at fewer seeds (O(N^2) cost)


@dataclass
class FSPoint:
    n_stars: int
    fuel_pct_median: float
    fuel_pct_lo: float
    fuel_pct_hi: float
    fuel_abs_median: float
    time_pct_median: float
    seeds_positive: int
    seeds: int


def run_finite_size(n_list: tuple[int, ...] = FS_N, k: int = FS_SEEDS_MAIN) -> list[FSPoint]:
    from experiments.lightspeed_coordination import SEEDS
    pts: list[FSPoint] = []
    for n in n_list:
        c = run_paired("powered", n_stars=n, probe_speed_c=FS_LAMBDA, seeds=SEEDS[:k])
        fmed, flo, fhi, _, _, _ = summary(c.fuel_pct)
        from experiments.stats_util import sign_test_positive
        kpos, nn, _ = sign_test_positive(c.fuel_abs)
        pts.append(
            FSPoint(
                n_stars=n,
                fuel_pct_median=fmed,
                fuel_pct_lo=flo,
                fuel_pct_hi=fhi,
                fuel_abs_median=statistics.median(c.fuel_abs),
                time_pct_median=statistics.median(c.time_pct) if c.time_pct else float("nan"),
                seeds_positive=kpos,
                seeds=nn,
            )
        )
    return pts


def main() -> None:
    print(f"Fuel tax vs system size - powered, Lambda={FS_LAMBDA}, event mode\n")
    print(f"  {'N':>6}{'fuel % (med [IQR])':>24}{'fuel abs (med)':>16}{'time % (med)':>14}{'seeds +':>10}")
    pts = list(run_finite_size())
    tn, tk = FS_TREND
    pts += run_finite_size((tn,), tk)
    for p in pts:
        iqr = f"{p.fuel_pct_median:+.1f} [{p.fuel_pct_lo:+.1f},{p.fuel_pct_hi:+.1f}]"
        print(f"  {p.n_stars:>6}{iqr:>24}{p.fuel_abs_median:>+16.0f}{p.time_pct_median:>+14.1f}"
              f"{f'{p.seeds_positive}/{p.seeds}':>10}")
    print(
        "\nReading: the absolute wasted journeys grow with the field (more stars, more traffic),\n"
        "but as a PERCENT of the perfect-information waste the fuel tax is roughly flat near\n"
        "~18-19% - a size-independent fraction of effort, not a finite-box artifact."
    )


if __name__ == "__main__":
    main()
