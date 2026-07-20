"""Oracle: the Rust full-fill loop reproduces the Python reference bit-for-bit.

Tier 2 of the 200k event-loop speedup (see docs/HARDWARE.md). The Rust crate gains a
``run_fill`` that owns the whole event loop for the supported config
(``policy="powered"``, ``coordination in {instant, lightspeed}``, ``stepping="event"``);
everything else falls back to the pure-Python fold. Like the kd-tree backend oracle
(``test_kdtree_backends.py``), this asserts the accelerated path is byte-identical to the
reference, so it can never move a reported number - it only changes wall-clock.

Skips cleanly when ``swarm_rust`` is not built (a checkout without the rust extra), so CI on
the Python path stays green; when the extension is present the guard is live.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from swarm import SwarmParams, simulate_swarm

rust = pytest.importorskip("swarm_rust")
if not hasattr(rust, "run_fill"):
    pytest.skip("swarm_rust lacks run_fill (rebuild the crate)", allow_module_level=True)

import swarm.sim as sim


def _summary(r) -> dict:
    """Every SwarmResult field except the per-event trace (which the fast path omits)."""
    return {f.name: getattr(r, f.name) for f in fields(r) if f.name != "steps"}


# Matrix over the supported fast-path config: both coordination modes, a periodic and a
# non-periodic field, a range of N, offspring, and seeds. Each must match the Python fold exactly.
MATRIX = [
    dict(n_stars=400, coordination="instant", seed=1),
    dict(n_stars=400, coordination="lightspeed", seed=1),
    dict(n_stars=900, coordination="lightspeed", seed=7, offspring_per_settlement=3),
    dict(n_stars=1500, coordination="instant", seed=3),
    dict(n_stars=1200, coordination="lightspeed", seed=11, periodic=True),
    dict(n_stars=600, coordination="lightspeed", seed=2, max_retargets=2),
]


@pytest.mark.parametrize("cfg", MATRIX, ids=lambda c: f"{c['coordination']}-n{c['n_stars']}-s{c['seed']}")
def test_rust_fill_matches_python(cfg: dict) -> None:
    seed = cfg.pop("seed")
    params = SwarmParams(policy="powered", probe_speed_c=0.2, speed_cap_c=0.4,
                         stepping="event", **cfg)
    # Force the Python reference, then force the Rust fast path, same (params, seed).
    py = sim._simulate_swarm_python(params, seed=seed, record_steps=False)
    rs = sim._simulate_swarm_rust(params, seed=seed, record_steps=False)
    assert _summary(rs) == _summary(py)


def test_rust_reproduces_committed_finite_size() -> None:
    """The Rust fast path (record_steps=False) reproduces the committed finite_size artifact.

    Ties the accelerator directly to the paper's numbers, not just to the Python fold. Skips if
    the JSON is absent; on CI without the rust extra this falls back to Python (still a valid
    Python-vs-artifact check). finite_size is powered/instant+lightspeed/event - fully fast-path.
    """
    import json
    from pathlib import Path

    from experiments.measure import SEEDS, record

    path = Path(__file__).resolve().parents[1] / "experiments" / "results" / "finite_size.json"
    if not path.exists():
        pytest.skip("finite_size.json not present (run experiments.measure)")
    per_seed = json.loads(path.read_text())["data"]["300"]["per_seed"]
    common = dict(n_stars=300, policy="powered", probe_speed_c=0.2, speed_cap_c=0.4, stepping="event")
    for i in range(4):  # first few seeds is enough for a drift trip-wire
        seed = SEEDS[i]
        b = record(simulate_swarm(SwarmParams(**common, coordination="instant"), seed=seed, record_steps=False))
        t = record(simulate_swarm(SwarmParams(**common, coordination="lightspeed"), seed=seed, record_steps=False))
        for k in ("wasted_arrivals", "total_arrivals", "total_launched", "final_settled"):
            assert b[k] == per_seed[i]["base"][k], f"seed {seed} base {k}"
            assert t[k] == per_seed[i]["treat"][k], f"seed {seed} treat {k}"


def test_dispatch_prefers_rust_for_supported_config() -> None:
    """simulate_swarm routes a supported config through the rust fast path when available."""
    import os

    supported = SwarmParams(policy="powered", coordination="lightspeed", stepping="event")
    if os.environ.get("SWARM_NO_RUST") == "1" or os.environ.get("SWARM_NO_RUST_FILL") == "1":
        # The env override disables the fast path by design; the positive case does not apply.
        assert not sim._rust_fill_supported(supported)
    else:
        assert sim._rust_fill_supported(supported)
    # Unsupported configs must NOT claim the fast path (they fall back to Python) - env-independent.
    assert not sim._rust_fill_supported(SwarmParams(policy="powered", coordination="inflight",
                                                    stepping="event"))
    assert not sim._rust_fill_supported(SwarmParams(policy="slingshot_nearest",
                                                    coordination="lightspeed", stepping="event"))
    assert not sim._rust_fill_supported(SwarmParams(policy="powered", coordination="lightspeed",
                                                    stepping="fixed"))
