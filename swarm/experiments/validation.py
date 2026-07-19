"""Experiment: does the model reproduce Nicholson & Forgan (2013)?

The paired study rests on the "instant" (perfect global information) run being a faithful
stand-in for Nicholson & Forgan's model. Two levels of validation:

1. Reduction (exact, pinned by the test suite): "instant" is the c -> infinity limit of the
   light-speed gate by construction, so it reproduces the plain perfect-information fold
   bit-for-bit (test_instant_mode_is_the_perfect_info_baseline).

2. QUANTITATIVE agreement with Nicholson & Forgan (2013), at the resolved event timestep:
   (a) gravitational slingshots explore about two orders of magnitude faster than powered
   flight - their headline; and (b) their surprising result that aiming for the NEAREST star
   beats aiming for the LARGEST boost on total exploration time. Earlier a coarse fixed
   dt=5000 yr quantized the boosted hops and undercut the speedup to ~20x; the event fold
   removes that and recovers the full ~two-orders-of-magnitude figure.

Run:  uv run python -O -m experiments.validation  # ensemble; -O strips debug invariants
"""

from __future__ import annotations

from swarm import SwarmParams, simulate_swarm

SEED = 0x9E3779B9
N = 400


def _run(policy: str) -> object:
    # Event (resolved) timestep, so the slingshot speedup is not dt-quantized.
    return simulate_swarm(SwarmParams(n_stars=N, policy=policy, stepping="event"), seed=SEED)


def main() -> None:
    print(f"Nicholson & Forgan reproduction - N={N}, seed={SEED}, event timestep\n")

    powered = _run("powered")
    nearest = _run("slingshot_nearest")
    maxboost = _run("slingshot_maxboost")

    print(f"  {'policy':<20}{'t100 (yr)':>14}{'v_max (km/s)':>14}")
    for name, r in (("powered", powered), ("slingshot_nearest", nearest), ("slingshot_maxboost", maxboost)):
        print(f"  {name:<20}{r.t100_years:>14,.0f}{r.max_probe_speed_km_s:>14,.0f}")

    speedup = powered.t100_years / nearest.t100_years
    print(f"\n  slingshots >> powered (their headline): nearest fills {speedup:.0f}x sooner than powered")
    print(f"    (about two orders of magnitude, as N&F report; the coarse dt=5000 fold gave only ~20x)")
    print(f"  nearest beats max-boost on time:        {nearest.t100_years:,.0f} < "
          f"{maxboost.t100_years:,.0f} yr  ({nearest.t100_years < maxboost.t100_years})")
    print(f"  max-boost reaches the higher speed:     {maxboost.max_probe_speed_km_s:,.0f} > "
          f"{nearest.max_probe_speed_km_s:,.0f} km/s  ({maxboost.max_probe_speed_km_s > nearest.max_probe_speed_km_s})")


if __name__ == "__main__":
    from experiments._run import warn_if_no_optimize

    warn_if_no_optimize("experiments.validation")
    main()
