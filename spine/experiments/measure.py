"""Measurement driver for the spine paper (FINDINGS #9): writes committed JSON.

Mirrors the swarm reproducibility backbone: each measurement writes its own JSON under
``results/``; the paper and figures (``paper_figures.py``) restate only those committed
numbers; and ``tests/test_measure_results.py`` re-runs a tiny slice and asserts it matches,
so the JSON cannot silently drift from the fold. The spine fold is a pure seeded function
of ``(params, seed)``, so every JSON here is bit-reproducible run to run.

Unlike swarm's driver this is cheap (a copy time is instant; each tax A/B is a few hundred
stars in event mode). The full regen is a few minutes, dominated by the powered break-even
searches (each a run of full 1200-star fills) and the 24-seed x 3-field-size tax ensemble, so
it runs anywhere. We still commit the JSON and the paper restates only it.

The finding reduces to one inequality (see ``SCRUTINY.md``):

    manufacturing dwell  <<  galactic fill time

with the dwell = the fleet's 1-AU copy cadence in years. The numerator is a lunar-regolith
*proxy* (probe-sim's own bill of materials is an open [GAP]), so the whole case rests on a
robustness *margin*, not on the exact copy time. These measurements establish that margin.

Measurements (SCRUTINY.md claim in brackets):
  copy_time_robustness - dwell fraction vs a x0.1..x1e5 copy-time sweep + the break-even
                         copy time where the powered dwell reaches 1% of the fill [C1, decisive]
  dwell_tax            - derived-vs-zero-dwell A/B over a seed ensemble (median + IQR), a
                         fixed-dt -> event convergence check, and a field-size check [C6]
  policy_sweep         - dwell fraction across the three policies and the crossover copy
                         time at which the dwell stops being negligible for each [C7]

Run:
    uv run --extra dev python -m experiments.measure            # all (skip existing)
    uv run --extra dev python -m experiments.measure --force    # recompute all
    uv run --extra dev python -m experiments.measure copy_time_robustness   # a subset
"""

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

# A fixed seed ensemble - the ONLY source of randomness in this driver, so every JSON is
# bit-reproducible. Sequential offsets by the golden-ratio odd constant (the same constant
# the default scenario seed uses) give well-separated 32-bit seeds without a PRNG here.
SEEDS: tuple[int, ...] = tuple((0x9E3779B9 + 0x61C88647 * i) & 0xFFFFFFFF for i in range(24))

# The dwell-fraction threshold that defines "no longer negligible". One percent of the whole
# galactic fill is a deliberately generous bar: even at 1% the manufacturing dwell is a minor
# correction to a multi-million-year process. Break-even and crossover are quoted against it.
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
    """One dwell as a fraction of the whole fill, event mode (the per-copy separation).

    This is f = tau / T100: the time to build ONE copy against the whole galactic fill. It is
    NOT the manufacturing cost of the fill - the front pays one dwell per settlement, so the
    cumulative cost is f times the number of settlements on the critical path (see
    ``_cumulative_tax``). f fixes the order of magnitude; the cumulative tax is the physical cost.
    """
    t100 = _t100(policy, settle_years, n_stars=n_stars, seed=seed)
    return (settle_years / t100) if (t100 and t100 > 0) else None


def _cumulative_tax(
    policy: str, settle_years: float, *, n_stars: int, seed: int, zero_t100: float | None
) -> float | None:
    """Fractional slowdown of the whole fill from switching the dwell on (A/B, event mode).

    This is the physically meaningful manufacturing cost on exploration: (T100_with -
    T100_zero) / T100_zero, the extra fill time the derived dwell buys against the old
    zero-dwell baseline. It equals f multiplied by the number of dwells on the critical path,
    so it is the quantity the ``rounding error on settlement`` claim must be stated on, not f.
    ``zero_t100`` is the zero-dwell fill (passed in so it is computed once per policy/field).
    """
    if zero_t100 in (None, 0.0):
        return None
    withd = _t100(policy, settle_years, n_stars=n_stars, seed=seed)
    return ((withd - zero_t100) / zero_t100) if withd is not None else None


def _break_even_multiplier(
    policy: str, nominal_settle: float, *, n_stars: int, seed: int, bar: float = NEGLIGIBLE_BAR
) -> dict:
    """The copy-time multiplier at which the dwell fraction first reaches ``bar``.

    The fraction rises with the copy time (a longer dwell is a larger share of the fill), but
    SUB-linearly - a longer dwell also lengthens the fill - so we solve for the crossover by
    bisection on the multiplier rather than assuming linearity (SCRUTINY.md C1). Returns the
    multiplier, the copy time it corresponds to, and the fraction there.
    """
    def frac(mult: float) -> float:
        f = _dwell_fraction(policy, nominal_settle * mult, n_stars=n_stars, seed=seed)
        # If the fill never completes (dwell so large the front stalls under max_years), the
        # dwell is by then a large share of exploration - treat as above the bar.
        return f if f is not None else 1.0

    lo, hi = 1.0, 1.0
    # Expand hi until the fraction crosses the bar (or we hit a sane ceiling).
    while frac(hi) < bar and hi < 1e6:
        lo, hi = hi, hi * 10.0
    if frac(hi) < bar:
        return {"reached": False, "multiplier": None, "copy_time_days": None, "fraction_at": frac(hi)}
    # Bisect in log space for the crossing. 20 steps resolve the crossing decade to ~5 sig
    # figs - far finer than the order-of-magnitude margin this feeds.
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


