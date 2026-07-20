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
    uv run --extra dev python -O -m experiments.measure            # all measurements (skip existing)
    uv run --extra dev python -O -m experiments.measure --force    # recompute all
    uv run --extra dev python -O -m experiments.measure lambda_sweep floor_bracket   # a subset

    # P2 companion (issue #38 p2 substrate; see experiments/SPEC_P2_LADDER.md).
    # Runs a power-of-two-N sweep alongside every historical measurement and merges the result
    # under the top-level ``p2`` key of the same file. Historical top-level keys are untouched.
    uv run --extra dev python -O -m experiments.measure --p2       # p2 companion for every JSON
    uv run --extra dev python -O -m experiments.measure --p2 --force   # recompute p2 blocks

The ``-O`` strips ``if __debug__:`` invariant checks; ensemble runs get a ~2-3x
wall-clock win at bit-identical results (see docs/HARDWARE.md "Assertion mode").
Omit ``-O`` while iterating - you'll get a stderr warning on each run.

Distributed across K boxes (issue #33, item 2 - only for measurements in SHARDABLE):

    # On each box i in 0..K-1:
    uv run --extra dev python -O -m experiments.measure --seed-slice $i/$K finite_size_periodic
    # Then, with all shard files under experiments/results/:
    uv run --extra dev python -O -m experiments.measure --merge finite_size_periodic

The merge is bit-identical to a single-machine full run; see swarm/tests/test_seed_slice.py.

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
from swarm.sim import _build_kdtree, initial_state

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


# Per-measurement canonical N for the p2 fixed-N base sweeps (issue #38 follow-up). Each value is
# the largest power of two whose FULL ensemble regenerates in <= 1 min wall-clock at
# SWARM_WORKERS=8 on k02 (see docs/HARDWARE.md); different measurements have different per-seed cost
# (offspring count, in-flight relay, Thomas clustering, fixed-vs-event stepping), so each lands on
# its own N rather than a shared anchor. The folds are deterministic (CLAUDE.md sec 7), so N is a
# pure wall-clock choice and never changes a result. SWARM_P2_N_OVERRIDE forces a single N across
# all of these (used only to probe the 1-min ceiling; unset in normal regeneration).
P2_FIXED_N = {
    "lambda_sweep": 2048,   # 30.7s (4096 = 72.6s, over)
    "branching": 8192,      # 57.9s (16384 would be ~116s)
    "energy_tax": 2048,     # 57.3s (slingshot policies are the costly part)
    "concurrency": 32768,   # 33.3s (65536 = 73.6s, over)
    "floor_bracket": 32768, # 64.2s (marginally over the minute; kept deliberately)
    "retarget_cap": 32768,  # 52.3s
    "dt_artifact": 8192,    # 53.4s (fixed-step rows use the pointer path, so this caps lowest)
    "clumpiness": 4096,     # 26.4s (8192 = 69.5s, over)
}


def _p2_fixed_n(name: str) -> int:
    """Canonical p2 star count for a fixed-N base sweep, honouring the SWARM_P2_N_OVERRIDE probe."""
    override = os.environ.get("SWARM_P2_N_OVERRIDE")
    return int(override) if override else P2_FIXED_N[name]


# --------------------------------------------------------------------------------------------
# seed slicing for distributed ensembles (item 2 of #33's alternative-levers list)
# --------------------------------------------------------------------------------------------
# The seed ensemble is map-only (each `(seed, mode)` run is independent), so it can be split
# across machines with linear speedup. ``--seed-slice N/K`` runs only every K-th seed starting
# at N (i.e., seeds at positions `i` where `i % K == N`), and writes to a shard file. The user
# runs K shards on K boxes (any way that suits them: ssh, cloud batch, spot fleet) then runs
# ``--merge <name> --slice-count K`` to reconstruct the full result from the shards.
#
# Bit-identical guarantee: ``merge(shard 0..K-1) == single-machine full run`` at the JSON
# byte level. The fold is deterministic in (params, seed), so per-seed results are unchanged;
# the merge step just re-interleaves them in the original seed order and re-runs aggregates
# through the same summary functions. Verified by ``tests/test_seed_slice.py``.
#
# Scope: not every measurement is shardable yet. See ``SHARDABLE`` below; extending is
# straightforward - each new measurement registers a merger function that concatenates its
# shard-per-seed rows and calls its own aggregator.

_SEED_SLICE: tuple[int, int] | None = None  # (index, count) - set by --seed-slice; else full run


def _apply_slice(seeds: list[int]) -> list[int]:
    """Filter ``seeds`` down to the active seed slice, or return unchanged when no slice.

    ``--seed-slice N/K`` selects ``[seeds[i] for i in range(len(seeds)) if i % K == N]``.
    Every shardable measurement wraps its ``SEEDS[:X]`` in a call to this helper.
    """
    if _SEED_SLICE is None:
        return seeds
    idx, count = _SEED_SLICE
    return [s for i, s in enumerate(seeds) if i % count == idx]


def _shard_suffix() -> str:
    """Filename suffix for the active slice, or empty when running the full ensemble."""
    if _SEED_SLICE is None:
        return ""
    return f".shard{_SEED_SLICE[0]}_{_SEED_SLICE[1]}"


# Measurements that support ``--seed-slice`` / ``--merge`` today. Each entry needs a matching
# entry in ``MERGERS`` (see below). Adding a measurement: refactor it to gather per-seed rows
# through ``_paired`` (already deterministic under slicing) and register the merger.
SHARDABLE = {"finite_size_periodic"}


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
    # record_steps=False: this worker only reads scalar aggregates via record(), never the
    # per-event trace. Dropping it is what keeps two paired N=200k event runs (e.g. the heavy
    # branching_scale sweep) inside a worker's RAM instead of OOMing. Numbers are unchanged.
    b = simulate_swarm(SwarmParams(coordination=mode_base, **params), seed=seed, record_steps=False)
    t = simulate_swarm(SwarmParams(coordination=mode_treat, **params), seed=seed, record_steps=False)
    return (record(b), record(t))


def _single_worker(args: tuple[str, dict, int]) -> dict:
    """One single-mode run at a seed. Top-level for pickling. Used by the non-paired sweeps
    (floor_bracket, dt_artifact_extra, ...) that need N modes for the SAME seed but do not fit
    the strict base/treat shape of ``_paired_worker``.
    """
    mode, params, seed = args
    r = simulate_swarm(SwarmParams(coordination=mode, **params), seed=seed, record_steps=False)
    return record(r)


def _concurrency_worker(args: tuple[str, dict, int, tuple[float, ...]]) -> tuple[str, int, int, dict[float, int]]:
    """One (mode, seed) concurrency run. Returns (mode, seed, peak_in_flight, {bin: in_flight}).

    The `series` walk that used to happen in the main loop is done inside the worker so nothing
    but small scalars crosses the process boundary (each SwarmResult holds one SwarmStep per event,
    which at N=200k is ~2M records; keeping that in the worker keeps IPC cheap).
    """
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
    """Paired instant/lightspeed clumpy run. Returns (record_b, record_t, hop_hists).

    Clumpiness needs the SwarmResult's ``settle_hop_hist``/``wasted_hop_hist`` arrays for the
    stratified-by-hop-length cancellation test; ``record()`` does not carry them, so this worker
    is a specialised paired variant that returns the histograms alongside the records.
    """
    params, seed = args
    # Hop histograms come from state counters (carried on the record/result), not from the
    # per-event trace, so record_steps=False is safe here too.
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
    """ProcessPoolExecutor.map with the same determinism + progress conventions as ``_paired``.

    Executor.map preserves input order, so 1, 4, or N workers produce byte-identical output. When
    SWARM_WORKERS<=1 (or CPU=1) the loop runs serially and is thus a drop-in for the old for-loops.
    """
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


def _kd_nn_other_d2(kd: dict, xs: list[float], ys: list[float], zs: list[float], i: int) -> float:
    """Squared distance from point ``i`` to its nearest OTHER point, via k-d branch-and-bound.

    Standalone NN over the fixed positions (no unsettled/beacon state), so it is the diagnostic
    analogue of ``swarm.sim._nearest_unsettled_at`` for Clark-Evans R. Tie-break is lowest index
    (matches the naive O(N^2) scan): a same-d2 point displaces the best only when its index is
    lower, so bit-identical to the pairwise-loop version on tied inputs (continuous coordinates
    tie only with probability zero).
    """
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
    """Clark-Evans aggregation index R = observed mean NN distance / Poisson expectation (3D).

    R = 1 Poisson (uniform), R < 1 clustered, R > 1 regular. The Poisson 3D nearest-neighbour
    expectation is 0.55396 * rho^(-1/3) with rho = N / L^3 (Clark & Evans 1954, the 3D form).
    Used comparatively across fields at the SAME N and box, so the (mild, constant) box edge bias
    cancels. Near-O(N log N) via the same k-d tree the sim uses (a standalone NN branch-and-bound
    over ``_build_kdtree``, no settle/beacon state), so the diagnostic no longer gates a large-N
    clumpy-field sweep.
    """
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
    """Write ``<name>.json`` (or ``<name>.shardN_K.json`` when running a seed slice).

    When a slice is active the output carries a top-level ``_shard`` block; ``--merge`` reads
    that block to interleave shards back into full seed order before re-aggregating.
    """
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
    """Merge a top-level ``p2`` block into the existing ``<name>.json``, preserving every other key.

    Follow-up to PRs #79/#80/#81 (flat p2 kd-tree substrate + wired dispatch at p2 N). This is
    the paper-side p2 ladder migration: alongside every historical measurement, an
    ``n_stars = 2^k`` companion sweep lives under the ``p2`` key. The historical top-level keys
    (``config``, ``data``, ``scale_regression``, ...) stay byte-for-byte untouched - the drift
    guards on those keys remain load-bearing - and the p2 companion adds its own self-contained
    ``{config, ...payload}`` under ``p2``.

    See ``swarm/experiments/SPEC_P2_LADDER.md`` for the full schema and the sweep-size choices.
    """
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


def p2_lambda_sweep() -> None:
    """P2 companion to ``m_lambda_sweep``: N=500 -> the 1-min-ceiling p2 N (see P2_FIXED_N)."""
    seeds = SEEDS[:512]
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
    """N=200k companion to the headline speed sweep: does tax ~ v/c linearity hold at scale?

    The base sweep runs at N=500 for a tight CI on the tax slope (a = 0.97 [0.89, 1.19]). At N=200k
    the total tax is a fifth of the small-N value (the fuel-tax bulk decline), so the natural question
    is not the magnitude but whether the SHAPE stays linear in Lambda - i.e. whether the collision
    argument that gives tax ~ v/c is still the right first-order description at the finite-size arm's
    tip. Same Lambda ladder as the base; seeds drop to 8 (the same precision target the ``finite_size``
    sweep uses at N=200k).
    """
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
    """P2 companion to ``m_lambda_sweep_scale``: N=200_000 -> N=262_144 (next p2 above 200k)."""
    seeds = SEEDS[:8]
    n_stars = 262_144
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
    """N=200k companion to the branching sweep: does the tax-grows-with-branching claim hold at scale?

    The base sweep (N=400) shows tax rising monotonically up to offspring=16 without saturating. Since
    the same-N fuel tax at N=200k is only ~1.5% (down from ~19% at N=300), the paper's ``does the
    tax also grow with offspring at scale'' question is a real open one - a larger field breeds more
    simultaneous races per settlement, but each race has a larger neighbourhood so the marginal
    collision rate could saturate. Offspring ladder stops at 8 (offspring=16 at N=200k over-subscribes
    RAM on k02 - roughly 6x the arrivals of offspring=4 means ~1.2 GB per worker peak, and even 4
    concurrent workers push into swap); seeds drop to 6. See docs/HARDWARE.md.
    """
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
    """P2 companion to ``m_branching_scale``: N=200_000 -> N=262_144 (next p2 above 200k).

    Offspring ladder stops at 8 for the same reason the historical version does (offspring=16 at
    N>200k over-subscribes RAM per docs/HARDWARE.md); 6 seeds to match the base.
    """
    seeds = SEEDS[:6]
    n_stars = 262_144
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


def p2_finite_size() -> None:
    """P2 companion to ``m_finite_size``: p2 ladder matched to the historical seed pattern.

    Historical: (300, 600, 1200, 2400, 4800, 9600, 24000, 48000, 200000).
    P2:         (256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 262144).

    Nine points each; seed counts match the historical rows exactly so the two lever arms
    are directly comparable. Byte-for-byte comparison against the historical points isn't
    possible (different N), but bit-identity of the flat vs pointer path at matching p2 N is
    already proven by ``tests/test_flat_run_fill_oracle.py``.
    """
    n_seeds_by_n = [(256, 48), (512, 48), (1024, 48), (2048, 48), (4096, 32),
                    (8192, 32), (16384, 24), (32768, 16), (262144, 8)]
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
    """Run the paired instant/lightspeed concurrency ensemble in parallel over (seed, mode).

    Shared between the N=500 headline sweep (``m_concurrency``) and the N=200k scale companion
    (``m_concurrency_scale``); executor.map preserves input order so this is byte-identical to the
    old serial version at any worker count.
    """
    modes = ("instant", "lightspeed")
    params = dict(n_stars=n_stars, policy="powered", probe_speed_c=lam,
                  speed_cap_c=max(0.05, 2 * lam), stepping="event")
    args = [(mode, params, s, tuple(bins)) for s in seeds for mode in modes]
    results = _parallel_map(_concurrency_worker, args, label="seed")
    # Bucket back per mode, preserving seed order (args are emitted seed-then-mode, so the mode
    # sub-lists reflect the input seed order regardless of worker completion order).
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
    data = _concurrency_ensemble(seeds, n_stars, lam, bins)
    write_result("concurrency",
                 {"policy": "powered", "lambda": lam, "n_stars": n_stars, "n_seeds": len(seeds),
                  "stepping": "event"},
                 {"data": data})


def p2_concurrency() -> None:
    """P2 companion to ``m_concurrency``: N=500 -> the 1-min-ceiling p2 N (see P2_FIXED_N)."""
    seeds = SEEDS[:16]
    n_stars = _p2_fixed_n("concurrency")
    lam = 0.2
    bins = [round(i / 20, 2) for i in range(1, 19)] + [0.95, 0.97, 0.99]
    data = _concurrency_ensemble(seeds, n_stars, lam, bins)
    write_p2_companion("concurrency",
                       {"policy": "powered", "lambda": lam, "n_stars": n_stars, "n_seeds": len(seeds),
                        "stepping": "event"},
                       {"data": data})


def m_concurrency_scale() -> None:
    """N=200k companion to the concurrency sweep: does the many-probes-in-flight mechanism hold
    at the honest lever arm?

    Same paired instant/lightspeed structure and coverage bins as ``m_concurrency`` at N=500, but at
    the N=200,000 finite-size scale where the fuel tax is only ~1.5%. If the mechanism claim is
    right, the median in-flight population should scale roughly with N (the field is exponentially
    branching until stars run out); this is the at-scale figure for the paper's Section 5 argument
    that a wasted trip is one of hundreds (thousands, at 200k) aloft and never sits on the critical
    path. Seeds are scaled down to 8 (the same precision-target logic as ``m_finite_size`` at 200k).
    """
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
    n_stars = 262_144
    lam = 0.2
    bins = [round(i / 20, 2) for i in range(1, 19)] + [0.95, 0.97, 0.99]
    data = _concurrency_ensemble(seeds, n_stars, lam, bins)
    write_p2_companion("concurrency_scale",
                       {"policy": "powered", "lambda": lam, "n_stars": n_stars, "n_seeds": len(seeds),
                        "stepping": "event"},
                       {"data": data})


def _floor_bracket_body(seeds: list[int], n_stars: int, lambdas: list[float]) -> dict:
    """Shared floor-bracket ensemble body (used by ``m_floor_bracket`` and its p2 companion).

    Runs the (mode, seed) paired ensemble and computes the standard aggregate + per-seed block.
    Factored so the historical and p2 pass share code exactly - only ``n_stars`` differs.
    """
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
    """instant / inflight / lightspeed: how much of the decision-site tax survives in-flight relay.

    inflight is the optimistic bound (a probe redirects the instant a beacon overtakes it). We
    report, per Lambda, all three modes' wasted arrivals, redundant travel, and fill time, plus
    the inflight-vs-lightspeed deltas - the referee's requested floor estimate.
    """
    seeds = SEEDS[:48]
    n_stars = 400
    lambdas = [0.05, 0.1, 0.2]
    data = _floor_bracket_body(seeds, n_stars, lambdas)
    write_result("floor_bracket",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "modes": ["instant", "lightspeed", "inflight"], "stepping": "event"},
                 {"data": data})


