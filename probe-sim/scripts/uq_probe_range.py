"""End-to-end UQ validation on a probe-sim headline finding.

CLAUDE.md §2 asks for a small script that runs the full flow and asserts on
behavior, not on execution. Issue #35 asks specifically for four things:

  (a) error bars shrink when an input's spread shrinks,
  (b) Sobol total-order indices sum to ~1 for an additive model,
  (c) a dominant input actually dominates the Sobol ranking,
  (d) the whole pipeline is deterministic under seeding.

We validate all four against a real probe-sim finding: the maximum heliocentric
distance a solar-electric probe can hold a required power demand (Borgue & Hein
shape). Inputs are sourced Kopp & Lean TSI (1360.8 +/- 0.5) and the Landis &
Bailey space multi-junction efficiency range (0.28-0.32); area and demand are
Fixed here (they are per-scenario knobs, not per-source uncertainties, at this
step of the depth track).

Run: `uv run --extra dev python scripts/uq_probe_range.py`
"""

from __future__ import annotations

import math
import sys

from probe_sim.environment import SOLAR_CONSTANT_1AU_W_M2, SOLAR_CONSTANT_1AU_W_M2_STD
from vn_core.uq.distributions import Fixed, Normal, Uniform
from vn_core.uq.sample import monte_carlo
from vn_core.uq.sobol import sobol_total_order


def max_reach_au(sample: dict[str, float]) -> float:
    """d = sqrt(S0 * area * eff / required_power_w). All inputs sampled."""
    return math.sqrt(
        sample["S0"] * sample["area_m2"] * sample["efficiency"]
        / sample["required_power_w"]
    )


HEADLINE_INPUTS = {
    "S0": Normal(mean=SOLAR_CONSTANT_1AU_W_M2, std=SOLAR_CONSTANT_1AU_W_M2_STD),
    "efficiency": Uniform(low=0.28, high=0.32),  # Landis & Bailey space multi-junction range
    "area_m2": Fixed(200.0),
    "required_power_w": Fixed(208_000.0),
}


def main() -> int:
    print("probe-sim UQ end-to-end validation")
    print("-----------------------------------")
    print(f"Finding: max heliocentric reach (AU) for a 200 m^2 array at 208 kW demand.")
    print(f"Inputs:")
    print(f"  S0          Normal({SOLAR_CONSTANT_1AU_W_M2}, {SOLAR_CONSTANT_1AU_W_M2_STD})  W/m^2 (Kopp & Lean 2011)")
    print(f"  efficiency  Uniform(0.28, 0.32)         (Landis & Bailey 2002, AIAA-2002-0718)")
    print(f"  area_m2     Fixed(200.0)                m^2 (scenario knob)")
    print(f"  P_required  Fixed(208 000)              W (from synthetic factory in tests)")
    print()

    # --- (a) + (d): MC produces an error bar; error bar shrinks when a spread does.
    wide = monte_carlo(HEADLINE_INPUTS, max_reach_au, n=10_000, seed=42)
    narrow_inputs = {**HEADLINE_INPUTS, "efficiency": Fixed(0.30)}
    narrow = monte_carlo(narrow_inputs, max_reach_au, n=10_000, seed=42)
    print(f"MC (wide  efficiency): d = {wide.mean:.4f} AU, std {wide.std:.4f}, "
          f"90% CI [{wide.q05:.4f}, {wide.q95:.4f}]")
    print(f"MC (fixed efficiency): d = {narrow.mean:.4f} AU, std {narrow.std:.4f}, "
          f"90% CI [{narrow.q05:.4f}, {narrow.q95:.4f}]")
    assert narrow.std < wide.std, "Pinning efficiency should shrink the error bar"
    print("  [OK] error bar shrinks when an input's spread shrinks (issue #35 (a))")

    # Determinism (d): the SAME call produces byte-identical results.
    again = monte_carlo(HEADLINE_INPUTS, max_reach_au, n=10_000, seed=42)
    assert again.values == wide.values, "MC not deterministic under seeding"
    print("  [OK] MC deterministic under seeding (issue #35 (d))")

    # --- (b): additive model Sobol indices sum to ~1.
    add_inputs = {"a": Uniform(0, 1), "b": Uniform(0, 1), "c": Uniform(0, 1)}
    add_sobol = sobol_total_order(add_inputs, lambda s: s["a"] + s["b"] + s["c"], n=3000, seed=99)
    total = sum(add_sobol.total_order.values())
    print(f"Sobol on f = a + b + c, Uniform inputs: sum(S_T) = {total:.3f}")
    assert abs(total - 1.0) < 0.05, f"Additive sum {total} not near 1"
    print("  [OK] additive-model Sobol indices sum to ~1 (issue #35 (b))")

    # --- (c): probe-sim finding - efficiency should dominate the ranking.
    ranking = sobol_total_order(HEADLINE_INPUTS, max_reach_au, n=2000, seed=57)
    print("Sobol total-order (probe-sim reach):")
    for name, val in ranking.ranked():
        print(f"  {name:20s} {val:+.4f}")
    top = ranking.ranked()[0]
    assert top[0] == "efficiency", f"Expected efficiency to dominate, got {top}"
    assert top[1] > 0.90, f"Dominant S_T too weak: {top[1]}"
    print("  [OK] dominant input dominates the ranking (issue #35 (c))")

    print()
    print("All four validation properties pass. UQ prototype green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
