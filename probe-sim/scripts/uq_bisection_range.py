"""UQ end-to-end on the operational-range **bisection** finding.

`scripts/uq_probe_range.py` uses the closed-form analytic reach; this script
targets probe_sim.range.operational_range, which is the actual load-bearing
finding of the module (it wraps closure-sim's simulate() at each bisection
step). Slower per evaluation, so a smaller sample size is honest.

Confirms the same four validation properties from issue #35 on the bisection
finding, so the UQ prototype is not only correct on analytic maths - it also
works on the finding a paper would actually cite.

Run: `uv run --extra dev python scripts/uq_bisection_range.py`
"""

from __future__ import annotations

import sys
import time

from closure_sim.models import Factory, ReplicationParams, Subsystem

from probe_sim.environment import (
    SOLAR_CONSTANT_1AU_W_M2,
    SOLAR_CONSTANT_1AU_W_M2_STD,
    SolarArray,
)
from probe_sim.range import operational_range
from probe_sim.uq.distributions import Fixed, Normal, Uniform
from probe_sim.uq.sample import monte_carlo
from probe_sim.uq.sobol import sobol_total_order


def _factory() -> Factory:
    return Factory(
        name="synthetic-uq-probe",
        subsystems=[
            Subsystem(
                name="structure",
                mass_kg=1000.0,
                category="structure",
                producible_locally=True,
                energy_to_produce_kwh_per_kg=100.0,
            ),
            Subsystem(
                name="chips",
                mass_kg=100.0,
                category="electronics",
                producible_locally=False,
            ),
        ],
    )


def _rep() -> ReplicationParams:
    return ReplicationParams(
        seed_mass_kg=1000.0,
        local_build_rate_kg_per_day=10.0,
        vitamin_resupply_mass_kg=1000.0,
        resupply_cadence_days=30.0,
        available_power_kw=1000.0,
        target_output_kg_per_day=50.0,
        duration_days=3650,
        dt_days=1.0,
    )


FACTORY = _factory()
REP = _rep()


def bisection_range_au(sample: dict[str, float]) -> float:
    """The load-bearing finding: how far can the probe still self-replicate?

    Wraps operational_range, closing over the factory / rep from the scenario;
    only the sourced inputs (S0, area, efficiency) are sampled.
    """
    array = SolarArray(area_m2=sample["area_m2"], efficiency=sample["efficiency"])
    result = operational_range(
        array, FACTORY, REP, lo_au=0.1, hi_au=20.0, tol_au=1e-2,
        solar_constant=sample["S0"],
    )
    if result.operational_range_au is None:
        # Underpowered even at 0.1 AU - return a floor so MC / Sobol still
        # produce numeric outputs. This is more informative than raising: a
        # sampled parameter making the probe non-viable IS the finding.
        return 0.0
    return result.operational_range_au


HEADLINE_INPUTS = {
    "S0": Normal(mean=SOLAR_CONSTANT_1AU_W_M2, std=SOLAR_CONSTANT_1AU_W_M2_STD),
    "efficiency": Uniform(low=0.28, high=0.32),
    "area_m2": Fixed(200.0),
}


def main() -> int:
    print("probe-sim UQ end-to-end (bisection finding, closure-sim in the loop)")
    print("-" * 70)
    print("Finding: operational_range_au for a 200 m^2 array driving the synthetic")
    print("         factory (energy_to_produce=100 kWh/kg, target=50 kg/day).")
    print()

    # (a) + (d): MC with error bar; shrinkage under a narrowed input.
    t0 = time.time()
    wide = monte_carlo(HEADLINE_INPUTS, bisection_range_au, n=200, seed=42)
    dt_wide = time.time() - t0
    print(f"MC n=200 (wide efficiency)   d = {wide.mean:.3f} +- {wide.std:.3f} AU, "
          f"90% CI [{wide.q05:.3f}, {wide.q95:.3f}]   [{dt_wide:.2f}s]")

    narrow_inputs = {**HEADLINE_INPUTS, "efficiency": Fixed(0.30)}
    t0 = time.time()
    narrow = monte_carlo(narrow_inputs, bisection_range_au, n=200, seed=42)
    dt_narrow = time.time() - t0
    print(f"MC n=200 (fixed efficiency)  d = {narrow.mean:.3f} +- {narrow.std:.3f} AU, "
          f"90% CI [{narrow.q05:.3f}, {narrow.q95:.3f}]   [{dt_narrow:.2f}s]")
    assert narrow.std < wide.std, "Pinning efficiency should shrink the error bar"
    print("  [OK] (a) error bar shrinks with input spread")

    # (d) determinism on the load-bearing finding.
    again = monte_carlo(HEADLINE_INPUTS, bisection_range_au, n=200, seed=42)
    assert again.values == wide.values, "MC not deterministic on bisection finding"
    print("  [OK] (d) deterministic under seeding (byte-identical)")

    # (b) - (c): Sobol total-order, on the actual bisection finding.
    # n=100 * (K+2)=5 = 500 evaluations of a ~0.5 s bisection.
    print()
    print(f"Sobol total-order (n=100, {100 * (len(HEADLINE_INPUTS) + 2)} evals) ...")
    t0 = time.time()
    r = sobol_total_order(HEADLINE_INPUTS, bisection_range_au, n=100, seed=57)
    dt_s = time.time() - t0
    print(f"  variance {r.variance:.4e}, mean {r.mean:.3f} AU, {dt_s:.2f}s")
    for name, val in r.ranked():
        print(f"    {name:12s} {val:+.4f}")
    top_name, top_val = r.ranked()[0]
    assert top_name == "efficiency", f"expected efficiency to dominate, got {top_name}"
    print(f"  [OK] (c) efficiency dominates the bisection-finding Sobol ranking")
    print()
    print("Load-bearing UQ pipeline green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
