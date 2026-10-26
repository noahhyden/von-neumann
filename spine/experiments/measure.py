"""Measurement driver for the spine paper (FINDINGS #9): writes committed JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median

from swarm.models import SwarmParams
from swarm.sim import simulate_swarm

from spine.run import DAYS_PER_JULIAN_YEAR, derive_settle_time_years
from spine.scenario import SpineScenario

RESULTS = Path(__file__).resolve().parent / "results"

# A fixed golden-ratio-stepped seed ensemble (see REFERENCES.md) - the ONLY source of randomness in this driver, so every JSON is bit-reproducible.
SEEDS: tuple[int, ...] = tuple((0x9E3779B9 + 0x61C88647 * i) & 0xFFFFFFFF for i in range(24))

# The dwell-fraction threshold (1% of the galactic fill, a convention marked [ESTIMATE] in REFERENCES.md) that defines "no longer negligible".
NEGLIGIBLE_BAR: float = 0.01


def _t100(
    policy: str,
    settle_years: float,
    *,
    n_stars: int,
    seed: int,
    stepping: str = "event",
    dt_years: float = 1.0,
    offspring: int = 2,
) -> float | None:
    """Fill time (years to 100% settled) for one swarm run. Event mode is dt-independent."""
    kw: dict[str, object] = dict(
        n_stars=n_stars,
        offspring_per_settlement=offspring,
        settle_time_years=settle_years,
        policy=policy,
        stepping=stepping,
    )
    if stepping == "fixed":
        kw["dt_years"] = dt_years
    return simulate_swarm(SwarmParams(**kw), seed=seed).t100_years  # type: ignore[arg-type]


def _dwell_fraction(
    policy: str, settle_years: float, *, n_stars: int, seed: int
) -> float | None:
    """One dwell as a fraction of the whole fill, event mode (the analytic separation)."""
    t100 = _t100(policy, settle_years, n_stars=n_stars, seed=seed)
    return (settle_years / t100) if (t100 and t100 > 0) else None


def _break_even_multiplier(
    policy: str, nominal_settle: float, *, n_stars: int, seed: int, bar: float = NEGLIGIBLE_BAR
) -> dict:
    """The copy-time multiplier at which the dwell fraction first reaches ``bar``."""
    def frac(mult: float) -> float:
        f = _dwell_fraction(policy, nominal_settle * mult, n_stars=n_stars, seed=seed)
        # If the fill never completes (dwell so large the front stalls under max_years), the dwell is by then a large share of exploration - treat as above the bar.
        return f if f is not None else 1.0

    lo, hi = 1.0, 1.0
    # Expand hi until the fraction crosses the bar (or we hit a sane ceiling).
    while frac(hi) < bar and hi < 1e6:
        lo, hi = hi, hi * 10.0
    if frac(hi) < bar:
        return {"reached": False, "multiplier": None, "copy_time_days": None, "fraction_at": frac(hi)}
    # Bisect in log space for the crossing.
    for _ in range(20):
        mid = (lo * hi) ** 0.5
        if frac(mid) < bar:
            lo = mid
        else:
            hi = mid
    mult = (lo * hi) ** 0.5
    return {
        "reached": True,
        "multiplier": mult,
        "copy_time_days": None,  # filled by caller (needs nominal copy days)
        "fraction_at": frac(mult),
    }


# C1 (decisive): the robustness margin.
def m_copy_time_robustness(sc: SpineScenario) -> dict:
    """Sweep the derived copy time and record whether the finding survives (SCRUTINY.md C1)."""
    nominal = derive_settle_time_years(sc)
    nominal_copy_days = nominal * DAYS_PER_JULIAN_YEAR
    policy = "powered"
    n_stars = sc.n_stars
    seed = sc.seed

    multipliers = [0.1, 1.0, 10.0, 100.0, 1_000.0, 10_000.0, 100_000.0]
    sweep = []
    for m in multipliers:
        settle = nominal * m
        f = _dwell_fraction(policy, settle, n_stars=n_stars, seed=seed)
        sweep.append(
            {
                "multiplier": m,
                "settle_years": settle,
                "copy_time_days": settle * DAYS_PER_JULIAN_YEAR,
                "dwell_fraction": f,
                "negligible": (f is not None and f < NEGLIGIBLE_BAR),
            }
        )

    be = _break_even_multiplier(policy, nominal, n_stars=n_stars, seed=seed)
    if be["reached"]:
        be["copy_time_days"] = nominal_copy_days * be["multiplier"]

    # C2 folded in: the binding build-rate regime and the [ESTIMATE] array-efficiency sensitivity (copy time scales as 1/efficiency, so 20-40% vs 30% is x0.75..x1.5; see REFERENCES.md).
    return {
        "measurement": "copy_time_robustness",
        "config": {
            "policy": policy,
            "n_stars": n_stars,
            "seed": seed,
            "stepping": "event",
            "negligible_bar": NEGLIGIBLE_BAR,
        },
        "nominal": {
            "settle_years": nominal,
            "copy_time_days": nominal_copy_days,
            "dwell_fraction": _dwell_fraction(policy, nominal, n_stars=n_stars, seed=seed),
        },
        "sweep": sweep,
        "break_even": be,
    }


# C6: the A/B dwell tax over an ensemble, with dt-convergence and field-size sub-checks.
def _quartiles(xs: list[float]) -> dict:
    ys = sorted(xs)
    n = len(ys)

    def q(p: float) -> float:
        if n == 1:
            return ys[0]
        idx = p * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        return ys[lo] + (ys[hi] - ys[lo]) * (idx - lo)

    return {"median": median(ys), "q25": q(0.25), "q75": q(0.75), "min": ys[0], "max": ys[-1]}


def m_dwell_tax(sc: SpineScenario) -> dict:
    """The manufacturing dwell's galactic cost, measured A/B over a seed ensemble (C6)."""
    nominal = derive_settle_time_years(sc)
    n_stars = sc.tax_n_stars
    policies = ["slingshot_nearest", "slingshot_maxboost"]

    ensemble = {}
    for policy in policies:
        per_seed = []
        for seed in SEEDS:
            withd = _t100(policy, nominal, n_stars=n_stars, seed=seed, stepping="event")
            zerod = _t100(policy, 0.0, n_stars=n_stars, seed=seed, stepping="event")
            tax = (
                (withd - zerod) / zerod
                if (withd is not None and zerod not in (None, 0.0))
                else None
            )
            per_seed.append(
                {"seed": seed, "t100_with": withd, "t100_zero": zerod, "tax_fraction": tax}
            )
        taxes = [r["tax_fraction"] for r in per_seed if r["tax_fraction"] is not None]
        ensemble[policy] = {"per_seed": per_seed, "stats": _quartiles(taxes) if taxes else None}

    # Sub-check 1: dt convergence - fixed stepping at shrinking dt should approach the dt-independent event-mode tax for the default seed and nearest-slingshot.
    dt_seed = sc.seed
    dt_policy = "slingshot_nearest"
    event_tax = None
    ez = _t100(dt_policy, 0.0, n_stars=n_stars, seed=dt_seed, stepping="event")
    ew = _t100(dt_policy, nominal, n_stars=n_stars, seed=dt_seed, stepping="event")
    if ew is not None and ez not in (None, 0.0):
        event_tax = (ew - ez) / ez
    dt_convergence = {"event_tax": event_tax, "fixed": []}
    for dt in [8.0, 4.0, 2.0, 1.0, 0.5]:
        fw = _t100(dt_policy, nominal, n_stars=n_stars, seed=dt_seed, stepping="fixed", dt_years=dt)
        fz = _t100(dt_policy, 0.0, n_stars=n_stars, seed=dt_seed, stepping="fixed", dt_years=dt)
        ft = (fw - fz) / fz if (fw is not None and fz not in (None, 0.0)) else None
        dt_convergence["fixed"].append({"dt_years": dt, "tax_fraction": ft})

    # Sub-check 2: finite size - the median tax over the ensemble at a few field sizes; a flat trend means the small-field tax is representative (SCRUTINY.md C6.3).
    size_check = {"policy": dt_policy, "sizes": []}
    for n in [200, 400, 800]:
        taxes = []
        for seed in SEEDS:
            w = _t100(dt_policy, nominal, n_stars=n, seed=seed, stepping="event")
            z = _t100(dt_policy, 0.0, n_stars=n, seed=seed, stepping="event")
            if w is not None and z not in (None, 0.0):
                taxes.append((w - z) / z)
        size_check["sizes"].append(
            {"n_stars": n, "median_tax": median(taxes) if taxes else None, "n_seeds": len(taxes)}
        )

    return {
        "measurement": "dwell_tax",
        "config": {
            "n_stars": n_stars,
            "n_seeds": len(SEEDS),
            "settle_years": nominal,
            "stepping": "event",
            "offspring_per_settlement": sc.offspring_per_settlement,
        },
        "ensemble": ensemble,
        "dt_convergence": dt_convergence,
        "finite_size": size_check,
    }


