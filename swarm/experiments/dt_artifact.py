"""Experiment: the coarse fixed-timestep coordination tax is a discretization artifact.

A fixed timestep dt advances the fold in constant jumps and processes every probe that has
arrived within the window together. When dt exceeds the hop time - which it does badly in the
boosted/slingshot regime (hops ~1e2-1e3 yr against the slice-1 default dt=5000 yr) - many
launches land in one window and all decide from the same stale snapshot, so they collide far
more than they physically would. That inflates the measured light-speed coordination tax.

This sweep shows the fill-100% time penalty for slingshot_nearest collapsing from ~30% at
dt=5000 toward ~0 as dt shrinks, and matches the dt-independent event fold at the bottom. It
is why the paper's headline metric is redundant travel at event resolution, not fill time.

Run:  uv run python -O -m experiments.dt_artifact  # ensemble; -O strips debug invariants
"""

from __future__ import annotations

import statistics

from swarm import SwarmParams, simulate_swarm

from experiments.stats_util import sign_test_positive

SEEDS = [0x9E3779B9 + 2654435761 * k for k in range(32)]
N_STARS = 300
DTS = (5000.0, 2000.0, 1000.0, 500.0, 250.0)


def _median_time_penalty(dt: float | None) -> tuple[float, float, float, int, int]:
    """Median fill-100% penalty (%) over the ensemble at fixed dt, or event mode if dt is None."""
    ps: list[float] = []
    for s in SEEDS:
        common = dict(n_stars=N_STARS, policy="slingshot_nearest")
        if dt is None:
            common["stepping"] = "event"
        else:
            common["stepping"] = "fixed"
            common["dt_years"] = dt
        i = simulate_swarm(SwarmParams(**common, coordination="instant"), seed=s)
        l = simulate_swarm(SwarmParams(**common, coordination="lightspeed"), seed=s)
        if i.t100_years and l.t100_years:
            ps.append((l.t100_years - i.t100_years) / i.t100_years * 100.0)
    ys = sorted(ps)
    med = statistics.median(ys)
    kpos, n, _ = sign_test_positive(ys)
    return med, ys[len(ys) // 4], ys[(3 * len(ys)) // 4], kpos, n


def main() -> None:
    print(f"Fill-100% time penalty vs timestep - slingshot_nearest, N={N_STARS}, {len(SEEDS)} seeds\n")
    print(f"  {'timestep':>12}{'median %':>12}{'IQR %':>18}{'seeds +':>10}")
    for dt in DTS:
        med, lo, hi, kpos, n = _median_time_penalty(dt)
        print(f"  {f'dt={dt:.0f} yr':>12}{med:>+11.1f}{f'[{lo:+.1f},{hi:+.1f}]':>18}{f'{kpos}/{n}':>10}")
    med, lo, hi, kpos, n = _median_time_penalty(None)
    print(f"  {'event (dt->0)':>12}{med:>+11.1f}{f'[{lo:+.1f},{hi:+.1f}]':>18}{f'{kpos}/{n}':>10}")
    print(
        "\nReading: the apparent time tax is monotone in dt and collapses to ~0 as the timestep\n"
        "resolves the boosted hops. The ~30% headline of a dt=5000 model is a discretization\n"
        "artifact, not a physical coordination penalty."
    )


if __name__ == "__main__":
    from experiments._run import warn_if_no_optimize

    warn_if_no_optimize("experiments.dt_artifact")
    main()
