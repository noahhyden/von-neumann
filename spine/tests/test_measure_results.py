"""Drift guard: the committed JSON artifacts must still match the fold (SCRUTINY.md C8).

The paper restates only numbers committed under `experiments/results/`. That is safe only if
the JSON cannot silently drift from the code that made it. Each test re-runs a TINY slice of a
measurement (one or two direct fills, never the break-even search) and asserts it reproduces the
committed record exactly - the spine fold is a pure seeded function, so this is an exact check
modulo JSON float round-trip. A refactor that changes the fold fails here until the JSON is
regenerated (`python -m experiments.measure --force`).

We deliberately guard the deterministic single fills (sweep points, per-seed A/B records, and
per-policy nominal fractions), NOT the bisection-derived break-even, whose endpoint depends on
the search path. The break-even is a convenience read off the same fills these guard.

Each test skips if its JSON is absent, so a fresh checkout without a local run still passes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.measure import _dwell_fraction, _t100
from spine.run import derive_settle_time_years
from spine.scenario import SpineScenario

RESULTS = Path(__file__).resolve().parents[1] / "experiments" / "results"


def _load(name: str) -> dict:
    path = RESULTS / f"{name}.json"
    if not path.exists():
        pytest.skip(f"{name}.json not present (run experiments.measure)")
    return json.loads(path.read_text())


def test_copy_time_robustness_matches_fold() -> None:
    d = _load("copy_time_robustness")
    cfg = d["config"]
    sc = SpineScenario.default()
    nominal = derive_settle_time_years(sc)
    # Guard the nominal point and the first two sweep multipliers (direct fills).
    got = _dwell_fraction(cfg["policy"], nominal, n_stars=cfg["n_stars"], seed=cfg["seed"])
    assert got == pytest.approx(d["nominal"]["dwell_fraction"], rel=1e-9)
    for entry in d["sweep"][:3]:
        f = _dwell_fraction(cfg["policy"], entry["settle_years"], n_stars=cfg["n_stars"], seed=cfg["seed"])
        assert f == pytest.approx(entry["dwell_fraction"], rel=1e-9), f"mult {entry['multiplier']}"


def test_dwell_tax_matches_fold() -> None:
    d = _load("dwell_tax")
    cfg = d["config"]
    settle = cfg["settle_years"]
    n = cfg["n_stars"]
    block = d["ensemble"]["slingshot_nearest"]["per_seed"]
    for rec in block[:2]:  # first two seeds only
        w = _t100("slingshot_nearest", settle, n_stars=n, seed=rec["seed"], stepping="event")
        z = _t100("slingshot_nearest", 0.0, n_stars=n, seed=rec["seed"], stepping="event")
        assert w == pytest.approx(rec["t100_with"], rel=1e-9)
        assert z == pytest.approx(rec["t100_zero"], rel=1e-9)
        tax = (w - z) / z
        assert tax == pytest.approx(rec["tax_fraction"], rel=1e-9)


def test_policy_sweep_matches_fold() -> None:
    d = _load("policy_sweep")
    cfg = d["config"]
    settle = cfg["settle_years"]
    n = cfg["n_stars"]
    for row in d["policies"]:
        t100 = _t100(row["policy"], settle, n_stars=n, seed=cfg["seed"], stepping="event")
        assert t100 == pytest.approx(row["t100_years"], rel=1e-9), row["policy"]
        frac = settle / t100
        assert frac == pytest.approx(row["dwell_fraction"], rel=1e-9), row["policy"]
