"""Experiment: what does the perfect-information baseline actually reproduce?

The paired study rests on the "instant" (perfect global information) run being a faithful
stand-in for Nicholson & Forgan's model, so the light-speed run is measured against a
trustworthy baseline. This makes that check explicit and states honestly what does and
does not match.

Two levels of validation:

1. Reduction (exact): "instant" is the c -> infinity limit of the light-speed gate by
   construction, so it must reproduce the default perfect-information fold bit-for-bit.
   The test suite pins this (test_instant_mode_is_the_perfect_info_baseline); we re-assert
   it here as a printed check.

2. Qualitative agreement with Nicholson & Forgan (2013): we reproduce their two headline
   findings - (a) gravitational slingshots explore far faster than powered flight, and
   (b) their surprising result that aiming for the NEAREST star beats aiming for the
   LARGEST boost on total exploration time. We do NOT reproduce their ~100x speedup
   quantitatively: at the default dt=5000 yr the boosted hops are shorter than one step
   and get quantized, so the measured speedup is ~20x (documented in REFERENCES.md).
   Lowering dt recovers more of it; the qualitative ordering is dt-robust.

Run:  uv run python -m experiments.validation      (from the swarm/ package root)
"""

from __future__ import annotations

from swarm import SwarmParams, simulate_swarm

SEED = 0x9E3779B9
N = 400


def _run(policy: str, coordination: str = "instant", **kw: object) -> object:
    return simulate_swarm(SwarmParams(n_stars=N, policy=policy, coordination=coordination, **kw), seed=SEED)


def main() -> None:
    print(f"Baseline validation - N={N}, seed={SEED}\n")

    # (1) Exact reduction: instant == default perfect-info fold.
    explicit = _run("slingshot_nearest", "instant")
    default = simulate_swarm(SwarmParams(n_stars=N, policy="slingshot_nearest"), seed=SEED)
    reduces = (
        [s.n_settled for s in explicit.steps] == [s.n_settled for s in default.steps]
        and explicit.t100_years == default.t100_years
    )
    print(f"(1) 'instant' reproduces the perfect-info baseline bit-for-bit: {reduces}")

    # (2) Qualitative Nicholson & Forgan findings.
    powered = _run("powered")
    nearest = _run("slingshot_nearest")
    maxboost = _run("slingshot_maxboost")

    print("\n(2) Qualitative agreement with Nicholson & Forgan (2013):")
    print(f"  {'policy':<20}{'t100 (yr)':>14}{'v_max (km/s)':>14}")
    for name, r in (("powered", powered), ("slingshot_nearest", nearest), ("slingshot_maxboost", maxboost)):
        print(f"  {name:<20}{r.t100_years:>14,.0f}{r.max_probe_speed_km_s:>14,.0f}")

    speedup = powered.t100_years / nearest.t100_years
    print(f"\n  slingshot >> powered:            nearest fills {speedup:.0f}x sooner than powered")
    print(f"    (dt-limited; N&F's ~100x needs a smaller dt - see REFERENCES.md)")
    print(f"  nearest beats max-boost on time: nearest t100 {nearest.t100_years:,.0f} < "
          f"max-boost {maxboost.t100_years:,.0f} yr  ({nearest.t100_years < maxboost.t100_years})")
    print(f"  max-boost reaches higher speed:  {maxboost.max_probe_speed_km_s:,.0f} > "
          f"{nearest.max_probe_speed_km_s:,.0f} km/s  ({maxboost.max_probe_speed_km_s > nearest.max_probe_speed_km_s})")


if __name__ == "__main__":
    main()