def p2_floor_bracket() -> None:
    """P2 companion to ``m_floor_bracket``: N=400 -> the 1-min-ceiling p2 N (see P2_FIXED_N)."""
    seeds = SEEDS[:48]
    n_stars = _p2_fixed_n("floor_bracket")
    lambdas = [0.05, 0.1, 0.2]
    data = _floor_bracket_body(seeds, n_stars, lambdas)
    write_p2_companion("floor_bracket",
                       {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                        "lambdas": lambdas, "modes": ["instant", "lightspeed", "inflight"],
                        "stepping": "event"},
                       {"data": data})


def m_floor_bracket_scale() -> None:
    """N=200k companion to the floor bracket: how much of the (already tiny, ~1.5%) tax survives
    in-flight relay at scale?

    The base result (N=400) shows the inflight mode recovers essentially all of the decision-site
    tax. At N=200k the wasted-arrival tax itself is only ~1.5%, so the interesting question is
    whether the floor is still 0 at scale or whether some irreducible residue survives. Same 3 x 3
    (lambdas x modes) shape; seeds drop to 8.
    """
    seeds = SEEDS[:8]
    n_stars = 200_000
    lambdas = [0.05, 0.1, 0.2]
    data = _floor_bracket_body(seeds, n_stars, lambdas)
    write_result("floor_bracket_scale",
                 {"policy": "powered", "n_stars": n_stars, "n_seeds": len(seeds),
                  "lambdas": lambdas, "modes": ["instant", "lightspeed", "inflight"], "stepping": "event"},
                 {"data": data})


