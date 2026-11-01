"""Heavy measurement driver: runs the full referee-revision ensemble and writes committed JSON."""

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
from swarm.sim import _build_kdtree, initial_state

from experiments.stats_util import bootstrap_median_ci, loglog_slope_ci, sign_test_positive

RESULTS_DIR = Path(__file__).resolve().parent / "results"
# v3: per-run records carry ``total_arrivals`` (settlements + wasted trips).
SCHEMA_VERSION = 3

# Deterministic seed ensemble (paired: every mode shares each seed): 512 available, each measurement uses a prefix sized to its cost (see REFERENCES.md, "Measurement design").
SEEDS = [0x9E3779B9 + 2654435761 * k for k in range(512)]


# Per-measurement canonical N for the p2 fixed-N base sweeps (issue #38 follow-up): at-scale N=262,144 for the headline set, else the largest power of two regenerating in <= 1 min (REFERENCES.md, "Measurement design").
P2_FIXED_N = {
    "lambda_sweep": 262144,  # at-scale (1-min N was 2048)
    "branching": 262144,     # at-scale (1-min N was 8192)
    "energy_tax": 2048,      # 57.3s 1-min N (slingshot policies are the costly part; not at-scale)
    "concurrency": 262144,   # at-scale (1-min N was 32768); records the per-event step trace
    "floor_bracket": 262144, # at-scale (1-min N was 32768)
    "retarget_cap": 262144,  # at-scale: the no-plateau finding is sharpest at max N. 723s @ 32 seeds
    "dt_artifact": 262144,   # at-scale (1-min N was 8192; fixed-step rows use the pointer path)
    "clumpiness": 4096,      # 26.4s 1-min N (Thomas-cluster fields are costly; not at-scale)
}


def _p2_fixed_n(name: str) -> int:
    """Canonical p2 star count for a fixed-N base sweep, honouring the SWARM_P2_N_OVERRIDE probe."""
    override = os.environ.get("SWARM_P2_N_OVERRIDE")
    return int(override) if override else P2_FIXED_N[name]


# At-scale finite-size p2 ladder: N = 2^8..2^18 (11 points) with a linear 32->8 seed ramp, shared by the base, interior-edge and periodic-control companions.
_FS_P2_LADDER = [(256, 32), (512, 30), (1024, 27), (2048, 25), (4096, 22), (8192, 20),
                 (16384, 18), (32768, 15), (65536, 13), (131072, 10), (262144, 8)]


# --------------------------------------------------------------------------------------------

_SEED_SLICE: tuple[int, int] | None = None  # (index, count) - set by --seed-slice; else full run


def _apply_slice(seeds: list[int]) -> list[int]:
    """Filter ``seeds`` down to the active seed slice, or return unchanged when no slice."""
    if _SEED_SLICE is None:
        return seeds
    idx, count = _SEED_SLICE
    return [s for i, s in enumerate(seeds) if i % count == idx]


def _shard_suffix() -> str:
    """Filename suffix for the active slice, or empty when running the full ensemble."""
    if _SEED_SLICE is None:
        return ""
    return f".shard{_SEED_SLICE[0]}_{_SEED_SLICE[1]}"


# Measurements that support ``--seed-slice`` / ``--merge`` today.
SHARDABLE = {"finite_size_periodic"}


# --------------------------------------------------------------------------------------------

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
    """One paired (seed, base/treat) run."""
    mode_base, mode_treat, params, seed = args
    # record_steps=False: this worker only reads scalar aggregates via record(), never the per-event trace.
    b = simulate_swarm(SwarmParams(coordination=mode_base, **params), seed=seed, record_steps=False)
    t = simulate_swarm(SwarmParams(coordination=mode_treat, **params), seed=seed, record_steps=False)
    return (record(b), record(t))


def _single_worker(args: tuple[str, dict, int]) -> dict:
    """One single-mode run at a seed."""
    mode, params, seed = args
    r = simulate_swarm(SwarmParams(coordination=mode, **params), seed=seed, record_steps=False)
    return record(r)


def _concurrency_worker(args: tuple[str, dict, int, tuple[float, ...]]) -> tuple[str, int, int, dict[float, int]]:
    """One (mode, seed) concurrency run."""
    mode, params, seed, bins = args
    r = simulate_swarm(SwarmParams(coordination=mode, **params), seed=seed)
    peak = max(st.in_flight for st in r.steps)
    per_bin: dict[float, int] = {}
    idx = 0
    for b in bins:
        while idx < len(r.steps) and r.steps[idx].fraction_settled < b:
            idx += 1
        if idx < len(r.steps):
            per_bin[b] = r.steps[idx].in_flight
    return (mode, seed, peak, per_bin)


def _clumpy_paired_worker(args: tuple[dict, int]) -> tuple[dict, dict, list[int], list[int], list[int], list[int]]:
    """Paired instant/lightspeed clumpy run."""
    params, seed = args
    # Hop histograms come from state counters (carried on the record/result), not from the per-event trace, so record_steps=False is safe here too.
    b = simulate_swarm(SwarmParams(coordination="instant", **params), seed=seed, record_steps=False)
    t = simulate_swarm(SwarmParams(coordination="lightspeed", **params), seed=seed, record_steps=False)
    return (record(b), record(t),
            list(b.settle_hop_hist), list(b.wasted_hop_hist),
            list(t.settle_hop_hist), list(t.wasted_hop_hist))


def _dt_paired_worker(args: tuple[dict, int]) -> tuple[float | None, float | None]:
    """Paired instant/lightspeed dt-artifact run. Returns (t100_instant, t100_lightspeed)."""
    params, seed = args
    i = simulate_swarm(SwarmParams(coordination="instant", **params), seed=seed, record_steps=False)
    l = simulate_swarm(SwarmParams(coordination="lightspeed", **params), seed=seed, record_steps=False)
    return (i.t100_years, l.t100_years)