# C7: the generalization - dwell fraction across policies and the crossover.
def m_policy_sweep(sc: SpineScenario) -> dict:
    """Dwell fraction and break-even copy time for every policy (SCRUTINY.md C7)."""
    nominal = derive_settle_time_years(sc)
    nominal_copy_days = nominal * DAYS_PER_JULIAN_YEAR
    # Cross-policy comparison and crossover run on the smaller (tax) field, so all three policies - including the ~50 break-even fills powered needs - are cheap and on one footing.
    n_stars = sc.tax_n_stars
    seed = sc.seed

    policies = ["powered", "slingshot_nearest", "slingshot_maxboost"]
    rows = []
    for policy in policies:
        t100 = _t100(policy, nominal, n_stars=n_stars, seed=seed)
        frac = (nominal / t100) if (t100 and t100 > 0) else None
        be = _break_even_multiplier(policy, nominal, n_stars=n_stars, seed=seed)
        if be["reached"]:
            be["copy_time_days"] = nominal_copy_days * be["multiplier"]
        rows.append(
            {
                "policy": policy,
                "t100_years": t100,
                "dwell_fraction": frac,
                "break_even": be,
            }
        )

    return {
        "measurement": "policy_sweep",
        "config": {
            "n_stars": n_stars,
            "seed": seed,
            "stepping": "event",
            "settle_years": nominal,
            "copy_time_days": nominal_copy_days,
            "negligible_bar": NEGLIGIBLE_BAR,
        },
        "policies": rows,
    }


MEASUREMENTS = {
    "copy_time_robustness": m_copy_time_robustness,
    "dwell_tax": m_dwell_tax,
    "policy_sweep": m_policy_sweep,
}


def run_measurement(name: str, force: bool = False) -> None:
    """Zero-argument-shaped entry for vn-run: the measurement functions take a scenario, specs do not."""
    rc = main([name] + (["--force"] if force else []))
    if rc:
        raise RuntimeError(f"spine measurement {name!r} failed with exit code {rc}")


def main(argv: list[str]) -> int:
    force = "--force" in argv
    names = [a for a in argv if not a.startswith("--")]
    if not names:
        names = list(MEASUREMENTS)

    RESULTS.mkdir(exist_ok=True)
    sc = SpineScenario.default()
    for name in names:
        if name not in MEASUREMENTS:
            print(f"unknown measurement: {name}", file=sys.stderr)
            return 2
        path = RESULTS / f"{name}.json"
        if path.exists() and not force:
            print(f"skip {name} (exists; --force to recompute)")
            continue
        print(f"run  {name} ...", flush=True)
        result = MEASUREMENTS[name](sc)
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"wrote {path.relative_to(RESULTS.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
