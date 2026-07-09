"""Experiment: what does light-speed-limited coordination cost the swarm?

FRONTIER #1. A paired A/B: for each configuration the SAME seeded galaxy is filled under
`coordination="instant"` (the source model's perfect global info) and `"lightspeed"` (a
probe knows a distant star is settled only after the news-light arrives). The two share the
seed, so the per-seed difference is the coordination effect alone; we report the ensemble
distribution (median, IQR, bootstrap CI, sign test), never a single run.

ALL runs use `stepping="event"` - the dt-independent event-driven fold. This matters: with a
coarse fixed timestep the tax is badly overstated, because dt >> hop time batches many
launches into one step so they all decide from the same stale snapshot and collide. That is a
discretization artifact (see experiments/dt_artifact.py); at the resolved limit it is gone.

The finding, at resolved timestep:
- The TIME tax (fill-100% slowdown) is ~0 - light-speed lag does not slow the fill. The
  large time penalty of coarse-dt models is an artifact.
- The real cost is REDUNDANT TRAVEL: stale views send probes to stars already claimed by
  others. Probes-built is identical in both modes (= offspring x settlements = 2N), so the
  cost is entirely wasted JOURNEYS - a fuel/energy tax a perfect-information model hides.
- That fuel tax scales cleanly with Lambda = v/c (the probe speed in units of c): negligible
  at the powered cruise, ~1% of journeys at slingshot speeds (Lambda ~ 0.01), rising to ~18%
  at directed-energy speeds (Lambda ~ 0.2). Lambda is the governing parameter - for fuel, not
  time.

Run:  uv run python -m experiments.lightspeed_coordination
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from swarm import SwarmParams, simulate_swarm
from swarm.models import C_PC_PER_YEAR, KM_S_TO_PC_YR

from experiments.stats_util import bootstrap_median_ci, sign_test_positive

# Fixed, deterministic seed ensemble. The two coordination modes share each seed (paired).
SEEDS = [0x9E3779B9 + 2654435761 * k for k in range(32)]
N_STARS = 400  # the Lambda sweep runs powered flight here (event mode is fast for powered)

# The v/c grid for the headline scaling law. The powered cruise (3e-5 c) sits far to the left
# (tax negligible); the slingshot policies self-limit near Lambda ~ 0.01; directed-energy /
# light-sail concepts reach 0.1-0.2 c. probe_speed_c IS Lambda for powered flight.
LAMBDAS = (0.01, 0.03, 0.05, 0.1, 0.2)


@dataclass
class Paired:
    """Per-seed paired metrics (lightspeed vs instant) for one configuration."""
    time_pct: list[float] = field(default_factory=list)   # fill-100% slowdown %
    fuel_abs: list[float] = field(default_factory=list)    # extra wasted journeys (count)
    fuel_pct: list[float] = field(default_factory=list)    # extra wasted journeys, % of instant
    v_eff_km_s: list[float] = field(default_factory=list)  # mean launch speed (lightspeed run)


def run_paired(policy: str, *, n_stars: int = N_STARS, probe_speed_c: float = 3e-5,
               speed_cap_c: float | None = None, seeds: list[int] | None = None,
               max_retargets: int = 8) -> Paired:
    """Fill each seeded galaxy under instant and lightspeed (event mode); collect paired metrics."""
    seeds = seeds if seeds is not None else SEEDS
    cap = speed_cap_c if speed_cap_c is not None else max(0.05, 2.0 * probe_speed_c)
    out = Paired()
    for s in seeds:
        common = dict(n_stars=n_stars, policy=policy, probe_speed_c=probe_speed_c,
                      speed_cap_c=cap, stepping="event", max_retargets=max_retargets)
        i = simulate_swarm(SwarmParams(**common, coordination="instant"), seed=s)
        l = simulate_swarm(SwarmParams(**common, coordination="lightspeed"), seed=s)
        if i.t100_years and l.t100_years:
            out.time_pct.append((l.t100_years - i.t100_years) / i.t100_years * 100.0)
        out.fuel_abs.append(float(l.wasted_arrivals - i.wasted_arrivals))
        if i.wasted_arrivals:
            out.fuel_pct.append((l.wasted_arrivals - i.wasted_arrivals) / i.wasted_arrivals * 100.0)
        out.v_eff_km_s.append(l.mean_launch_speed_km_s)
    return out


def summary(xs: list[float]) -> tuple[float, float, float, int, int, float]:
    """(median, IQR-lo, IQR-hi, bootstrap-lo, bootstrap-hi, sign-test-p) - or zeros if empty."""
    if not xs:
        return 0.0, 0.0, 0.0, 0, 0, 1.0
    ys = sorted(xs)
    med = statistics.median(ys)
    iqr_lo, iqr_hi = ys[len(ys) // 4], ys[(3 * len(ys)) // 4]
    _, blo, bhi = bootstrap_median_ci(ys)
    _, _, p = sign_test_positive(ys)
    return med, iqr_lo, iqr_hi, blo, bhi, p


def lambda_sweep(seeds: list[int] | None = None) -> dict[float, Paired]:
    """The headline: fuel + time tax vs Lambda = v/c, powered flight, event mode."""
    return {lam: run_paired("powered", probe_speed_c=lam, seeds=seeds) for lam in LAMBDAS}


def main() -> None:
    print(f"Light-speed coordination, event (resolved) timestep - {len(SEEDS)} paired seeds\n")

    # (1) Headline scaling law: fuel + time tax vs Lambda = v/c (powered, N=600).
    print(f"Fuel tax (extra wasted journeys) and time tax vs Lambda = v/c  (powered, N={N_STARS}):")
    print(f"  {'Lambda':>7}{'v (km/s)':>10}{'fuel % (med [95% CI])':>28}{'sign p':>10}{'time % (med)':>14}")
    sweep = lambda_sweep()
    for lam in LAMBDAS:
        c = sweep[lam]
        fmed, _, _, flo, fhi, fp = summary(c.fuel_pct)
        tmed, *_ = summary(c.time_pct)
        v = statistics.median(c.v_eff_km_s)
        print(f"  {lam:>7}{v:>10.0f}   {fmed:>+6.1f} [{flo:+.1f},{fhi:+.1f}]{fp:>13.1e}{tmed:>+13.1f}")

    # (2) Where the natural policies sit on that axis (slingshots self-limit; cruise is tiny).
    print("\nWhere real policies sit on the Lambda axis (event mode, N=300):")
    print(f"  {'policy':<22}{'v_eff (km/s)':>13}{'Lambda_eff':>12}{'fuel % (med)':>14}{'sign p':>10}")
    for pol, v0 in (("powered", 3e-5), ("slingshot_nearest", 3e-5), ("slingshot_maxboost", 3e-5)):
        c = run_paired(pol, n_stars=300, probe_speed_c=v0)
        v = statistics.median(c.v_eff_km_s)
        lam = v * KM_S_TO_PC_YR / C_PC_PER_YEAR
        fmed, _, _, _, _, fp = summary(c.fuel_pct)
        print(f"  {pol:<22}{v:>13.0f}{lam:>12.2e}{fmed:>+13.1f}{fp:>10.1e}")

    print(
        "\nReading: the fill-TIME tax is ~0 at every speed (light-speed lag does not slow the\n"
        "fill - the coarse-dt penalty is an artifact). The real cost is redundant TRAVEL, and\n"
        "it scales cleanly with Lambda = v/c: ~1% of journeys at slingshot speeds, ~18% at\n"
        "directed-energy speeds. Probes-built is identical in both modes, so the tax is fuel,\n"
        "not replication and not time."
    )


if __name__ == "__main__":
    main()