def _parallel_map(worker, args_list: list, *, label: str = ""):
    """ProcessPoolExecutor.map with the same determinism + progress conventions as ``_paired``."""
    n = len(args_list)
    workers = _worker_count()
    results = []
    if workers <= 1:
        for i, a in enumerate(args_list):
            results.append(worker(a))
            if label:
                print(f"      {label} {i + 1}/{n}", end="\r", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for i, r in enumerate(ex.map(worker, args_list)):
                results.append(r)
                if label:
                    print(f"      {label} {i + 1}/{n} ({workers} workers)", end="\r", flush=True)
    if label:
        print(" " * 60, end="\r")
    return results


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
    """Least-squares slope of ``y = a*x`` through the origin: a = sum(x*y)/sum(x^2)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if y is not None]
    denom = sum(x * x for x, _ in pairs)
    if denom == 0:
        return None
    return sum(x * y for x, y in pairs) / denom


def _kd_nn_other_d2(kd: dict, xs: list[float], ys: list[float], zs: list[float], i: int) -> float:
    """Squared distance from point ``i`` to its nearest OTHER point, via k-d branch-and-bound."""
    px, py, pz = xs[i], ys[i], zs[i]
    axis = kd["axis"]
    split = kd["split"]
    lo = kd["lo"]
    hi = kd["hi"]
    bucket_flat = kd["bucket_flat"]
    bucket_offsets = kd["bucket_offsets"]
    bxmin = kd["bxmin"]
    bxmax = kd["bxmax"]
    bymin = kd["bymin"]
    bymax = kd["bymax"]
    bzmin = kd["bzmin"]
    bzmax = kd["bzmax"]
    best = -1
    best_d2 = float("inf")
    stack = [kd["root"]]
    while stack:
        node = stack.pop()
        dlo2 = 0.0
        t = bxmin[node] - px
        if t > 0.0:
            dlo2 = t * t
        else:
            t = px - bxmax[node]
            if t > 0.0:
                dlo2 = t * t
        t = bymin[node] - py
        if t > 0.0:
            dlo2 += t * t
        else:
            t = py - bymax[node]
            if t > 0.0:
                dlo2 += t * t
        t = bzmin[node] - pz
        if t > 0.0:
            dlo2 += t * t
        else:
            t = pz - bzmax[node]
            if t > 0.0:
                dlo2 += t * t
        if dlo2 > best_d2:
            continue
        ax = axis[node]
        if ax == -1:
            start = int(bucket_offsets[node])
            end = int(bucket_offsets[node + 1])
            for k in range(start, end):
                j = int(bucket_flat[k])
                if j == i:
                    continue
                dx = xs[j] - px
                dy = ys[j] - py
                dz = zs[j] - pz
                d2 = dx * dx + dy * dy + dz * dz
                if d2 < best_d2 or (d2 == best_d2 and best >= 0 and j < best):
                    best_d2 = d2
                    best = j
        else:
            p_ax = px if ax == 0 else (py if ax == 1 else pz)
            if p_ax < split[node]:
                stack.append(hi[node])
                stack.append(lo[node])
            else:
                stack.append(lo[node])
                stack.append(hi[node])
    return best_d2


def clark_evans_R(xs: list[float], ys: list[float], zs: list[float], box_side_pc: float) -> float:
    """Clark-Evans aggregation index R = observed mean NN distance / Poisson expectation (3D)."""
    n = len(xs)
    if n < 2 or box_side_pc <= 0:
        return 1.0
    kd = _build_kdtree(xs, ys, zs)
    total = 0.0
    for i in range(n):
        total += _kd_nn_other_d2(kd, xs, ys, zs, i) ** 0.5
    observed = total / n
    rho = n / (box_side_pc ** 3)
    expected = 0.55396 / (rho ** (1.0 / 3.0))
    return observed / expected


def write_result(name: str, config: dict, payload: dict) -> Path:
    """Write ``<name>.json`` (or ``<name>.shardN_K.json`` when running a seed slice)."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{name}{_shard_suffix()}.json"
    doc: dict = {"schema_version": SCHEMA_VERSION, "generator": "experiments.measure",
                 "measurement": name, "config": config}
    if _SEED_SLICE is not None:
        doc["_shard"] = {"index": _SEED_SLICE[0], "count": _SEED_SLICE[1]}
    doc.update(payload)
    out.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    return out


def write_p2_companion(name: str, config: dict, payload: dict) -> Path:
    """Merge a top-level ``p2`` block into the existing ``<name>.json``, preserving every other key."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{name}.json"
    if not out.exists():
        raise SystemExit(
            f"write_p2_companion({name!r}): expected {out} to exist first "
            f"(run the historical pass before the p2 companion)."
        )
    doc = json.loads(out.read_text())
    p2_block: dict = {"config": config}
    p2_block.update(payload)
    doc["p2"] = p2_block
    out.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    return out


def _p2_has_companion(name: str) -> bool:
    """True if ``<name>.json`` already has a ``p2`` block. Used by the CLI to skip completed work."""
    out = RESULTS_DIR / f"{name}.json"
    if not out.exists():
        return False
    return "p2" in json.loads(out.read_text())


def _paired(mode_treat: str, *, seeds: list[int], mode_base: str = "instant", **params) -> list[tuple[dict, dict]]:
    """Fill each seeded galaxy under ``mode_base`` and ``mode_treat`` (same seed); return records."""
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

def bounce_depth(wasted_arrivals: int, n_stars: int) -> float:
    """Instant-run bounce depth b = W_inst / N (wasted arrivals per star)."""
    if n_stars <= 0:
        raise ValueError(f"n_stars must be positive, got {n_stars}")
    return wasted_arrivals / n_stars


def median_bounce_depth(records: list[dict]) -> float:
    """Median bounce depth over a list of per-seed instant records (each carrying ``wasted_arrivals`` and ``n_stars``)."""
    return statistics.median(bounce_depth(r["wasted_arrivals"], r["n_stars"]) for r in records)


def locate_plateau(b_by_cap: dict[int, float], threshold: float = 0.05) -> int | None:
    """Smallest cap ``k`` whose doubling ``2*k`` no longer moves the bounce depth, or None."""
    for k in sorted(b_by_cap):
        two_k = 2 * k
        if two_k in b_by_cap and (b_by_cap[two_k] - b_by_cap[k]) < threshold:
            return k
    return None


def _instant_bounce_sweep(seeds: list[int], n_stars: int, caps: list[int]) -> dict[int, list[float]]:
    """Instant-only fold at each cap over the seed ensemble; returns ``{cap: [b per seed]}``."""
    args = [("instant",
             dict(n_stars=n_stars, policy="powered", probe_speed_c=0.2, speed_cap_c=0.4,
                  stepping="event", max_retargets=cap),
             seed)
            for cap in caps for seed in seeds]
    recs = _parallel_map(_single_worker, args, label="instant")
    out: dict[int, list[float]] = {}
    idx = 0
    for cap in caps:
        out[cap] = [bounce_depth(recs[idx + j]["wasted_arrivals"], n_stars) for j in range(len(seeds))]
        idx += len(seeds)
    return out


def locate_plateau_report(n_stars: int, *, caps: list[int] | None = None,
                          seeds: list[int] | None = None, threshold: float = 0.05,
                          paired: bool = False) -> dict:
    """Locate cap*(N) from instant-only bounce depth; optionally one paired run for the tax."""
    caps = sorted(set(caps if caps is not None else [8, 16, 32]))
    seeds = seeds if seeds is not None else SEEDS[:8]
    sweep = _instant_bounce_sweep(seeds, n_stars, caps)
    b_by_cap = {cap: statistics.median(vs) for cap, vs in sweep.items()}
    cap_star = locate_plateau(b_by_cap, threshold)
    ladder: list[dict] = []
    prev: float | None = None
    for cap in caps:
        b = b_by_cap[cap]
        ladder.append({"cap": cap, "b_median": b, "delta_b": None if prev is None else b - prev})
        prev = b
    report = {"n_stars": n_stars, "n_seeds": len(seeds), "caps": caps,
              "threshold": threshold, "ladder": ladder, "cap_star": cap_star, "paired": None}
    if paired and cap_star is not None:
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event", max_retargets=cap_star)
        report["paired"] = {"cap": cap_star, "fuel_pct": _tax_block(rows)["fuel_pct"]}
    return report


def _print_plateau_report(rep: dict) -> None:
    """Human-readable dump of a ``locate_plateau_report`` result."""
    print(f"plateau locator: N={rep['n_stars']}, {rep['n_seeds']} seeds, "
          f"threshold={rep['threshold']} (b = W_inst/N)")
    print(f"  {'cap':>5}  {'b_median':>10}  {'delta_b':>10}")
    for row in rep["ladder"]:
        db = "" if row["delta_b"] is None else f"{row['delta_b']:+.3f}"
        print(f"  {row['cap']:>5}  {row['b_median']:>10.3f}  {db:>10}")
    if rep["cap_star"] is None:
        print("  cap* = none: no plateau in the tested ladder (cap is a lower bound; "
              "extend --plateau-caps or run larger caps)")
    else:
        print(f"  cap* = {rep['cap_star']} (bounce depth flat past here; "
              f"run one paired measurement here for the tax value)")
    if rep["paired"] is not None:
        fp = rep["paired"]["fuel_pct"]
        print(f"  paired tax at cap {rep['paired']['cap']}: "
              f"fuel {fp['median']:.3f}% (95% CI {fp['ci_lo']:.3f}..{fp['ci_hi']:.3f})")


# --------------------------------------------------------------------------------------------

def m_lambda_sweep() -> None:
    """Headline: fuel/time/travel/energy tax vs Lambda = v/c (powered, event, lightspeed vs instant)."""
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


def p2_lambda_sweep() -> None:
    """P2 companion to ``m_lambda_sweep``: at-scale N=262,144, 128 seeds (see P2_FIXED_N)."""
    seeds = SEEDS[:128]
    n_stars = _p2_fixed_n("lambda_sweep")
    lambdas = [0.01, 0.03, 0.05, 0.1, 0.2]
    data = {}
    for lam in lambdas:
        print(f"    [p2] Lambda={lam}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                       probe_speed_c=lam, speed_cap_c=max(0.05, 2 * lam), stepping="event")
        data[str(lam)] = _tax_block(rows)
    write_p2_companion("lambda_sweep",
                       {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                        "lambdas": lambdas, "mode_base": "instant", "mode_treat": "lightspeed",
                        "stepping": "event"},
                       {"data": data})


def m_lambda_sweep_scale() -> None:
    """N=200k companion to the headline speed sweep: does tax ~ v/c linearity hold at scale?"""
    seeds = SEEDS[:8]
    n_stars = 200_000
    lambdas = [0.01, 0.03, 0.05, 0.1, 0.2]
    data = {}
    for lam in lambdas:
        print(f"    Lambda={lam}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                       probe_speed_c=lam, speed_cap_c=max(0.05, 2 * lam), stepping="event")
        data[str(lam)] = _tax_block(rows)
    write_result("lambda_sweep_scale",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "mode_base": "instant", "mode_treat": "lightspeed",
                  "stepping": "event"},
                 {"data": data})


def p2_lambda_sweep_scale() -> None:
    """P2 companion to ``m_lambda_sweep_scale``: at-scale N=524_288."""
    seeds = SEEDS[:8]
    n_stars = 524_288
    lambdas = [0.01, 0.03, 0.05, 0.1, 0.2]
    data = {}
    for lam in lambdas:
        print(f"    [p2] Lambda={lam}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                       probe_speed_c=lam, speed_cap_c=max(0.05, 2 * lam), stepping="event")
        data[str(lam)] = _tax_block(rows)
    write_p2_companion("lambda_sweep_scale",
                       {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                        "lambdas": lambdas, "mode_base": "instant", "mode_treat": "lightspeed",
                        "stepping": "event"},
                       {"data": data})


def m_branching() -> None:
    """Fuel/time/energy tax vs the replication branching factor (offspring per settlement)."""
    seeds = SEEDS[:32]
    n_stars = 400
    # Swept high (to 16) so the saturation claim is tested, not asserted from a 3-point plateau:
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


def p2_branching() -> None:
    """P2 companion to ``m_branching``: N=400 -> the 1-min-ceiling p2 N (see P2_FIXED_N)."""
    seeds = SEEDS[:32]
    n_stars = _p2_fixed_n("branching")
    offspring = [2, 3, 4, 8, 16]
    lambdas = [0.05, 0.2]
    data = {}
    for lam in lambdas:
        for off in offspring:
            key = f"lam{lam}_off{off}"
            print(f"    [p2] Lambda={lam} offspring={off}", flush=True)
            rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                           probe_speed_c=lam, speed_cap_c=max(0.05, 2 * lam),
                           offspring_per_settlement=off, stepping="event")
            data[key] = _tax_block(rows)
    write_p2_companion("branching",
                       {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                        "lambdas": lambdas, "offspring": offspring, "mode_treat": "lightspeed",
                        "stepping": "event"},
                       {"data": data})


def m_branching_scale() -> None:
    """N=200k companion to the branching sweep: does the tax-grows-with-branching claim hold at scale?"""
    seeds = SEEDS[:6]
    n_stars = 200_000
    offspring = [2, 3, 4, 8]
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
    write_result("branching_scale",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "offspring": offspring, "mode_treat": "lightspeed",
                  "stepping": "event"},
                 {"data": data})


def p2_branching_scale() -> None:
    """P2 companion to ``m_branching_scale``: N=200_000 -> N=262_144 (next p2 above 200k)."""
    seeds = SEEDS[:6]
    n_stars = 524_288
    offspring = [2, 3, 4, 8]
    lambdas = [0.05, 0.2]
    data = {}
    for lam in lambdas:
        for off in offspring:
            key = f"lam{lam}_off{off}"
            print(f"    [p2] Lambda={lam} offspring={off}", flush=True)
            rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                           probe_speed_c=lam, speed_cap_c=max(0.05, 2 * lam),
                           offspring_per_settlement=off, stepping="event")
            data[key] = _tax_block(rows)
    write_p2_companion("branching_scale",
                       {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                        "lambdas": lambdas, "offspring": offspring, "mode_treat": "lightspeed",
                        "stepping": "event"},
                       {"data": data})


def m_energy_tax() -> None:
    """Energy-weighted tax per policy: count-tax vs (1/2)v^2-weighted tax (1x and 2x brackets)."""
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


def p2_energy_tax() -> None:
    """P2 companion to ``m_energy_tax``: N=400 -> the 1-min-ceiling p2 N (see P2_FIXED_N)."""
    seeds = SEEDS[:32]
    n_stars = _p2_fixed_n("energy_tax")
    policies = ["powered", "slingshot_nearest", "slingshot_maxboost"]
    data = {}
    for pol in policies:
        print(f"    [p2] policy={pol}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy=pol, stepping="event")
        block = _tax_block(rows)
        v_wasted = [t["mean_wasted_speed_km_s"] for _, t in rows if t["mean_wasted_speed_km_s"] > 0]
        block["mean_wasted_speed_km_s"] = statistics.median(v_wasted) if v_wasted else 0.0
        block["lambda_eff"] = (block["mean_wasted_speed_km_s"] * KM_S_TO_PC_YR / C_PC_PER_YEAR)
        data[pol] = block
    write_p2_companion("energy_tax",
                       {"policies": policies, "n_stars": n_stars, "n_seeds": len(seeds),
                        "mode_treat": "lightspeed", "stepping": "event",
                        "note": "energy_pct_1x/2x are the flyby/rendezvous bracket; relativistic excess < 3.1% to 0.2c"},
                       {"data": data})


def m_finite_size() -> None:
    """Fuel tax % vs system size over a 16x span (300..4800), powered, Lambda=0.2, event."""
    # High-seed sweep reaching N=200,000 (near-linear since #30), with seeds scaled down as N grows to hold the median tight.
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


def p2_finite_size() -> None:
    """P2 companion to ``m_finite_size``: the full power-of-two ladder 256..262,144."""
    n_seeds_by_n = _FS_P2_LADDER
    data = {}
    per_n_fuel: dict[int, list[float]] = {}
    for n, k in n_seeds_by_n:
        print(f"    [p2] N={n} ({k} seeds)", flush=True)
        rows = _paired("lightspeed", seeds=SEEDS[:k], n_stars=n, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event")
        data[str(n)] = _tax_block(rows)
        per_n_fuel[n] = [pct_delta(t["wasted_arrivals"], b["wasted_arrivals"]) for b, t in rows]
    ns = [n for n, _ in n_seeds_by_n]
    slope, slope_lo, slope_hi = loglog_slope_ci([math.log10(n) for n in ns],
                                                [per_n_fuel[n] for n in ns])
    write_p2_companion("finite_size",
                       {"policy": "powered", "lambda": 0.2, "n_and_seeds": n_seeds_by_n,
                        "mode_treat": "lightspeed", "stepping": "event"},
                       {"data": data,
                        "scale_regression": {"x": "log10(N)",
                                             "unit": "percentage points per decade of N",
                                             "resample": "seeds within each N",
                                             "slope": slope, "ci_lo": slope_lo, "ci_hi": slope_hi}})


def _concurrency_ensemble(seeds: list[int], n_stars: int, lam: float,
                          bins: list[float]) -> dict:
    """Run the paired instant/lightspeed concurrency ensemble in parallel over (seed, mode)."""
    modes = ("instant", "lightspeed")
    params = dict(n_stars=n_stars, policy="powered", probe_speed_c=lam,
                  speed_cap_c=max(0.05, 2 * lam), stepping="event")
    args = [(mode, params, s, tuple(bins)) for s in seeds for mode in modes]
    results = _parallel_map(_concurrency_worker, args, label="seed")
    # Bucket back per mode, preserving seed order (args are emitted seed-then-mode, so the mode
    series = {m: {b: [] for b in bins} for m in modes}
    peak = {m: [] for m in modes}
    seen: dict[str, set[int]] = {m: set() for m in modes}
    for mode, seed, p, per_bin in results:
        if seed in seen[mode]:
            continue  # defensive: never expected, executor.map is one-to-one
        seen[mode].add(seed)
        peak[mode].append(p)
        for b, v in per_bin.items():
            series[mode][b].append(v)
    data = {}
    for mode in modes:
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
                      "peak_in_flight_median": statistics.median(peak[mode]) if peak[mode] else None}
    return data


def m_concurrency() -> None:
    """In-flight probe count vs coverage fraction: the mechanism behind 'no fill-time tax'."""
    seeds = SEEDS[:16]
    n_stars = 500
    lam = 0.2
    # coverage fractions to 0.90 in steps of 0.05, then fine tail bins into the final few percent
    bins = [round(i / 20, 2) for i in range(1, 19)] + [0.95, 0.97, 0.99]
    data = _concurrency_ensemble(seeds, n_stars, lam, bins)
    write_result("concurrency",
                 {"policy": "powered", "lambda": lam, "n_stars": n_stars, "n_seeds": len(seeds),
                  "stepping": "event"},
                 {"data": data})


def p2_concurrency() -> None:
    """P2 companion to ``m_concurrency``: at-scale N=262,144, 32 seeds (see P2_FIXED_N)."""
    seeds = SEEDS[:32]
    n_stars = _p2_fixed_n("concurrency")
    lam = 0.2
    bins = [round(i / 20, 2) for i in range(1, 19)] + [0.95, 0.97, 0.99]
    data = _concurrency_ensemble(seeds, n_stars, lam, bins)
    write_p2_companion("concurrency",
                       {"policy": "powered", "lambda": lam, "n_stars": n_stars, "n_seeds": len(seeds),
                        "stepping": "event"},
                       {"data": data})


def m_concurrency_scale() -> None:
    """N=200k companion to the concurrency sweep: does the many-probes-in-flight mechanism hold at the honest lever arm?"""
    seeds = SEEDS[:8]
    n_stars = 200_000
    lam = 0.2
    bins = [round(i / 20, 2) for i in range(1, 19)] + [0.95, 0.97, 0.99]
    data = _concurrency_ensemble(seeds, n_stars, lam, bins)
    write_result("concurrency_scale",
                 {"policy": "powered", "lambda": lam, "n_stars": n_stars, "n_seeds": len(seeds),
                  "stepping": "event"},
                 {"data": data})


def p2_concurrency_scale() -> None:
    """P2 companion to ``m_concurrency_scale``: N=200_000 -> N=262_144 (next p2 above 200k)."""
    seeds = SEEDS[:8]
    n_stars = 524_288
    lam = 0.2
    bins = [round(i / 20, 2) for i in range(1, 19)] + [0.95, 0.97, 0.99]
    data = _concurrency_ensemble(seeds, n_stars, lam, bins)
    write_p2_companion("concurrency_scale",
                       {"policy": "powered", "lambda": lam, "n_stars": n_stars, "n_seeds": len(seeds),
                        "stepping": "event"},
                       {"data": data})


def _floor_bracket_body(seeds: list[int], n_stars: int, lambdas: list[float]) -> dict:
    """Shared floor-bracket ensemble body (used by ``m_floor_bracket`` and its p2 companion)."""
    data = {}
    modes = ("instant", "lightspeed", "inflight")
    for lam in lambdas:
        print(f"    Lambda={lam}", flush=True)
        cap = max(0.05, 2 * lam)
        params = dict(n_stars=n_stars, policy="powered", probe_speed_c=lam,
                      speed_cap_c=cap, stepping="event")
        args = [(mode, params, s) for mode in modes for s in seeds]
        recs = _parallel_map(_single_worker, args, label=f"lam={lam}")
        runs = {mode: recs[i * len(seeds):(i + 1) * len(seeds)] for i, mode in enumerate(modes)}
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
    return data


def m_floor_bracket() -> None:
    """instant / inflight / lightspeed: how much of the decision-site tax survives in-flight relay."""
    seeds = SEEDS[:48]
    n_stars = 400
    lambdas = [0.05, 0.1, 0.2]
    data = _floor_bracket_body(seeds, n_stars, lambdas)
    write_result("floor_bracket",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "modes": ["instant", "lightspeed", "inflight"], "stepping": "event"},
                 {"data": data})


def p2_floor_bracket() -> None:
    """P2 companion to ``m_floor_bracket``: at-scale N=262,144, 32 seeds (see P2_FIXED_N)."""
    seeds = SEEDS[:32]
    n_stars = _p2_fixed_n("floor_bracket")
    lambdas = [0.05, 0.1, 0.2]
    data = _floor_bracket_body(seeds, n_stars, lambdas)
    write_p2_companion("floor_bracket",
                       {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                        "lambdas": lambdas, "modes": ["instant", "lightspeed", "inflight"],
                        "stepping": "event"},
                       {"data": data})


def m_floor_bracket_scale() -> None:
    """N=200k companion to the floor bracket: how much of the (already tiny, ~1.5%) tax survives in-flight relay at scale?"""
    seeds = SEEDS[:8]
    n_stars = 200_000
    lambdas = [0.05, 0.1, 0.2]
    data = _floor_bracket_body(seeds, n_stars, lambdas)
    write_result("floor_bracket_scale",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "modes": ["instant", "lightspeed", "inflight"], "stepping": "event"},
                 {"data": data})


def p2_floor_bracket_scale() -> None:
    """P2 companion to ``m_floor_bracket_scale``: at-scale N=524_288."""
    seeds = SEEDS[:8]
    n_stars = 524_288
    lambdas = [0.05, 0.1, 0.2]
    data = _floor_bracket_body(seeds, n_stars, lambdas)
    write_p2_companion("floor_bracket_scale",
                       {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                        "lambdas": lambdas, "modes": ["instant", "lightspeed", "inflight"],
                        "stepping": "event"},
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


def p2_retarget_cap() -> None:
    """P2 companion to ``m_retarget_cap``: N=400 -> the 1-min-ceiling p2 N (see P2_FIXED_N)."""
    seeds = SEEDS[:32]
    n_stars = _p2_fixed_n("retarget_cap")
    caps = [2, 4, 8, 16, 32]
    data = {}
    for cap in caps:
        print(f"    [p2] max_retargets={cap}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event", max_retargets=cap)
        data[str(cap)] = _tax_block(rows)
    write_p2_companion("retarget_cap",
                       {"policy": "powered", "lambda": 0.2, "n_stars": n_stars, "n_seeds": len(seeds),
                        "caps": caps, "mode_treat": "lightspeed", "stepping": "event"},
                       {"data": data})


def m_retarget_cap_scale() -> None:
    """N=200k companion to the re-target-cap sweep: does insensitivity to the bookkeeping cap hold at scale?"""
    seeds = SEEDS[:8]
    n_stars = 200_000
    caps = [2, 4, 8, 16, 32]
    data = {}
    for cap in caps:
        print(f"    max_retargets={cap}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event", max_retargets=cap)
        data[str(cap)] = _tax_block(rows)
    write_result("retarget_cap_scale",
                 {"policy": "powered", "lambda": 0.2, "n_stars": n_stars, "n_seeds": len(seeds),
                  "caps": caps, "mode_treat": "lightspeed", "stepping": "event"},
                 {"data": data})


def p2_retarget_cap_scale() -> None:
    """P2 companion to ``m_retarget_cap_scale``: N=200_000 -> N=262_144 (next p2 above 200k)."""
    seeds = SEEDS[:8]
    n_stars = 262_144
    caps = [2, 4, 8, 16, 32]
    data = {}
    for cap in caps:
        print(f"    [p2] max_retargets={cap}", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n_stars, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event", max_retargets=cap)
        data[str(cap)] = _tax_block(rows)
    write_p2_companion("retarget_cap_scale",
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
        common = dict(n_stars=n_stars, policy="slingshot_nearest")
        common.update({"stepping": "event"} if dt is None else {"stepping": "fixed", "dt_years": dt})
        # Parallel over seeds: each seed spawns a paired instant/lightspeed run in the worker.
        args = [(common, s) for s in seeds]
        pairs = _parallel_map(_dt_paired_worker, args, label=label)
        pens = [((l - i) / i * 100.0) for (i, l) in pairs if i and l]
        kpos, nnz, _ = sign_test_positive(pens)
        rows_out.append({"dt": dt, "label": label, "time_pct": summarize(pens),
                         "seeds_pos": kpos, "seeds_nonzero": nnz})
    write_result("dt_artifact",
                 {"policy": "slingshot_nearest", "n_stars": n_stars, "n_seeds": len(seeds), "dts": dts},
                 {"rows": rows_out})


def p2_dt_artifact() -> None:
    """P2 companion to ``m_dt_artifact``: N=300 -> N=512 (70% larger, cleanly p2)."""
    seeds = SEEDS[:32]
    n_stars = _p2_fixed_n("dt_artifact")
    dts = [5000.0, 2000.0, 1000.0, 500.0, 250.0]
    rows_out = []
    for dt in dts + [None]:
        label = f"dt={dt:.0f}" if dt is not None else "event"
        print(f"    [p2] {label}", flush=True)
        common = dict(n_stars=n_stars, policy="slingshot_nearest")
        common.update({"stepping": "event"} if dt is None else {"stepping": "fixed", "dt_years": dt})
        args = [(common, s) for s in seeds]
        pairs = _parallel_map(_dt_paired_worker, args, label=label)
        pens = [((l - i) / i * 100.0) for (i, l) in pairs if i and l]
        kpos, nnz, _ = sign_test_positive(pens)
        rows_out.append({"dt": dt, "label": label, "time_pct": summarize(pens),
                         "seeds_pos": kpos, "seeds_nonzero": nnz})
    write_p2_companion("dt_artifact",
                       {"policy": "slingshot_nearest", "n_stars": n_stars, "n_seeds": len(seeds), "dts": dts},
                       {"rows": rows_out})


def _clumpiness_run(seeds: list[int], n_stars: int, lambdas: list[float],
                    n_clumps: int, levels: list[tuple[str, dict]], r_seed_count: int = 16) -> dict:
    """Shared clumpy-field sweep body, used by ``m_clumpiness`` (N=500) and its scale companion."""
    data = {}
    for label, field_kw in levels:
        print(f"    level={label}", flush=True)
        # Measured clumpiness (Clark-Evans R), median over a seed subset (near-O(N log N) via k-d tree).
        r_vals = []
        for s in seeds[:r_seed_count]:
            st = initial_state(SwarmParams(n_stars=n_stars, policy="powered", **field_kw), seed=s)
            r_vals.append(clark_evans_R(st.xs, st.ys, st.zs, SwarmParams(n_stars=n_stars).box_side_pc))
        clumpiness_R = statistics.median(r_vals)
        per_lambda = {}
        # Per-seed fuel tax at each Lambda, to fit a through-origin slope per seed afterwards.
        seed_tax = {i: {} for i in range(len(seeds))}
        for lam in lambdas:
            print(f"      Lambda={lam}", flush=True)
            # Aggregate hop-length histograms across seeds (for the stratified d-cancellation test).
            hist = {m: {"settle": [0] * N_HOP_BINS, "wasted": [0] * N_HOP_BINS}
                    for m in ("instant", "lightspeed")}
            base_waste_frac = []
            params = dict(n_stars=n_stars, policy="powered", probe_speed_c=lam,
                          speed_cap_c=max(0.05, 2 * lam), stepping="event", **field_kw)
            # Parallel over seeds: each worker runs the paired instant/lightspeed pair AND returns
            args = [(params, s) for s in seeds]
            results = _parallel_map(_clumpy_paired_worker, args, label=f"lam={lam}")
            rows: list[tuple[dict, dict]] = []
            for i, (rec_b, rec_t, b_settle, b_wasted, t_settle, t_wasted) in enumerate(results):
                rows.append((rec_b, rec_t))
                for k in range(N_HOP_BINS):
                    hist["instant"]["settle"][k] += b_settle[k]
                    hist["instant"]["wasted"][k] += b_wasted[k]
                    hist["lightspeed"]["settle"][k] += t_settle[k]
                    hist["lightspeed"]["wasted"][k] += t_wasted[k]
                if rec_b["total_arrivals"]:
                    base_waste_frac.append(rec_b["wasted_arrivals"] / rec_b["total_arrivals"] * 100.0)
                seed_tax[i][lam] = pct_delta(rec_t["wasted_arrivals"], rec_b["wasted_arrivals"])
            block = _tax_block(rows)
            block["baseline_waste_frac_pct"] = summarize(base_waste_frac)  # perfect-info waste / all journeys
            block["hop_hist"] = hist
            per_lambda[str(lam)] = block
        # Per-seed through-origin slope a of tax = a*Lambda (predicted 1), then bootstrap over seeds.
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
    return data


def m_clumpiness() -> None:
    """Does tax = Lambda survive a CLUMPY (non-uniform) field? [reviewer robustness ask]."""
    seeds = SEEDS[:48]
    n_stars = 500
    lambdas = [0.05, 0.1, 0.2]
    n_clumps = 25  # ~20 stars/clump at N=500: dense enough to over-subscribe under 2-offspring branching
    # Levels: the exact uniform cube (null), then Thomas clumps tightening from near-uniform to
    levels = [
        ("uniform", {}),
        ("sigma0.30", {"n_clumps": n_clumps, "clump_sigma_frac": 0.30}),
        ("sigma0.15", {"n_clumps": n_clumps, "clump_sigma_frac": 0.15}),
        ("sigma0.08", {"n_clumps": n_clumps, "clump_sigma_frac": 0.08}),
        ("sigma0.05", {"n_clumps": n_clumps, "clump_sigma_frac": 0.05}),
    ]
    data = _clumpiness_run(seeds, n_stars, lambdas, n_clumps, levels)
    write_result("clumpiness",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "n_clumps": n_clumps, "levels": [lb for lb, _ in levels],
                  "mode_base": "instant", "mode_treat": "lightspeed", "stepping": "event"},
                 {"data": data})


def p2_clumpiness() -> None:
    """P2 companion to ``m_clumpiness``: N=500 -> the 1-min-ceiling p2 N (see P2_FIXED_N). Same n_clumps=25."""
    seeds = SEEDS[:48]
    n_stars = _p2_fixed_n("clumpiness")
    lambdas = [0.05, 0.1, 0.2]
    n_clumps = 25
    levels = [
        ("uniform", {}),
        ("sigma0.30", {"n_clumps": n_clumps, "clump_sigma_frac": 0.30}),
        ("sigma0.15", {"n_clumps": n_clumps, "clump_sigma_frac": 0.15}),
        ("sigma0.08", {"n_clumps": n_clumps, "clump_sigma_frac": 0.08}),
        ("sigma0.05", {"n_clumps": n_clumps, "clump_sigma_frac": 0.05}),
    ]
    data = _clumpiness_run(seeds, n_stars, lambdas, n_clumps, levels)
    write_p2_companion("clumpiness",
                       {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                        "lambdas": lambdas, "n_clumps": n_clumps, "levels": [lb for lb, _ in levels],
                        "mode_base": "instant", "mode_treat": "lightspeed", "stepping": "event"},
                       {"data": data})


def m_clumpiness_scale() -> None:
    """N=200k companion to the clumpy-field sweep: does tax = Lambda still hold on non-uniform fields at scale?"""
    seeds = SEEDS[:8]
    n_stars = 200_000
    lambdas = [0.05, 0.1, 0.2]
    n_clumps = 25
    levels = [
        ("uniform", {}),
        ("sigma0.30", {"n_clumps": n_clumps, "clump_sigma_frac": 0.30}),
        ("sigma0.15", {"n_clumps": n_clumps, "clump_sigma_frac": 0.15}),
        ("sigma0.08", {"n_clumps": n_clumps, "clump_sigma_frac": 0.08}),
        ("sigma0.05", {"n_clumps": n_clumps, "clump_sigma_frac": 0.05}),
    ]
    data = _clumpiness_run(seeds, n_stars, lambdas, n_clumps, levels, r_seed_count=8)
    write_result("clumpiness_scale",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "n_clumps": n_clumps, "levels": [lb for lb, _ in levels],
                  "mode_base": "instant", "mode_treat": "lightspeed", "stepping": "event"},
                 {"data": data})


def p2_clumpiness_scale() -> None:
    """P2 companion to ``m_clumpiness_scale``: N=200_000 -> N=262_144 (next p2 above 200k)."""
    seeds = SEEDS[:8]
    n_stars = 262_144
    lambdas = [0.05, 0.1, 0.2]
    n_clumps = 25
    levels = [
        ("uniform", {}),
        ("sigma0.30", {"n_clumps": n_clumps, "clump_sigma_frac": 0.30}),
        ("sigma0.15", {"n_clumps": n_clumps, "clump_sigma_frac": 0.15}),
        ("sigma0.08", {"n_clumps": n_clumps, "clump_sigma_frac": 0.08}),
        ("sigma0.05", {"n_clumps": n_clumps, "clump_sigma_frac": 0.05}),
    ]
    data = _clumpiness_run(seeds, n_stars, lambdas, n_clumps, levels, r_seed_count=8)
    write_p2_companion("clumpiness_scale",
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


def p2_validation() -> None:
    """P2 companion to ``m_validation``: N=400 -> N=512 (28% larger, cleanly p2)."""
    seed = 0x9E3779B9
    n = 512
    out = {}
    for pol in ("powered", "slingshot_nearest", "slingshot_maxboost"):
        r = simulate_swarm(SwarmParams(n_stars=n, policy=pol, stepping="event"), seed=seed)
        out[pol] = {"t100": r.t100_years, "max_speed_km_s": r.max_probe_speed_km_s}
    speedup = out["powered"]["t100"] / out["slingshot_nearest"]["t100"]
    write_p2_companion("validation",
                       {"n_stars": n, "seed": seed, "stepping": "event"},
                       {"policies": out, "nearest_speedup_over_powered": speedup,
                        "nearest_beats_maxboost_on_time": out["slingshot_nearest"]["t100"] < out["slingshot_maxboost"]["t100"]})


def _interior_wasted(rec: dict, start_bin: int) -> int:
    """Wasted arrivals whose target sits at wall distance >= the shell (bins ``start_bin``..end)."""
    return sum(rec["wasted_wall_hist"][start_bin:])


def _interior_settled(rec: dict, start_bin: int) -> int:
    return sum(rec["settle_wall_hist"][start_bin:])


def m_finite_size_interior() -> None:
    """Finite-size EDGE test (referee finding M1): does the with-N tax decline survive when the tax is measured on BULK stars only?"""
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


def p2_finite_size_interior() -> None:
    """P2 companion to ``m_finite_size_interior``: p2 ladder matched to the historical seed pattern."""
    n_seeds_by_n = _FS_P2_LADDER
    shells = {"all": 0, "interior_1nn": 2, "interior_2nn": 4}
    data = {}
    per_n: dict[str, dict[int, list]] = {s: {} for s in shells}
    for n, k in n_seeds_by_n:
        print(f"    [p2] N={n} ({k} seeds)", flush=True)
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
        interior_frac = [_interior_settled(b, 2) / b["final_settled"] for b, _ in rows]
        block["interior_2nn_settled_frac"] = summarize(interior_frac)
        data[str(n)] = block
    ns = [n for n, _ in n_seeds_by_n]
    regressions = {}
    for name in shells:
        slope, lo, hi = loglog_slope_ci([math.log10(n) for n in ns], [per_n[name][n] for n in ns])
        regressions[name] = {"slope": slope, "ci_lo": lo, "ci_hi": hi}
    write_p2_companion("finite_size_interior",
                       {"policy": "powered", "lambda": 0.2, "n_and_seeds": n_seeds_by_n,
                        "mode_treat": "lightspeed", "stepping": "event",
                        "shells_nn": {"interior_1nn": 1.0, "interior_2nn": 2.0},
                        "note": "tax on interior stars only (target >= shell mean-NN distances from any wall)"},
                       {"data": data,
                        "scale_regression": {"x": "log10(N)",
                                             "unit": "percentage points per decade of N",
                                             "resample": "seeds within each N",
                                             "by_shell": regressions}})


def m_finite_size_periodic() -> None:
    """Finite-size EDGE test, second control (referee finding M1): the periodic-box cross-check."""
    n_seeds_by_n = [(300, 32), (600, 32), (1200, 24), (2400, 16), (4800, 12),
                    (9600, 12), (24000, 10), (48000, 8), (200000, 6)]
    data = {}
    per_n: dict[int, list[float]] = {}
    for n, k in n_seeds_by_n:
        seeds = _apply_slice(SEEDS[:k])
        if not seeds:
            # Under an aggressive slice (K larger than k) some N's shard may be empty; the merge step tolerates this and reconstructs from other shards.
            data[str(n)] = _tax_block([])
            per_n[n] = []
            print(f"    N={n} (skipped: empty slice)", flush=True)
            continue
        label = f"    N={n} ({len(seeds)} seeds, periodic)"
        if _SEED_SLICE is not None:
            label += f" [shard {_SEED_SLICE[0]}/{_SEED_SLICE[1]}]"
        print(label, flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event", periodic=True)
        data[str(n)] = _tax_block(rows)
        per_n[n] = [pct_delta(t["wasted_arrivals"], b["wasted_arrivals"]) for b, t in rows]
    ns = [n for n, _ in n_seeds_by_n]
    # Under a shard, scale_regression is a subset regression; the merge step recomputes it from the concatenated per-seed data.
    if _SEED_SLICE is None:
        slope, lo, hi = loglog_slope_ci([math.log10(n) for n in ns], [per_n[n] for n in ns])
    else:
        slope = lo = hi = None
    write_result("finite_size_periodic",
                 {"policy": "powered", "lambda": 0.2, "n_and_seeds": n_seeds_by_n,
                  "mode_treat": "lightspeed", "stepping": "event", "periodic": True},
                 {"data": data,
                  "scale_regression": {"x": "log10(N)", "unit": "percentage points per decade of N",
                                       "resample": "seeds within each N",
                                       "slope": slope, "ci_lo": lo, "ci_hi": hi}})


def p2_finite_size_periodic() -> None:
    """P2 companion to ``m_finite_size_periodic``: p2 ladder matched to the historical seed pattern."""
    n_seeds_by_n = _FS_P2_LADDER
    data = {}
    per_n: dict[int, list[float]] = {}
    for n, k in n_seeds_by_n:
        seeds = SEEDS[:k]
        print(f"    [p2] N={n} ({len(seeds)} seeds, periodic)", flush=True)
        rows = _paired("lightspeed", seeds=seeds, n_stars=n, policy="powered",
                       probe_speed_c=0.2, speed_cap_c=0.4, stepping="event", periodic=True)
        data[str(n)] = _tax_block(rows)
        per_n[n] = [pct_delta(t["wasted_arrivals"], b["wasted_arrivals"]) for b, t in rows]
    ns = [n for n, _ in n_seeds_by_n]
    slope, lo, hi = loglog_slope_ci([math.log10(n) for n in ns], [per_n[n] for n in ns])
    write_p2_companion("finite_size_periodic",
                       {"policy": "powered", "lambda": 0.2, "n_and_seeds": n_seeds_by_n,
                        "mode_treat": "lightspeed", "stepping": "event", "periodic": True},
                       {"data": data,
                        "scale_regression": {"x": "log10(N)",
                                             "unit": "percentage points per decade of N",
                                             "resample": "seeds within each N",
                                             "slope": slope, "ci_lo": lo, "ci_hi": hi}})


MEASUREMENTS = {
    "lambda_sweep": m_lambda_sweep,
    "lambda_sweep_scale": m_lambda_sweep_scale,
    "branching": m_branching,
    "branching_scale": m_branching_scale,
    "energy_tax": m_energy_tax,
    "finite_size": m_finite_size,
    "finite_size_interior": m_finite_size_interior,
    "finite_size_periodic": m_finite_size_periodic,
    "concurrency": m_concurrency,
    "concurrency_scale": m_concurrency_scale,
    "floor_bracket": m_floor_bracket,
    "floor_bracket_scale": m_floor_bracket_scale,
    "retarget_cap": m_retarget_cap,
    "retarget_cap_scale": m_retarget_cap_scale,
    "dt_artifact": m_dt_artifact,
    "clumpiness": m_clumpiness,
    "clumpiness_scale": m_clumpiness_scale,
    "validation": m_validation,
}

# P2 companions: one per measurement above, each merged under the p2 key of its historical JSON (schema in experiments/SPEC_P2_LADDER.md).
P2_MEASUREMENTS = {
    "lambda_sweep": p2_lambda_sweep,
    "lambda_sweep_scale": p2_lambda_sweep_scale,
    "branching": p2_branching,
    "branching_scale": p2_branching_scale,
    "energy_tax": p2_energy_tax,
    "finite_size": p2_finite_size,
    "finite_size_interior": p2_finite_size_interior,
    "finite_size_periodic": p2_finite_size_periodic,
    "concurrency": p2_concurrency,
    "concurrency_scale": p2_concurrency_scale,
    "floor_bracket": p2_floor_bracket,
    "floor_bracket_scale": p2_floor_bracket_scale,
    "retarget_cap": p2_retarget_cap,
    "retarget_cap_scale": p2_retarget_cap_scale,
    "dt_artifact": p2_dt_artifact,
    "clumpiness": p2_clumpiness,
    "clumpiness_scale": p2_clumpiness_scale,
    "validation": p2_validation,
}

# Cheap-first order so an interrupted run lands the quick wins early.
ORDER = ["validation", "dt_artifact", "retarget_cap", "energy_tax", "branching",
         "lambda_sweep", "concurrency", "floor_bracket", "clumpiness", "finite_size",
         "finite_size_interior", "finite_size_periodic",
         "concurrency_scale", "retarget_cap_scale", "lambda_sweep_scale",
         "floor_bracket_scale", "clumpiness_scale", "branching_scale"]


def _merge_finite_size_periodic(shards: list[dict], config: dict) -> dict:
    """Reconstruct the full ``finite_size_periodic`` JSON from its K shards."""
    k = len(shards)
    n_and_seeds = config["n_and_seeds"]  # JSON: [[N, k_seeds], ...]
    data: dict = {}
    per_n: dict[int, list[float]] = {}
    for entry in n_and_seeds:
        n, k_seeds = int(entry[0]), int(entry[1])
        merged_rows: list[tuple[dict, dict]] = []
        for i in range(k_seeds):
            shard_idx = i % k
            row_idx = i // k
            per_seed_list = shards[shard_idx]["data"][str(n)]["per_seed"]
            if row_idx >= len(per_seed_list):
                raise ValueError(
                    f"shard {shard_idx} of {k} is missing row {row_idx} for N={n}; "
                    f"re-run the shard or check the slice_count matches every shard's _shard.count"
                )
            e = per_seed_list[row_idx]
            merged_rows.append((e["base"], e["treat"]))
        data[str(n)] = _tax_block(merged_rows)
        per_n[n] = [pct_delta(t["wasted_arrivals"], b["wasted_arrivals"]) for b, t in merged_rows]
    ns = [int(e[0]) for e in n_and_seeds]
    slope, lo, hi = loglog_slope_ci([math.log10(n) for n in ns], [per_n[n] for n in ns])
    return {
        "data": data,
        "scale_regression": {"x": "log10(N)", "unit": "percentage points per decade of N",
                             "resample": "seeds within each N",
                             "slope": slope, "ci_lo": lo, "ci_hi": hi},
    }


# Per-measurement mergers - one entry per shardable measurement (see SHARDABLE).
MERGERS = {
    "finite_size_periodic": _merge_finite_size_periodic,
}


def _do_merge(name: str) -> None:
    """Discover ``<name>.shard*_K.json`` files, verify they cover the slice, and merge to ``<name>.json``."""
    if name not in SHARDABLE:
        raise SystemExit(
            f"--merge: measurement '{name}' is not shardable. Shardable today: "
            f"{sorted(SHARDABLE)}. See measure.py's SHARDABLE / MERGERS to add a new one."
        )
    shard_files = sorted(RESULTS_DIR.glob(f"{name}.shard*_*.json"))
    if not shard_files:
        raise SystemExit(f"--merge: no shard files found matching {name}.shard*_*.json")
    shards: list[dict] = []
    for path in shard_files:
        with open(path) as f:
            doc = json.load(f)
        if "_shard" not in doc:
            raise SystemExit(f"{path.name}: missing _shard metadata; not a shard file")
        shards.append(doc)
    # Every shard must belong to the same slice count.
    counts = {s["_shard"]["count"] for s in shards}
    if len(counts) != 1:
        raise SystemExit(f"shards disagree on slice_count: {counts}")
    (k,) = counts
    # And every index 0..K-1 must be present exactly once.
    indices = sorted(s["_shard"]["index"] for s in shards)
    if indices != list(range(k)):
        raise SystemExit(
            f"shards for {name} are incomplete: have indices {indices}, need {list(range(k))}"
        )
    # Sort by shard index so the merger can address them positionally.
    shards.sort(key=lambda s: s["_shard"]["index"])
    # Configs must agree byte-for-byte, otherwise the shards ran different sweeps.
    configs = {json.dumps(s["config"], sort_keys=True) for s in shards}
    if len(configs) != 1:
        raise SystemExit(f"shards for {name} disagree on config; refusing to merge")
    config = shards[0]["config"]
    payload = MERGERS[name](shards, config)
    # Write the full JSON using the same code path as an end-to-end run (no _shard block).
    global _SEED_SLICE
    saved = _SEED_SLICE
    _SEED_SLICE = None
    try:
        out = write_result(name, config, payload)
    finally:
        _SEED_SLICE = saved
    print(f"[merged] {name} <- {len(shards)} shards -> {out}", flush=True)


def _parse_seed_slice(argv: list[str]) -> tuple[int, int] | None:
    """Extract ``--seed-slice N/K`` from argv. Returns (N, K) or None. Mutates argv in place."""
    for i, a in enumerate(argv):
        if a == "--seed-slice" and i + 1 < len(argv):
            spec = argv[i + 1]
            del argv[i : i + 2]
            break
        if a.startswith("--seed-slice="):
            spec = a.split("=", 1)[1]
            del argv[i]
            break
    else:
        return None
    if "/" not in spec:
        raise SystemExit(f"--seed-slice expects N/K, got {spec!r}")
    n_str, k_str = spec.split("/", 1)
    try:
        n, k = int(n_str), int(k_str)
    except ValueError as ex:
        raise SystemExit(f"--seed-slice: N and K must be integers ({ex})") from ex
    if not (0 <= n < k):
        raise SystemExit(f"--seed-slice: need 0 <= N < K, got N={n} K={k}")
    return n, k


def _extract_opt(argv: list[str], flag: str) -> str | None:
    """Pop ``--flag VALUE`` or ``--flag=VALUE`` from argv, returning VALUE (or None if absent)."""
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            val = argv[i + 1]
            del argv[i : i + 2]
            return val
        if a.startswith(flag + "="):
            val = a.split("=", 1)[1]
            del argv[i]
            return val
    return None


def _run_locate_plateau(argv: list[str]) -> None:
    """Handle ``--locate-plateau N`` and its ``--plateau-*`` options (issue #73)."""
    n_str = _extract_opt(argv, "--locate-plateau")
    if n_str is None:
        raise SystemExit("--locate-plateau expects a star count N, e.g. --locate-plateau 200000")
    try:
        n_stars = int(n_str)
    except ValueError as ex:
        raise SystemExit(f"--locate-plateau: N must be an integer ({ex})") from ex

    caps_str = _extract_opt(argv, "--plateau-caps")
    caps = [int(c) for c in caps_str.split(",")] if caps_str else [8, 16, 32]
    seeds_str = _extract_opt(argv, "--plateau-seeds")
    n_seeds = int(seeds_str) if seeds_str else 8
    thr_str = _extract_opt(argv, "--plateau-threshold")
    threshold = float(thr_str) if thr_str else 0.05
    paired = "--plateau-paired" in argv
    if paired:
        argv[:] = [a for a in argv if a != "--plateau-paired"]

    rep = locate_plateau_report(n_stars, caps=caps, seeds=SEEDS[:n_seeds],
                                threshold=threshold, paired=paired)
    _print_plateau_report(rep)


def main(argv: list[str]) -> None:
    global _SEED_SLICE
    _SEED_SLICE = _parse_seed_slice(argv)

    if any(a == "--locate-plateau" or a.startswith("--locate-plateau=") for a in argv):
        _run_locate_plateau(argv)
        return

    if "--merge" in argv:
        # --merge <name> [<name>...]: reconstruct full JSONs from shard files.
        i = argv.index("--merge")
        merge_names = [a for a in argv[i + 1 :] if not a.startswith("-")]
        if not merge_names:
            raise SystemExit("--merge: expected one or more measurement names")
        for n in merge_names:
            _do_merge(n)
        return

    p2_mode = "--p2" in argv
    if p2_mode:
        argv = [a for a in argv if a != "--p2"]
    force = "--force" in argv
    names = [a for a in argv if not a.startswith("-")]
    todo = names if names else ORDER
    dispatch = P2_MEASUREMENTS if p2_mode else MEASUREMENTS
    have_msg = "p2 companion" if p2_mode else "measurement"
    for name in todo:
        if name not in dispatch:
            print(f"unknown {have_msg}: {name} (have: {', '.join(ORDER)})")
            continue
        if _SEED_SLICE is not None and (p2_mode or name not in SHARDABLE):
            # p2 companions aren't shardable in this pass - see p2_finite_size_periodic docstring.
            print(
                f"[skip] {name} ({'--p2' if p2_mode else '--seed-slice active'}; "
                f"not shardable)",
                flush=True,
            )
            continue
        if p2_mode:
            out = RESULTS_DIR / f"{name}.json"
            if not out.exists():
                print(f"[skip] {name} (no historical file yet - run without --p2 first)",
                      flush=True)
                continue
            if _p2_has_companion(name) and not force:
                print(f"[skip] {name} (p2 companion present; --force to recompute)", flush=True)
                continue
            print(f"[run ] {name} [p2 companion]", flush=True)
            dispatch[name]()
            print(f"[done] {name} p2 -> results/{name}.json (p2 key merged)", flush=True)
        else:
            out = RESULTS_DIR / f"{name}{_shard_suffix()}.json"
            if out.exists() and not force:
                print(f"[skip] {name} (exists; --force to recompute)", flush=True)
                continue
            print(f"[run ] {name}{_shard_suffix()}", flush=True)
            dispatch[name]()
            print(f"[done] {name} -> results/{name}{_shard_suffix()}.json", flush=True)


if __name__ == "__main__":
    from experiments._run import warn_if_no_optimize

    warn_if_no_optimize("experiments.measure")
    main(sys.argv[1:])