def p2_floor_bracket_scale() -> None:
    """P2 companion to ``m_floor_bracket_scale``: N=200_000 -> N=262_144 (next p2 above 200k)."""
    seeds = SEEDS[:8]
    n_stars = 262_144
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
    """N=200k companion to the re-target-cap sweep: does insensitivity to the bookkeeping cap
    hold at scale?

    The base (N=400) sweep pins the tax as invariant across caps=2..32. At N=200k there are ~10x
    more retarget events per fill (a bigger core, more late-arriving beacons), so if the cap ever
    bites it would bite hardest here. Same cap ladder; seeds drop to 8.
    """
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
    """P2 companion to ``m_dt_artifact``: N=300 -> N=512 (70% larger, cleanly p2).

    Note: this measurement uses stepping='fixed' and stepping='event'; only the event row
    (dt=None) hits the flat p2 kd-tree fast path. The fixed-step rows run through the pointer
    path even at p2 N, which is why its 1-min-ceiling N (P2_FIXED_N) is the lowest of the base
    sweeps. Included per the "no exclusions" scope decision.
    """
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
    """Shared clumpy-field sweep body, used by ``m_clumpiness`` (N=500) and its scale companion.

    Runs the paired instant/lightspeed ensemble across (level, Lambda), computes the per-seed
    through-origin slope for the tax=a*Lambda fit, and aggregates hop-length histograms. Clark-Evans
    R is measured on the first ``r_seed_count`` seeds (near-O(N log N) since the k-d tree rewrite).
    """
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
            # the hop histograms (which record() does not carry). executor.map preserves seed order.
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
    return data


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
    """N=200k companion to the clumpy-field sweep: does tax = Lambda still hold on non-uniform
    fields at scale?

    Same Thomas-cluster levels and Lambda ladder as the base, at N=200k with 8 seeds. Because the
    base measurement keeps ``n_clumps`` fixed at 25 to sweep sigma, at N=200k the clumps become
    dense mega-clusters (~8k stars each at sigma=0.05); the clumpiness_R the measurement records
    quantifies where each level actually lands in R-space, so the tax-vs-R curve is the comparable
    quantity across scales. The uniform level is still the hard null (must return ~0.96).
    """
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
    """P2 companion to ``m_clumpiness_scale``: N=200_000 -> N=262_144 (next p2 above 200k).

    Same n_clumps=25 as the historical - so at N=262_144 the mega-cluster size scales up
    proportionally (~10.5k stars/clump at the tightest sigma). See ``m_clumpiness_scale`` docs
    for the tax-vs-R interpretation this comparison enables.
    """
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
    """P2 companion to ``m_validation``: N=400 -> N=512 (28% larger, cleanly p2).

    Not a Nicholson & Forgan reproduction any more - N&F used N=400 for their canonical
    numbers - just the same three-policy comparison at a p2 scale for shape.
    """
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