def _break_even_cumulative(
    policy: str,
    nominal_settle: float,
    *,
    n_stars: int,
    seed: int,
    zero_t100: float | None,
    bar: float = NEGLIGIBLE_BAR,
) -> dict:
    """The copy-time multiplier at which the CUMULATIVE A/B tax first reaches ``bar``.

    Identical bisection to ``_break_even_multiplier`` but on the physical quantity: the whole
    fill's fractional slowdown (``_cumulative_tax``), not the per-copy ratio f. Because the
    cumulative tax is f times the critical-path length, this crossover sits well below the
    f-based one - it is the honest margin the ``rounding error`` claim rests on.
    """

    def frac(mult: float) -> float:
        f = _cumulative_tax(
            policy, nominal_settle * mult, n_stars=n_stars, seed=seed, zero_t100=zero_t100
        )
        return f if f is not None else 1.0

    lo, hi = 1.0, 1.0
    while frac(hi) < bar and hi < 1e6:
        lo, hi = hi, hi * 10.0
    if frac(hi) < bar:
        return {"reached": False, "multiplier": None, "copy_time_days": None, "tax_at": frac(hi)}
    for _ in range(20):
        mid = (lo * hi) ** 0.5
        if frac(mid) < bar:
            lo = mid
        else:
            hi = mid
    mult = (lo * hi) ** 0.5
    return {"reached": True, "multiplier": mult, "copy_time_days": None, "tax_at": frac(mult)}


# --------------------------------------------------------------------------------------
# C1 (decisive): the robustness margin.
# --------------------------------------------------------------------------------------
def m_copy_time_robustness(sc: SpineScenario) -> dict:
    """Sweep the derived copy time and record whether the finding survives (SCRUTINY.md C1).

    The numerator (copy time) is a lunar-regolith proxy for a probe with no sourced BOM, so
    the paper cannot rest on the exact 582 days. It rests on this: the powered dwell fraction
    stays orders below 1% across a x0.1..x1e5 copy-time sweep, and the break-even copy time
    (where it would reach 1%) is thousands of times the nominal. Powered is the tightest case
    for the margin because it has the longest fill; a bigger fill makes the fraction smaller,
    so if powered survives, every faster policy survives by more.
    """
    nominal = derive_settle_time_years(sc)
    nominal_copy_days = nominal * DAYS_PER_JULIAN_YEAR
    policy = "powered"
    n_stars = sc.n_stars
    seed = sc.seed

    # The zero-dwell baseline fill, computed once: the A of every A/B cumulative tax below, and
    # the denominator of the headline ratio T100 = tau / f (so the paper need not store it twice).
    zero_t100 = _t100(policy, 0.0, n_stars=n_stars, seed=seed)

    multipliers = [0.1, 1.0, 10.0, 100.0, 1_000.0, 10_000.0, 100_000.0]
    sweep = []
    for m in multipliers:
        settle = nominal * m
        t100 = _t100(policy, settle, n_stars=n_stars, seed=seed)
        f = (settle / t100) if (t100 and t100 > 0) else None
        tax = ((t100 - zero_t100) / zero_t100) if (t100 is not None and zero_t100) else None
        sweep.append(
            {
                "multiplier": m,
                "settle_years": settle,
                "copy_time_days": settle * DAYS_PER_JULIAN_YEAR,
                "t100_years": t100,
                "dwell_fraction": f,  # per-copy ratio f = tau / T100
                "cumulative_tax": tax,  # physical cost: (T100_with - T100_zero) / T100_zero
                "negligible": (tax is not None and tax < NEGLIGIBLE_BAR),
            }
        )

    # The per-copy ratio f crosses 1% far later than the physical cost does; we keep it for
    # comparison but the headline margin is stated on the cumulative tax.
    be_f = _break_even_multiplier(policy, nominal, n_stars=n_stars, seed=seed)
    if be_f["reached"]:
        be_f["copy_time_days"] = nominal_copy_days * be_f["multiplier"]
    be_cum = _break_even_cumulative(
        policy, nominal, n_stars=n_stars, seed=seed, zero_t100=zero_t100
    )
    if be_cum["reached"]:
        be_cum["copy_time_days"] = nominal_copy_days * be_cum["multiplier"]

    # C2 folded in: the binding build-rate regime. For the default seed the copy time is
    # MACHINERY-limited at 1 AU (about 20 kg/day, ~190x below the rate the 1-AU array could
    # power; the power branch binds only past ~13.7 AU). So the [ESTIMATE] array efficiency
    # (30%) and the solar input do NOT move the copy time here at all - the load-bearing input
    # is the machinery build rate and C*m_seed, whose plausible variation is a small
    # sub-interval of the margin this sweep measures.
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
            "t100_years": zero_t100,
            "dwell_fraction": _dwell_fraction(policy, nominal, n_stars=n_stars, seed=seed),
            "cumulative_tax": _cumulative_tax(
                policy, nominal, n_stars=n_stars, seed=seed, zero_t100=zero_t100
            ),
        },
        "sweep": sweep,
        "break_even": be_cum,  # the headline margin: on the cumulative (physical) tax
        "break_even_dwell_fraction": be_f,  # kept for comparison: on the per-copy ratio f
    }


