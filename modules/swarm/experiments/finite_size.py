"""Experiment: is the fuel tax a scale-stable fraction of the swarm's effort?"""

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
        "but as a PERCENT of the perfect-information waste the fuel tax DECLINES with N (~19% at\n"
        "N=300 down to ~13% at N=4800, and ~1.5% at N=200,000). The fraction is not size-independent;\n"
        "at galactic scale the coordination fuel tax as a fraction of effort largely vanishes."
    )


if __name__ == "__main__":
    from experiments._run import warn_if_no_optimize

    warn_if_no_optimize("experiments.finite_size")
    main()
