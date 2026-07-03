"""Differential test, half 2 of 2: recompute gen-diff.mjs's random cases with the
REAL closure-sim and assert the TS port agrees. Run from the closure-sim package
so the import resolves:

    node ../frontend/scripts/gen-diff.mjs
    cd ../closure-sim && uv run python ../frontend/scripts/diff_check.py

Handles the JS<->Python edge encodings: JS Infinity -> math.inf, JS null -> None.
"""
import json
import math
import sys

from closure_sim.closure import compute_closure
from closure_sim.models import Factory, ReplicationParams, Subsystem
from closure_sim.replication import simulate

CASES = "/tmp/frontend-diff-cases.json"


def decode(v):
    # reverse gen-diff.mjs's non-finite sentinels
    if v == "__inf__":
        return math.inf
    if v == "__-inf__":
        return -math.inf
    if v == "__nan__":
        return math.nan
    return v


def approx(a, b, rel=1e-6, abs_=1e-6):
    a = decode(a)
    # normalise the None/inf encodings
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, str):  # regime label
        return a == b
    if math.isinf(a) or math.isinf(b):
        return math.isinf(a) and math.isinf(b) and (a > 0) == (b > 0)
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def main() -> int:
    cases = json.load(open(CASES))
    failures = 0
    checked = 0
    for i, case in enumerate(cases):
        f = Factory(
            name="rand",
            subsystems=[Subsystem(**s) for s in case["factory"]["subsystems"]],
        )
        rep = ReplicationParams(**case["rep"])
        c = compute_closure(f)
        s = simulate(f, rep)
        py = {
            "closure_ratio": c.closure_ratio,
            "productivity_per_day": s.productivity_per_day,
            "energy_cap_kg_per_day": s.energy_cap_kg_per_day,
            "resupply_ceiling_kg_per_day": s.resupply_ceiling_kg_per_day,
            "time_to_target_days": s.time_to_target_days,
            "empirical_doubling_time_days": s.empirical_doubling_time_days,
            "final_factory_mass_kg": s.final_factory_mass_kg,
            "final_output_kg_per_day": s.final_output_kg_per_day,
            "late_regime": s.regime_timeline[-1].regime.value,
        }
        for k, pv in py.items():
            checked += 1
            tv = case["ts"][k]
            if not approx(tv, pv):
                failures += 1
                print(f"  case {i} field {k}: TS={tv!r} PY={pv!r}")
    n = len(cases)
    print(f"checked {n} cases / {checked} fields")
    if failures:
        print(f"{failures} MISMATCHES")
        return 1
    print("TS port matches Python on all random cases: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