# --------------------------------------------------------------------------------------
# C6: the A/B dwell tax over an ensemble, with dt-convergence and field-size sub-checks.
# --------------------------------------------------------------------------------------
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
    """The manufacturing dwell's galactic cost, measured A/B over a seed ensemble (C6).

    For each fast (slingshot) policy and each seed we run the front twice - once with the
    derived dwell, once with dwell = 0 (the old ungrounded default) - on the same field, and
    take the fractional slowdown. We report the ensemble median and IQR, NOT a single seed
    (the sibling coordination-tax paper's single-seed numbers were a scrutiny finding). Event
    mode makes each run dt-independent; a separate fixed-dt sub-check shows the fixed scheme
    converges to it. Powered is not brute-forced here (its ~1e6-yr fill makes the ~1.6-yr tax
    unresolvable by simulation - itself the point); it is read analytically in policy_sweep.
    """
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

    # Sub-check 1: dt convergence. Fixed stepping at shrinking dt should approach the event
    # (dt-independent) value for the default seed and the nearest-slingshot policy.
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

    # Sub-check 2: finite size. Median tax over the ensemble at a few field sizes; a flat
    # trend means the small-field tax is representative (SCRUTINY.md C6.3).
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


# --------------------------------------------------------------------------------------
# C7: the generalization - dwell fraction across policies and the crossover.
# --------------------------------------------------------------------------------------
def m_policy_sweep(sc: SpineScenario) -> dict:
    """Dwell fraction and break-even copy time for every policy (SCRUTINY.md C7).

    "The constraint that rules one scale is a rounding error at the next" is claimed generally
    but computed at one point; this sweeps the three named policies, reports the analytic dwell
    fraction of each fill, and gives the crossover - the copy-time multiplier at which each
    policy's dwell would stop being negligible. The faster the policy (shorter fill) the larger
    the fraction and the nearer the crossover, so this also states where the finding breaks.
    """
    nominal = derive_settle_time_years(sc)
    nominal_copy_days = nominal * DAYS_PER_JULIAN_YEAR
    # Cross-policy comparison and crossover run on the smaller (tax) field, so all three
    # policies - including the many break-even fills powered needs - are cheap and on one
    # footing. The tax increases only mildly with field size (0.31->0.34% over 200->800 stars;
    # see dwell_tax finite_size), so the crossover ORDERING is field-size stable; the headline
    # powered numbers at the full 1200-star field live in copy_time_robustness.
    n_stars = sc.tax_n_stars
    seed = sc.seed

    policies = ["powered", "slingshot_nearest", "slingshot_maxboost"]
    rows = []
    for policy in policies:
        zero_t100 = _t100(policy, 0.0, n_stars=n_stars, seed=seed)
        t100 = _t100(policy, nominal, n_stars=n_stars, seed=seed)
        frac = (nominal / t100) if (t100 and t100 > 0) else None
        tax = ((t100 - zero_t100) / zero_t100) if (t100 is not None and zero_t100) else None
        be = _break_even_cumulative(
            policy, nominal, n_stars=n_stars, seed=seed, zero_t100=zero_t100
        )
        if be["reached"]:
            be["copy_time_days"] = nominal_copy_days * be["multiplier"]
        be_f = _break_even_multiplier(policy, nominal, n_stars=n_stars, seed=seed)
        if be_f["reached"]:
            be_f["copy_time_days"] = nominal_copy_days * be_f["multiplier"]
        rows.append(
            {
                "policy": policy,
                "t100_years": t100,
                "dwell_fraction": frac,  # per-copy ratio f = tau / T100
                "cumulative_tax": tax,  # physical cost at nominal (A/B on this field)
                "break_even": be,  # copy-time multiplier where the cumulative tax hits 1%
                "break_even_dwell_fraction": be_f,  # comparison: where f hits 1%
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
