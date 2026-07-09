"""Drift guard: the committed JSON result artifacts must still match the fold.

The heavy ensemble (``experiments/measure.py``) runs locally and its output is committed under
``experiments/results/``; the paper and figures restate only those numbers. That is only safe
if the committed JSON cannot silently drift from the code. These tests re-run a TINY slice of
each measurement (a couple of seeds) and assert it reproduces the corresponding committed
records exactly. A refactor that changes the fold therefore fails here until the JSON is
regenerated - the same discipline as the pinned-baseline tests, extended to the artifacts.

Each test skips if its JSON is absent (so a fresh checkout without a local run still passes);
in CI the artifacts are committed, so the guard is live.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from swarm import SwarmParams, simulate_swarm
from experiments.measure import SEEDS, record

RESULTS = Path(__file__).resolve().parents[1] / "experiments" / "results"


def _load(name: str) -> dict:
    path = RESULTS / f"{name}.json"
    if not path.exists():
        pytest.skip(f"{name}.json not present (run experiments.measure)")
    return json.loads(path.read_text())


def _assert_record_matches(got: dict, want: dict, ctx: str) -> None:
    # Integer counts must match exactly; floats to a tight relative tolerance (deterministic
    # fold, so this is really an exact check modulo JSON float round-trip).
    for k in ("wasted_arrivals", "midflight_aborts", "total_launched", "final_settled", "n_stars"):
        assert got[k] == want[k], f"{ctx}: {k} {got[k]} != {want[k]}"
    for k in ("t100", "wasted_travel_pc", "settle_energy_c2", "wasted_energy_c2"):
        if want[k] is None:
            assert got[k] is None, f"{ctx}: {k} {got[k]} != None"
        else:
            assert got[k] == pytest.approx(want[k], rel=1e-9), f"{ctx}: {k} {got[k]} != {want[k]}"


def test_validation_json_matches_fold() -> None:
    d = _load("validation")
    cfg = d["config"]
    for pol, want in d["policies"].items():
        r = simulate_swarm(SwarmParams(n_stars=cfg["n_stars"], policy=pol, stepping=cfg["stepping"]), seed=cfg["seed"])
        assert r.t100_years == pytest.approx(want["t100"], rel=1e-9)
        assert r.max_probe_speed_km_s == pytest.approx(want["max_speed_km_s"], rel=1e-9)


def test_lambda_sweep_json_matches_fold() -> None:
    d = _load("lambda_sweep")
    cfg = d["config"]
    lam = cfg["lambdas"][0]
    block = d["data"][str(lam)]
    for i in range(2):  # re-run the first two seeds only
        seed = SEEDS[i]
        common = dict(n_stars=cfg["n_stars"], policy=cfg["policy"], probe_speed_c=lam,
                      speed_cap_c=max(0.05, 2 * lam), stepping=cfg["stepping"])
        base = record(simulate_swarm(SwarmParams(**common, coordination="instant"), seed=seed))
        treat = record(simulate_swarm(SwarmParams(**common, coordination="lightspeed"), seed=seed))
        _assert_record_matches(base, block["per_seed"][i]["base"], f"lambda_sweep base seed{i}")
        _assert_record_matches(treat, block["per_seed"][i]["treat"], f"lambda_sweep treat seed{i}")


def test_clumpiness_json_matches_fold() -> None:
    # Guard the clumpy-field robustness numbers. Re-run two seeds of the uniform null level at the
    # first Lambda and assert they reproduce the committed per-seed records (same discipline as the
    # other measurements). The uniform level uses the default (n_clumps=None) field.
    d = _load("clumpiness")
    cfg = d["config"]
    lam = cfg["lambdas"][0]
    block = d["data"]["uniform"]["per_lambda"][str(lam)]
    for i in range(2):
        seed = SEEDS[i]
        common = dict(n_stars=cfg["n_stars"], policy="powered", probe_speed_c=lam,
                      speed_cap_c=max(0.05, 2 * lam), stepping="event")
        base = record(simulate_swarm(SwarmParams(**common, coordination="instant"), seed=seed))
        treat = record(simulate_swarm(SwarmParams(**common, coordination="lightspeed"), seed=seed))
        _assert_record_matches(base, block["per_seed"][i]["base"], f"clumpiness base seed{i}")
        _assert_record_matches(treat, block["per_seed"][i]["treat"], f"clumpiness treat seed{i}")


def test_floor_bracket_json_matches_fold() -> None:
    d = _load("floor_bracket")
    cfg = d["config"]
    lam = cfg["lambdas"][0]
    block = d["data"][str(lam)]
    cap = max(0.05, 2 * lam)
    for mode in ("instant", "lightspeed", "inflight"):
        seed = SEEDS[0]
        r = record(simulate_swarm(SwarmParams(n_stars=cfg["n_stars"], policy="powered", probe_speed_c=lam,
                                              speed_cap_c=cap, stepping=cfg["stepping"], coordination=mode), seed=seed))
        _assert_record_matches(r, block["per_seed"][mode][0], f"floor_bracket {mode} seed0")


def test_finite_size_json_matches_fold() -> None:
    # Guard the referee-critical scale numbers at the SMALLEST N only (N=4800 is ~200 s/seed;
    # too slow for a test). The small point exercises the same pipeline the whole sweep uses.
    d = _load("finite_size")
    n = min(int(k) for k in d["data"])
    block = d["data"][str(n)]
    for i in range(2):
        seed = SEEDS[i]
        common = dict(n_stars=n, policy="powered", probe_speed_c=0.2, speed_cap_c=0.4, stepping="event")
        base = record(simulate_swarm(SwarmParams(**common, coordination="instant"), seed=seed))
        treat = record(simulate_swarm(SwarmParams(**common, coordination="lightspeed"), seed=seed))
        _assert_record_matches(base, block["per_seed"][i]["base"], f"finite_size base seed{i}")
        _assert_record_matches(treat, block["per_seed"][i]["treat"], f"finite_size treat seed{i}")