def p2_finite_size_interior() -> None:
    """P2 companion to ``m_finite_size_interior``: p2 ladder matched to the historical seed pattern.

    Historical: (300, 600, 1200, 2400, 4800, 9600, 24000, 48000, 200000) with seeds
                (32, 32, 24, 16, 12, 12, 10, 8, 6).
    P2:         (256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 262144) with the same seed counts.
    """
    n_seeds_by_n = [(256, 32), (512, 32), (1024, 24), (2048, 16), (4096, 12),
                    (8192, 12), (16384, 10), (32768, 8), (262144, 6)]
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
        seeds = _apply_slice(SEEDS[:k])
        if not seeds:
            # Under an aggressive slice (K larger than k) some N's shard may be empty; the merge
            # step tolerates this and reconstructs from other shards.
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
    # Under a shard, scale_regression is a subset regression; the merge step recomputes it from
    # the concatenated per-seed data. Write ``None``s here so an accidentally-used shard file
    # never masquerades as a full result.
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
    """P2 companion to ``m_finite_size_periodic``: p2 ladder matched to the historical seed pattern.

    Not shardable via ``--seed-slice`` for the p2 pass - the historical periodic sweep is the
    sole shardable measurement today, and its shard/merge machinery is coupled to the historical
    file name (``finite_size_periodic.json``). The p2 companion runs full seeds always. If a
    p2 shard mode is ever wanted, ``SHARDABLE`` grows a ``finite_size_periodic_p2`` entry and
    ``_do_merge`` learns the p2 key routing - but that's out of scope for the migration.
    """
    n_seeds_by_n = [(256, 32), (512, 32), (1024, 24), (2048, 16), (4096, 12),
                    (8192, 12), (16384, 10), (32768, 8), (262144, 6)]
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

# P2 companions: one per measurement above. Each merges its result under the ``p2`` key of the
# corresponding historical file, so ``experiments.measure --p2`` runs the p2 sweeps on top of
# already-computed historical JSONs (which stay byte-for-byte untouched). See
# ``experiments/SPEC_P2_LADDER.md`` for the schema + sweep sizes.
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
    """Reconstruct the full ``finite_size_periodic`` JSON from its K shards.

    For each N block, interleaves per-seed rows across shards in the original SEED order
    (position ``i`` came from shard ``i % K`` at that shard's ``i // K`` row) and recomputes
    the per-block ``_tax_block`` and the top-level ``scale_regression`` via the same
    ``loglog_slope_ci`` the single-machine run used. Bit-identical by construction.
    """
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


def main(argv: list[str]) -> None:
    global _SEED_SLICE
    _SEED_SLICE = _parse_seed_slice(argv)

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
