"""Heavy measurement driver: runs the full referee-revision ensemble and writes committed JSON.

This is the "beefed-up simulation" the paper's second revision rests on. It is deliberately
kept OUT of CI: a full event-mode ensemble over many seeds, sizes, branching factors and three
coordination modes is minutes-to-hours of compute, which would overwhelm the GitHub runners.
Instead it runs locally and commits its deterministic seeded output as JSON result artifacts
under ``experiments/results/``; the figures (``paper_figures.py``) and the paper then restate
only those committed numbers, and CI just renders the figures and typesets (no heavy sim). The
fold is a pure seeded function of (params, seed), so every JSON is bit-reproducible run to run.

Each measurement writes its own file and SKIPS if the file already exists (pass ``--force`` to
recompute, or name specific measurements to run a subset), so a long run is resumable and can be
committed incrementally - progress survives an interrupted session.

Run:
    uv run --extra dev python -m experiments.measure            # all measurements (skip existing)
    uv run --extra dev python -m experiments.measure --force    # recompute all
    uv run --extra dev python -m experiments.measure lambda_sweep floor_bracket   # a subset

Measurements (referee asks in brackets):
    lambda_sweep   - fuel/time/energy tax vs Lambda = v/c, powered, event [headline]
    branching      - tax vs offspring branching factor 2/3/4 [ask 1: the parameter that makes contention]
    energy_tax     - energy-weighted tax per policy, count vs (1/2)v^2 weighting, 1x-2x bracket [ask 2]
    finite_size    - fuel tax % vs N over a 16x span, with the extrapolation caveat [ask 3]
    concurrency    - in-flight probe count vs coverage: why a loser is never on the critical path [ask 4]
    floor_bracket  - instant / inflight / lightspeed: how much of the tax survives in-flight relay [ask 5]
    retarget_cap   - fuel tax vs the max_retargets bookkeeping cap: show the insensitivity [smaller point]
    dt_artifact    - fill-time tax collapsing to ~0 as the fixed timestep resolves [kept from round 1]
    validation     - Nicholson & Forgan quantitative reproduction at event mode [kept from round 1]
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from swarm import SwarmParams, simulate_swarm
from swarm.models import C_PC_PER_YEAR, KM_S_TO_PC_YR, N_HOP_BINS
from swarm.sim import initial_state

from experiments.stats_util import bootstrap_median_ci, loglog_slope_ci, sign_test_positive

RESULTS_DIR = Path(__file__).resolve().parent / "results"
# v3: per-run records carry ``total_arrivals`` (settlements + wasted trips). Added to record()
# during the second revision; the version bump makes every committed artifact declare it.
SCHEMA_VERSION = 3

# Deterministic seed ensemble (paired: every mode shares each seed). 512 available; each
# measurement uses a prefix sized to its cost. The multiplier is odd (coprime to 2^32), so the
# 32-bit-masked seeds are all distinct. The headline speed sweep (cheap at N=500, ~1.6 s/seed)
# uses the full 512; the larger sweeps (finite_size, near-linear since #30) use short prefixes.
# Extending the pool past the old 64 leaves every existing prefix (<= 48) byte-identical.
SEEDS = [0x9E3779B9 + 2654435761 * k for k in range(512)]


# --------------------------------------------------------------------------------------------
# seed-ensemble parallelism (issue #27 item 3)
# --------------------------------------------------------------------------------------------
# The fold is a pure, seeded function of (params, seed), so every (seed, mode) run is independent
# and embarrassingly parallel. We fan the seed loop out over CPU cores with the standard-library
# ProcessPoolExecutor. This is a WALL-CLOCK aid only and must not change any number: results are
# always collected back into seed order (executor.map preserves input order), so 1, 4, or N
# workers produce byte-identical JSON. Set SWARM_WORKERS to override the core count; SWARM_WORKERS=1
# forces a serial-equivalent loop (also the fallback when a positive count cannot be parsed).

def _worker_count() -> int:
    """Number of worker processes: SWARM_WORKERS if set to a positive int, else os.cpu_count()."""
    env = os.environ.get("SWARM_WORKERS")
    if env is not None:
        try:
            n = int(env)
        except ValueError:
            n = 0
        if n >= 1:
            return n
    return os.cpu_count() or 1


def _paired_worker(args: tuple[str, str, dict, int]) -> tuple[dict, dict]:
    """One paired (seed, base/treat) run. Top-level so ProcessPoolExecutor can pickle it.

    Takes plain params + seed and returns the two records; SwarmParams is rebuilt inside the
    worker so nothing framework-specific has to cross the process boundary.
    """
    mode_base, mode_treat, params, seed = args
    b = simulate_swarm(SwarmParams(coordination=mode_base, **params), seed=seed)
    t = simulate_swarm(SwarmParams(coordination=mode_treat, **params), seed=seed)
    return (record(b), record(t))


# --------------------------------------------------------------------------------------------
# metric extraction + summary
# --------------------------------------------------------------------------------------------

def record(r) -> dict:
    """The scalar metrics of one run, as a plain dict (JSON-serialisable, no objects)."""
    return {
        "t25": r.t25_years, "t50": r.t50_years, "t75": r.t75_years,
        "t90": r.t90_years, "t99": r.t99_years, "t100": r.t100_years,
        "final_settled": r.final_settled, "n_stars": r.n_stars,
        "total_launched": r.total_probes_launched,
        "total_arrivals": r.total_arrivals,
        "wasted_arrivals": r.wasted_arrivals,
        "wasted_travel_pc": r.wasted_travel_pc,
        "midflight_aborts": r.midflight_aborts,
        "settle_energy_c2": r.settle_energy_c2,
        "wasted_energy_c2": r.wasted_energy_c2,
        "mean_launch_speed_km_s": r.mean_launch_speed_km_s,
        "mean_wasted_speed_km_s": r.mean_wasted_speed_km_s,
        "mean_wasted_hop_pc": r.mean_wasted_hop_pc,
        "settle_wall_hist": list(r.settle_wall_hist),
        "wasted_wall_hist": list(r.wasted_wall_hist),
    }


def summarize(xs: list[float]) -> dict:
    """Median, IQR, seeded bootstrap 95% CI, sign test, and mean for a per-seed list."""
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "median": None, "iqr_lo": None, "iqr_hi": None,
                "ci_lo": None, "ci_hi": None, "mean": None, "seeds_pos": 0, "seeds_nonzero": 0, "p": 1.0}
    ys = sorted(xs)
    _, blo, bhi = bootstrap_median_ci(ys)
    kpos, nnz, p = sign_test_positive(ys)
    return {
        "n": len(ys), "median": statistics.median(ys),
        "iqr_lo": ys[len(ys) // 4], "iqr_hi": ys[(3 * len(ys)) // 4],
        "ci_lo": blo, "ci_hi": bhi, "mean": statistics.fmean(ys),
        "seeds_pos": kpos, "seeds_nonzero": nnz, "p": p,
    }


def pct_delta(treat: float, base: float) -> float | None:
    """Percent change of ``treat`` over ``base`` (None if base is zero/None)."""
    if base is None or treat is None or base == 0:
        return None
    return (treat - base) / base * 100.0


def through_origin_slope(xs: list[float], ys: list[float]) -> float | None:
    """Least-squares slope of ``y = a*x`` through the origin: a = sum(x*y)/sum(x^2).

    The clumpy-field test fits the fuel tax against Lambda through the origin (the derivation
    predicts tax = 1*Lambda, i.e. a = 1) - so a per-seed slope is the single number that says
    whether clumpiness moved the LAW's coefficient.
    """
    pairs = [(x, y) for x, y in zip(xs, ys) if y is not None]
    denom = sum(x * x for x, _ in pairs)
    if denom == 0:
        return None
    return sum(x * y for x, y in pairs) / denom


def clark_evans_R(xs: list[float], ys: list[float], zs: list[float], box_side_pc: float) -> float:
    """Clark-Evans aggregation index R = observed mean NN distance / Poisson expectation (3D).

    R = 1 Poisson (uniform), R < 1 clustered, R > 1 regular. The Poisson 3D nearest-neighbour
    expectation is 0.55396 * rho^(-1/3) with rho = N / L^3 (Clark & Evans 1954, the 3D form).
    Used comparatively across fields at the SAME N and box, so the (mild, constant) box edge bias
    cancels. O(N^2) - cheap next to the sim, and computed on a modest seed subset.
    """
    n = len(xs)
    if n < 2 or box_side_pc <= 0:
        return 1.0
    total = 0.0
    for i in range(n):
        best = float("inf")
        xi, yi, zi = xs[i], ys[i], zs[i]
        for j in range(n):
            if i == j:
                continue
            d2 = (xi - xs[j]) ** 2 + (yi - ys[j]) ** 2 + (zi - zs[j]) ** 2
            if d2 < best:
                best = d2
        total += best ** 0.5
    observed = total / n
    rho = n / (box_side_pc ** 3)
    expected = 0.55396 / (rho ** (1.0 / 3.0))
    return observed / expected


def write_result(name: str, config: dict, payload: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{name}.json"
    doc = {"schema_version": SCHEMA_VERSION, "generator": "experiments.measure",
           "measurement": name, "config": config, **payload}
    out.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    return out


def _paired(mode_treat: str, *, seeds: list[int], mode_base: str = "instant", **params) -> list[tuple[dict, dict]]:
    """Fill each seeded galaxy under ``mode_base`` and ``mode_treat`` (same seed); return records.

    Parallel over seeds (see ``_worker_count``): each (seed, base/treat) run is independent. Results
    are always collected in seed order, so the returned list is identical to the serial version for
    any worker count. SWARM_WORKERS=1 takes the serial branch.
    """
    args = [(mode_base, mode_treat, params, s) for s in seeds]
    n = len(args)
    rows: list[tuple[dict, dict]] = []
    workers = _worker_count()
    if workers <= 1:
        for i, a in enumerate(args):
            rows.append(_paired_worker(a))
            print(f"      seed {i + 1}/{n}", end="\r", flush=True)
    else:
        # executor.map preserves input order, so rows come back in seed order regardless of which
        # worker finishes first; iterating it yields each result as it is ready, in that order.
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for i, row in enumerate(ex.map(_paired_worker, args)):
                rows.append(row)
                print(f"      seed {i + 1}/{n} ({workers} workers)", end="\r", flush=True)
    print(" " * 40, end="\r")
    return rows


def _tax_block(rows: list[tuple[dict, dict]]) -> dict:
    """Standard paired-tax summaries (fuel/time/travel/energy/probes) from baseline vs treatment."""
    fuel_pct = [pct_delta(t["wasted_arrivals"], b["wasted_arrivals"]) for b, t in rows]
    fuel_abs = [t["wasted_arrivals"] - b["wasted_arrivals"] for b, t in rows]
    time_pct = [pct_delta(t["t100"], b["t100"]) for b, t in rows]
    travel_pct = [pct_delta(t["wasted_travel_pc"], b["wasted_travel_pc"]) for b, t in rows]
    # Energy tax: extra wasted-journey kinetic energy over the baseline's useful (winning) energy,
    # at the flyby (1x) and rendezvous (2x) endpoints of the brake-and-reaccel bracket.
    e_extra = [t["wasted_energy_c2"] - b["wasted_energy_c2"] for b, t in rows]
    e_useful = [b["settle_energy_c2"] for b, t in rows]
    energy_pct_1x = [ex / eu * 100.0 if eu else None for ex, eu in zip(e_extra, e_useful)]
    energy_pct_2x = [2.0 * ex / eu * 100.0 if eu else None for ex, eu in zip(e_extra, e_useful)]
    probes_pct = [pct_delta(t["total_launched"], b["total_launched"]) for b, t in rows]
    return {
        "fuel_pct": summarize(fuel_pct), "fuel_abs": summarize(fuel_abs),
        "time_pct": summarize(time_pct), "travel_pct": summarize(travel_pct),
        "energy_pct_1x": summarize(energy_pct_1x), "energy_pct_2x": summarize(energy_pct_2x),
        "probes_pct": summarize(probes_pct),
        "per_seed": [{"base": b, "treat": t} for b, t in rows],
    }


# --------------------------------------------------------------------------------------------
# measurements
# --------------------------------------------------------------------------------------------

def m_lambda_sweep() -> None:
    """Headline: fuel/time/travel/energy tax vs Lambda = v/c (powered, event, lightspeed vs instant).

    512 seeds: this is the headline, and at N=500 a paired seed is ~1.6 s, so the ensemble is sized
    to a precision target (a tight CI on the tax), not to compute - unlike the expensive sweeps.
    """
    seeds = SEEDS[:512]
    n_stars = 500
    lambdas = [0.01, 0.03, 0.05, 0.1, 0.2]
    data = {}
    for lam in lambdas:
        print(f"    Lambda={lam}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                       probe_speed_c=lam, speed_cap_c=max(0.05, 2 * lam), stepping="event")
        data[str(lam)] = _tax_block(rows)
    write_result("lambda_sweep",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "mode_base": "instant", "mode_treat": "lightspeed",
                  "stepping": "event"},
                 {"data": data})


def m_branching() -> None:
    """Fuel/time/energy tax vs the replication branching factor (offspring per settlement)."""
    seeds = SEEDS[:32]
    n_stars = 400
    # Swept high (to 16) so the saturation claim is tested, not asserted from a 3-point plateau:
    # more offspring make more simultaneous races, but once enough probes already contend the
    # marginal collision rate should level off. Event-mode cost grows with offspring (off=16 has
    # ~6x the arrivals of off=4), so this measurement is the heavy end of the local run.
    offspring = [2, 3, 4, 8, 16]
    lambdas = [0.05, 0.2]
    data = {}
    for lam in lambdas:
        for off in offspring:
            key = f"lam{lam}_off{off}"
            print(f"    Lambda={lam} offspring={off}", flush=True)
            rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                           probe_speed_c=lam, speed_cap_c=max(0.05, 2 * lam),
                           offspring_per_settlement=off, stepping="event")
            data[key] = _tax_block(rows)
    write_result("branching",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "offspring": offspring, "mode_treat": "lightspeed",
                  "stepping": "event"},
                 {"data": data})


def m_energy_tax() -> None:
    """Energy-weighted tax per policy: count-tax vs (1/2)v^2-weighted tax (1x and 2x brackets).

    The energy weighting bites hardest where journeys have DIFFERENT speeds - the slingshot
    policies, whose wasted trips are faster/longer than the powered cruise. So we run all three
    policies (lightspeed vs instant, event) and report the count tax alongside the energy tax.
    """
    seeds = SEEDS[:32]
    n_stars = 400
    policies = ["powered", "slingshot_nearest", "slingshot_maxboost"]
    data = {}
    for pol in policies:
        print(f"    policy={pol}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy=pol, stepping="event")
        block = _tax_block(rows)
        # effective speed of wasted vs winning journeys (median over seeds), for the discussion
        v_wasted = [t["mean_wasted_speed_km_s"] for _, t in rows if t["mean_wasted_speed_km_s"] > 0]
        block["mean_wasted_speed_km_s"] = statistics.median(v_wasted) if v_wasted else 0.0
        block["lambda_eff"] = (block["mean_wasted_speed_km_s"] * KM_S_TO_PC_YR / C_PC_PER_YEAR)
        data[pol] = block
    write_result("energy_tax",
                 {"policies": policies, "n_stars": n_stars, "n_seeds": len(seeds),
                  "mode_treat": "lightspeed", "stepping": "event",
                  "note": "energy_pct_1x/2x are the flyby/rendezvous bracket; relativistic excess < 3.1% to 0.2c"},
                 {"data": data})


def m_finite_size() -> None:
    """Fuel tax % vs system size over a 16x span (300..4800), powered, Lambda=0.2, event.

    Seeds are scaled down as N grows. This is the honest lever arm for the scale discussion: a 16x
    span, NOT an extrapolation to 1e11 stars. Since issue #30 the run is near-linear (the k-d tree
    over the unsettled set, REFERENCES.md), so this committed ladder is no longer compute-bound and
    the sweep extends cleanly to N=200,000 - raise the ladder below when regenerating for a
    higher-N figure (the numbers here are the pinned artifact the drift guard checks, so leave them
    unless you are deliberately regenerating the result at a new scale).
    """
    # High-seed sweep to resolve whether the large-N tax decline is real or scatter. Since #30 the
    # run is near-linear, so the ladder now reaches N=200,000 (a ~670x span, not the old 16x). The
    # 300..4800 points and their seed counts are unchanged (they regenerate byte-identically); the
    # higher-N points scale seeds DOWN to a precision target - the tax spread narrows with N (the
    # per-seed 200k tax clusters within ~0.5 pp), so fewer seeds hold the median tight. The old
    # O(N^2) cost that once capped this at 4800 is gone: the whole ladder to 200k is cheaper than
    # the old sweep to 4800 (which was dominated by its 2400/4800 points).
    n_seeds_by_n = [(300, 48), (600, 48), (1200, 48), (2400, 48), (4800, 32),
                    (9600, 32), (24000, 24), (48000, 16), (200000, 8)]
    data = {}
    per_n_fuel: dict[int, list[float]] = {}
    for n, k in n_seeds_by_n:
        print(f"    N={n} ({k} seeds)", flush=True)
        rows = _paired("lightspeed", seeds=SEEDS[:k], n_stars=n, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event")
        data[str(n)] = _tax_block(rows)
        per_n_fuel[n] = [pct_delta(t["wasted_arrivals"], b["wasted_arrivals"]) for b, t in rows]
    # Scale trend, computed here so it regenerates from source (not only stated in the paper prose):
    # OLS slope of the median tax on log10(N), with a seeded-bootstrap 95% CI resampling seeds within
    # each N. The decline is convex (accelerating), so this linear slope is a local summary; the
    # paper reports the per-step drops for the shape.
    ns = [n for n, _ in n_seeds_by_n]
    slope, slope_lo, slope_hi = loglog_slope_ci([math.log10(n) for n in ns],
                                                [per_n_fuel[n] for n in ns])
    write_result("finite_size",
                 {"policy": "powered", "lambda": 0.2, "n_and_seeds": n_seeds_by_n,
                  "mode_treat": "lightspeed", "stepping": "event"},
                 {"data": data,
                  "scale_regression": {"x": "log10(N)", "unit": "percentage points per decade of N",
                                       "resample": "seeds within each N",
                                       "slope": slope, "ci_lo": slope_lo, "ci_hi": slope_hi}})


def m_concurrency() -> None:
    """In-flight probe count vs coverage fraction: the mechanism behind 'no fill-time tax'.

    Exponential branching keeps many probes aloft throughout the fill, so a loser's wasted trip
    is one of hundreds in flight and (almost) never sits on the critical path to the last star.
    We record, per coverage bin, the mean number of probes in flight, for instant vs lightspeed.
    """
    seeds = SEEDS[:16]
    n_stars = 500
    lam = 0.2
    # coverage fractions to 0.90 in steps of 0.05, then fine tail bins into the final few percent
    # (referee: the last-star metric lives at 99%+, where the in-flight population thins).
    bins = [round(i / 20, 2) for i in range(1, 19)] + [0.95, 0.97, 0.99]
    series = {"instant": {b: [] for b in bins}, "lightspeed": {b: [] for b in bins}}
    peak = {"instant": [], "lightspeed": []}
    for i, s in enumerate(seeds):
        for mode in ("instant", "lightspeed"):
            r = simulate_swarm(SwarmParams(n_stars=n_stars, policy="powered", probe_speed_c=lam,
                                           speed_cap_c=0.4, stepping="event", coordination=mode), seed=s)
            peak[mode].append(max(st.in_flight for st in r.steps))
            # for each coverage bin, the in_flight at the first step reaching that fraction
            idx = 0
            for b in bins:
                while idx < len(r.steps) and r.steps[idx].fraction_settled < b:
                    idx += 1
                if idx < len(r.steps):
                    series[mode][b].append(r.steps[idx].in_flight)
        print(f"      seed {i + 1}/{len(seeds)}", end="\r", flush=True)
    print(" " * 40, end="\r")
    data = {}
    for mode in ("instant", "lightspeed"):
        meds, clos, chis = [], [], []
        for b in bins:
            xs = series[mode][b]
            if xs:
                m, clo, chi = bootstrap_median_ci(xs)
            else:
                m = clo = chi = None
            meds.append(m); clos.append(clo); chis.append(chi)
        data[mode] = {"coverage": bins, "in_flight_median": meds,
                      "in_flight_ci_lo": clos, "in_flight_ci_hi": chis,
                      "peak_in_flight_median": statistics.median(peak[mode])}
    write_result("concurrency",
                 {"policy": "powered", "lambda": lam, "n_stars": n_stars, "n_seeds": len(seeds),
                  "stepping": "event"},
                 {"data": data})


def m_floor_bracket() -> None:
    """instant / inflight / lightspeed: how much of the decision-site tax survives in-flight relay.

    inflight is the optimistic bound (a probe redirects the instant a beacon overtakes it). We
    report, per Lambda, all three modes' wasted arrivals, redundant travel, and fill time, plus
    the inflight-vs-lightspeed deltas - the referee's requested floor estimate.
    """
    seeds = SEEDS[:48]
    n_stars = 400
    lambdas = [0.05, 0.1, 0.2]
    data = {}
    for lam in lambdas:
        print(f"    Lambda={lam}", flush=True)
        cap = max(0.05, 2 * lam)
        runs = {}
        for mode in ("instant", "lightspeed", "inflight"):
            recs = []
            for i, s in enumerate(seeds):
                r = simulate_swarm(SwarmParams(n_stars=n_stars, policy="powered", probe_speed_c=lam,
                                               speed_cap_c=cap, stepping="event", coordination=mode), seed=s)
                recs.append(record(r))
                print(f"      {mode} seed {i + 1}/{len(seeds)}", end="\r", flush=True)
            runs[mode] = recs
        print(" " * 50, end="\r")
        # paired summaries relative to instant
        def rel(mode: str, field: str) -> dict:
            return summarize([pct_delta(runs[mode][i][field], runs["instant"][i][field]) for i in range(len(seeds))])
        data[str(lam)] = {
            "wasted_arrivals_median": {m: statistics.median([r["wasted_arrivals"] for r in runs[m]]) for m in runs},
            "wasted_travel_pc_median": {m: statistics.median([r["wasted_travel_pc"] for r in runs[m]]) for m in runs},
            "t100_median": {m: statistics.median([r["t100"] for r in runs[m] if r["t100"]]) for m in runs},
            "midflight_aborts_median": {m: statistics.median([r["midflight_aborts"] for r in runs[m]]) for m in runs},
            "travel_pct_over_instant": {m: rel(m, "wasted_travel_pc") for m in ("lightspeed", "inflight")},
            "time_pct_over_instant": {m: rel(m, "t100") for m in ("lightspeed", "inflight")},
            "per_seed": {m: runs[m] for m in runs},
        }
    write_result("floor_bracket",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "modes": ["instant", "lightspeed", "inflight"], "stepping": "event"},
                 {"data": data})


def m_retarget_cap() -> None:
    """Fuel tax vs the max_retargets bookkeeping cap: show the result is insensitive to it."""
    seeds = SEEDS[:32]
    n_stars = 400
    caps = [2, 4, 8, 16, 32]
    data = {}
    for cap in caps:
        print(f"    max_retargets={cap}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event", max_retargets=cap)
        data[str(cap)] = _tax_block(rows)
    write_result("retarget_cap",
                 {"policy": "powered", "lambda": 0.2, "n_stars": n_stars, "n_seeds": len(seeds),
                  "caps": caps, "mode_treat": "lightspeed", "stepping": "event"},
                 {"data": data})


def m_dt_artifact() -> None:
    """Fill-time tax vs fixed timestep, collapsing to ~0 at the event (dt->0) limit."""
    seeds = SEEDS[:32]
    n_stars = 300
    dts = [5000.0, 2000.0, 1000.0, 500.0, 250.0]
    rows_out = []
    for dt in dts + [None]:
        label = f"dt={dt:.0f}" if dt is not None else "event"
        print(f"    {label}", flush=True)
        pens = []
        seeds_pos = 0
        for s in seeds:
            common = dict(n_stars=n_stars, policy="slingshot_nearest")
            common.update({"stepping": "event"} if dt is None else {"stepping": "fixed", "dt_years": dt})
            i = simulate_swarm(SwarmParams(**common, coordination="instant"), seed=s)
            l = simulate_swarm(SwarmParams(**common, coordination="lightspeed"), seed=s)
            if i.t100_years and l.t100_years:
                pens.append((l.t100_years - i.t100_years) / i.t100_years * 100.0)
        kpos, nnz, _ = sign_test_positive(pens)
        rows_out.append({"dt": dt, "label": label, "time_pct": summarize(pens),
                         "seeds_pos": kpos, "seeds_nonzero": nnz})
    write_result("dt_artifact",
                 {"policy": "slingshot_nearest", "n_stars": n_stars, "n_seeds": len(seeds), "dts": dts},
                 {"rows": rows_out})


def m_clumpiness() -> None:
    """Does tax = Lambda survive a CLUMPY (non-uniform) field? [reviewer robustness ask]

    The headline law's derivation assumes a locally uniform claim rate, so the hop length d
    cancels. A reviewer's sharpest critique: in a clumpy field hop length and local claim rate
    correlate, which could break the law's FORM (not just rescale it). We test it with a Thomas
    cluster process at fixed N and mean density (only the spatial arrangement changes), sweeping
    the clump scatter sigma from tight clumps to the uniform limit, crossed with Lambda.

    Theory prediction (v and c are GLOBAL constants, so they factor out of both exposure sums and
    the (d, rate) correlation cancels EXACTLY in the linear regime): clumpiness cannot break the
    v/c FORM through that correlation; it can only SOFTEN the slope downward via saturation of the
    per-hop waste probability in dense clumps (p = 1 - e^{-lambda*W} bending below linear). So we
    expect the through-origin slope a to drop below ~0.96 with clumpiness while staying linear in
    Lambda, UNLESS a temporal-non-stationarity term makes the tax hop-length-dependent. Three
    reported tests: (1) slope a vs measured clumpiness (Clark-Evans R); (2) the wasted-trip ratio
    p_lag/p_perfect stratified by hop length at the clumpiest level (flat in d => the mechanism
    survives); (3) linearity across Lambda. The uniform level is the hard null (must return ~0.96).
    """
    seeds = SEEDS[:48]
    n_stars = 500
    lambdas = [0.05, 0.1, 0.2]
    n_clumps = 25  # ~20 stars/clump at N=500: dense enough to over-subscribe under 2-offspring branching
    # Levels: the exact uniform cube (null), then Thomas clumps tightening from near-uniform to
    # extreme. sigma is the scatter as a fraction of box side; small = tight clumps + voids.
    levels = [
        ("uniform", {}),
        ("sigma0.30", {"n_clumps": n_clumps, "clump_sigma_frac": 0.30}),
        ("sigma0.15", {"n_clumps": n_clumps, "clump_sigma_frac": 0.15}),
        ("sigma0.08", {"n_clumps": n_clumps, "clump_sigma_frac": 0.08}),
        ("sigma0.05", {"n_clumps": n_clumps, "clump_sigma_frac": 0.05}),
    ]
    data = {}
    for label, field_kw in levels:
        print(f"    level={label}", flush=True)
        # Measured clumpiness (Clark-Evans R), median over a seed subset (the field is O(N^2)).
        r_vals = []
        for s in seeds[:16]:
            st = initial_state(SwarmParams(n_stars=n_stars, policy="powered", **field_kw), seed=s)
            r_vals.append(clark_evans_R(st.xs, st.ys, st.zs, SwarmParams(n_stars=n_stars).box_side_pc))
        clumpiness_R = statistics.median(r_vals)
        per_lambda = {}
        # Per-seed fuel tax at each Lambda, to fit a through-origin slope per seed afterwards.
        seed_tax = {i: {} for i in range(len(seeds))}
        for lam in lambdas:
            print(f"      Lambda={lam}", flush=True)
            rows: list[tuple[dict, dict]] = []
            # Aggregate hop-length histograms across seeds (for the stratified d-cancellation test).
            hist = {m: {"settle": [0] * N_HOP_BINS, "wasted": [0] * N_HOP_BINS}
                    for m in ("instant", "lightspeed")}
            base_waste_frac = []
            for i, s in enumerate(seeds):
                common = dict(n_stars=n_stars, policy="powered", probe_speed_c=lam,
                              speed_cap_c=max(0.05, 2 * lam), stepping="event", **field_kw)
                b = simulate_swarm(SwarmParams(**common, coordination="instant"), seed=s)
                t = simulate_swarm(SwarmParams(**common, coordination="lightspeed"), seed=s)
                rows.append((record(b), record(t)))
                for k in range(N_HOP_BINS):
                    hist["instant"]["settle"][k] += b.settle_hop_hist[k]
                    hist["instant"]["wasted"][k] += b.wasted_hop_hist[k]
                    hist["lightspeed"]["settle"][k] += t.settle_hop_hist[k]
                    hist["lightspeed"]["wasted"][k] += t.wasted_hop_hist[k]
                if b.total_arrivals:
                    base_waste_frac.append(b.wasted_arrivals / b.total_arrivals * 100.0)
                seed_tax[i][lam] = pct_delta(t.wasted_arrivals, b.wasted_arrivals)
                print(f"        seed {i + 1}/{len(seeds)}", end="\r", flush=True)
            print(" " * 50, end="\r")
            block = _tax_block(rows)
            block["baseline_waste_frac_pct"] = summarize(base_waste_frac)  # perfect-info waste / all journeys
            block["hop_hist"] = hist
            per_lambda[str(lam)] = block
        # Per-seed through-origin slope a of tax = a*Lambda (predicted 1), then bootstrap over seeds.
        # Fit on FRACTIONAL tax (percent/100) so a ~ 1 means "tax = Lambda" cleanly.
        slopes = [through_origin_slope(
                    lambdas,
                    [(seed_tax[i][lam] / 100.0 if seed_tax[i][lam] is not None else None) for lam in lambdas])
                  for i in range(len(seeds))]
        slopes = [a for a in slopes if a is not None]
        smed, slo, shi = bootstrap_median_ci(slopes)
        data[label] = {
            "clumpiness_R": clumpiness_R,
            "slope_median": smed, "slope_ci_lo": slo, "slope_ci_hi": shi,
            "slope_per_seed": slopes,
            "per_lambda": per_lambda,
        }
    write_result("clumpiness",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "n_clumps": n_clumps, "levels": [lb for lb, _ in levels],
                  "mode_base": "instant", "mode_treat": "lightspeed", "stepping": "event"},
                 {"data": data})


def m_validation() -> None:
    """Nicholson & Forgan quantitative reproduction at the event timestep (single canonical seed)."""
    seed = 0x9E3779B9
    n = 400
    out = {}
    for pol in ("powered", "slingshot_nearest", "slingshot_maxboost"):
        r = simulate_swarm(SwarmParams(n_stars=n, policy=pol, stepping="event"), seed=seed)
        out[pol] = {"t100": r.t100_years, "max_speed_km_s": r.max_probe_speed_km_s}
    speedup = out["powered"]["t100"] / out["slingshot_nearest"]["t100"]
    write_result("validation",
                 {"n_stars": n, "seed": seed, "stepping": "event"},
                 {"policies": out, "nearest_speedup_over_powered": speedup,
                  "nearest_beats_maxboost_on_time": out["slingshot_nearest"]["t100"] < out["slingshot_maxboost"]["t100"]})


def _interior_wasted(rec: dict, start_bin: int) -> int:
    """Wasted arrivals whose target sits at wall distance >= the shell (bins ``start_bin``..end)."""
    return sum(rec["wasted_wall_hist"][start_bin:])


def _interior_settled(rec: dict, start_bin: int) -> int:
    return sum(rec["settle_wall_hist"][start_bin:])


def m_finite_size_interior() -> None:
    """Finite-size EDGE test (referee finding M1): does the with-N tax decline survive when the
    tax is measured on BULK stars only?

    The hard-walled box means edge stars (fewer neighbours, less contention) dilute the tax, and the
    edge fraction falls as N^(-1/3), so the fraction can shrink with N for a purely geometric reason.
    Here each contested arrival is tagged by its target's distance to the nearest wall (the read-only
    ``*_wall_hist`` accumulators), and we recompute the paired fuel tax restricted to interior stars
    at two shells: >= 1 and >= 2 mean-NN distances from any wall. If the all-stars decline is an edge
    artifact it flattens under the interior restriction; if it is genuine bulk saturation it persists.

    Spans 300..200,000 (seeds scaled down with N), matching the committed ``finite_size`` all-stars
    sweep's range so the interior and all-stars declines are compared over an identical ~670x lever
    arm (near-linear since #30, the k-d tree over the unsettled set). The 300..4800 blocks regenerate
    byte-identically; the higher-N points are the edge-vs-bulk test at scale.
    """
    n_seeds_by_n = [(300, 32), (600, 32), (1200, 24), (2400, 16), (4800, 12),
                    (9600, 12), (24000, 10), (48000, 8), (200000, 6)]
    # Shell start-bins for WALL_BIN_EDGES_NN=(0.5,1,1.5,2): shell>=1.0 NN -> bins 2.., shell>=2.0 -> bin 4.
    shells = {"all": 0, "interior_1nn": 2, "interior_2nn": 4}
    data = {}
    per_n: dict[str, dict[int, list]] = {s: {} for s in shells}
    for n, k in n_seeds_by_n:
        print(f"    N={n} ({k} seeds)", flush=True)
        rows = _paired("lightspeed", seeds=SEEDS[:k], n_stars=n, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event")
        block = {"n_seeds": k}
        for name, sb in shells.items():
            if sb == 0:
                tax = [pct_delta(t["wasted_arrivals"], b["wasted_arrivals"]) for b, t in rows]
            else:
                tax = [pct_delta(_interior_wasted(t, sb), _interior_wasted(b, sb)) for b, t in rows]
            per_n[name][n] = tax
            block[name] = summarize(tax)
        # Interior fraction of the settled field (context: how much of the box is "bulk").
        interior_frac = [_interior_settled(b, 2) / b["final_settled"] for b, _ in rows]
        block["interior_2nn_settled_frac"] = summarize(interior_frac)
        data[str(n)] = block
    ns = [n for n, _ in n_seeds_by_n]
    regressions = {}
    for name in shells:
        slope, lo, hi = loglog_slope_ci([math.log10(n) for n in ns], [per_n[name][n] for n in ns])
        regressions[name] = {"slope": slope, "ci_lo": lo, "ci_hi": hi}
    write_result("finite_size_interior",
                 {"policy": "powered", "lambda": 0.2, "n_and_seeds": n_seeds_by_n,
                  "mode_treat": "lightspeed", "stepping": "event",
                  "shells_nn": {"interior_1nn": 1.0, "interior_2nn": 2.0},
                  "note": "tax on interior stars only (target >= shell mean-NN distances from any wall)"},
                 {"data": data,
                  "scale_regression": {"x": "log10(N)", "unit": "percentage points per decade of N",
                                       "resample": "seeds within each N", "by_shell": regressions}})


def m_finite_size_periodic() -> None:
    """Finite-size EDGE test, second control (referee finding M1): the periodic-box cross-check.

    The interior-only test (``m_finite_size_interior``) removes edge stars by masking; this removes
    them by geometry - a periodic (toroidal, minimum-image) box has no walls at all, so every star
    sits in a full neighbourhood. Same Lambda and N range as the hard-walled ``finite_size`` (now
    300..200,000 since #30), so the two slopes are directly comparable: if the hard-wall decline is
    a boundary artifact, the periodic tax stays flat (and higher, since no edge dilutes it); if it is
    genuine bulk saturation, the periodic tax declines too. The 300..4800 blocks regenerate
    byte-identically; the higher-N points settle the question at scale.
    """
    n_seeds_by_n = [(300, 32), (600, 32), (1200, 24), (2400, 16), (4800, 12),
                    (9600, 12), (24000, 10), (48000, 8), (200000, 6)]
    data = {}
    per_n: dict[int, list[float]] = {}
    for n, k in n_seeds_by_n:
        print(f"    N={n} ({k} seeds, periodic)", flush=True)
        rows = _paired("lightspeed", seeds=SEEDS[:k], n_stars=n, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event", periodic=True)
        data[str(n)] = _tax_block(rows)
        per_n[n] = [pct_delta(t["wasted_arrivals"], b["wasted_arrivals"]) for b, t in rows]
    ns = [n for n, _ in n_seeds_by_n]
    slope, lo, hi = loglog_slope_ci([math.log10(n) for n in ns], [per_n[n] for n in ns])
    write_result("finite_size_periodic",
                 {"policy": "powered", "lambda": 0.2, "n_and_seeds": n_seeds_by_n,
                  "mode_treat": "lightspeed", "stepping": "event", "periodic": True},
                 {"data": data,
                  "scale_regression": {"x": "log10(N)", "unit": "percentage points per decade of N",
                                       "resample": "seeds within each N",
                                       "slope": slope, "ci_lo": lo, "ci_hi": hi}})


MEASUREMENTS = {
    "lambda_sweep": m_lambda_sweep,
    "branching": m_branching,
    "energy_tax": m_energy_tax,
    "finite_size": m_finite_size,
    "finite_size_interior": m_finite_size_interior,
    "finite_size_periodic": m_finite_size_periodic,
    "concurrency": m_concurrency,
    "floor_bracket": m_floor_bracket,
    "retarget_cap": m_retarget_cap,
    "dt_artifact": m_dt_artifact,
    "clumpiness": m_clumpiness,
    "validation": m_validation,
}

# Cheap-first order so an interrupted run lands the quick wins early.
ORDER = ["validation", "dt_artifact", "retarget_cap", "energy_tax", "branching",
         "lambda_sweep", "concurrency", "floor_bracket", "clumpiness", "finite_size",
         "finite_size_interior", "finite_size_periodic"]


def main(argv: list[str]) -> None:
    force = "--force" in argv
    names = [a for a in argv if not a.startswith("-")]
    todo = names if names else ORDER
    for name in todo:
        if name not in MEASUREMENTS:
            print(f"unknown measurement: {name} (have: {', '.join(ORDER)})")
            continue
        out = RESULTS_DIR / f"{name}.json"
        if out.exists() and not force:
            print(f"[skip] {name} (exists; --force to recompute)", flush=True)
            continue
        print(f"[run ] {name}", flush=True)
        MEASUREMENTS[name]()
        print(f"[done] {name} -> results/{name}.json", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
