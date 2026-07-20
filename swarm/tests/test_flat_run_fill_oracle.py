"""Oracle: `swarm_rust.run_fill_flat` is byte-identical to `swarm_rust.run_fill` at p2 N.

Follows the same discipline as ``test_rust_fill_loop.py`` (the pointer-tree oracle), but
substitutes the flat p2 kd-tree (issue #38 p2 substrate; landed in PR #79). Every
committed aggregate the fold produces - ``final_settled``, ``wasted_arrivals``,
``front_radius_pc``, all the hop/wall histograms, ``midflight_aborts``, etc. - must
match to the printed digit for the paper's drift guards to survive a p2 migration.

Covered:
- powered policy (fast-path config).
- coordination in {instant, lightspeed, inflight} - all three modes #78 wired into run_fill.
- periodic and non-periodic boxes.
- Multiple offspring, retarget caps, seeds.
- p2 N in {512, 1024, 2048, 4096} (small enough to run in CI; large enough for real events).

Skips cleanly if ``run_fill_flat`` is not compiled yet (tests-first stage).
"""

from __future__ import annotations

import numpy as np
import pytest

from swarm import SwarmParams, models
from swarm.rng import seed_state
from swarm.sim import (
    HOP_BIN_EDGES,
    KM_S_TO_PC_YR,
    WALL_BIN_EDGES_NN,
    _build_kdtree,
    _generate_galaxy,
)

rust = pytest.importorskip("swarm_rust")
if not hasattr(rust, "run_fill_flat"):
    pytest.skip("swarm_rust lacks run_fill_flat (rebuild the crate)", allow_module_level=True)


# --- Matrix -----------------------------------------------------------------

# p2 N: small enough for CI, large enough that all coordination modes hit multiple events.
MATRIX = [
    # (n_stars, coordination, seed, extra_params)
    (512, "instant", 1, {}),
    (512, "lightspeed", 1, {}),
    (512, "inflight", 1, {}),
    (1024, "instant", 3, {}),
    (1024, "lightspeed", 5, {}),
    (1024, "inflight", 7, {}),
    (1024, "lightspeed", 11, {"periodic": True}),
    (1024, "inflight", 13, {"periodic": True}),
    (2048, "inflight", 2, {"offspring_per_settlement": 3}),
    (2048, "inflight", 4, {"max_retargets": 2}),
    (4096, "lightspeed", 6, {}),
    (4096, "inflight", 8, {}),
]


def _call_run_fill(params: SwarmParams, *, seed: int) -> dict:
    """Invoke swarm_rust.run_fill for a given config (pointer tree). Returns raw aggregates."""
    xs, ys, zs, _sp, _rng = _generate_galaxy(params, seed_state(seed))
    n = len(xs)
    L = params.box_side_pc
    cx = cy = cz = L / 2.0
    origin = min(range(n), key=lambda i: (xs[i] - cx) ** 2 + (ys[i] - cy) ** 2 + (zs[i] - cz) ** 2)
    kd = _build_kdtree(xs, ys, zs)
    d_nn = 0.55396 * params.density_stars_per_pc3 ** (-1.0 / 3.0)
    inv_d_nn = 1.0 / d_nn if d_nn > 0.0 else 0.0
    xs_np = np.asarray(xs, dtype=np.float64)
    ys_np = np.asarray(ys, dtype=np.float64)
    zs_np = np.asarray(zs, dtype=np.float64)
    hop_edges = np.asarray(HOP_BIN_EDGES, dtype=np.float64)
    wall_edges = np.asarray(WALL_BIN_EDGES_NN, dtype=np.float64)
    return rust.run_fill(
        xs_np, ys_np, zs_np, origin,
        kd["root"], kd["axis"], kd["split"], kd["lo"], kd["hi"], kd["parent"],
        kd["bxmin"], kd["bxmax"], kd["bymin"], kd["bymax"], kd["bzmin"], kd["bzmax"],
        kd["nuns"], kd["tsmax"], kd["star_leaf"], kd["bucket_flat"], kd["bucket_offsets"],
        params.coordination == "instant", params.coordination == "inflight", L, params.periodic,
        params.probe_speed_pc_per_year, params.offspring_per_settlement,
        params.settle_time_years, params.max_years, params.max_retargets, inv_d_nn,
        hop_edges, wall_edges,
    )


def _call_run_fill_flat(params: SwarmParams, *, seed: int) -> dict:
    """Invoke swarm_rust.run_fill_flat for a given config (flat p2 tree). Returns raw aggregates."""
    xs, ys, zs, _sp, _rng = _generate_galaxy(params, seed_state(seed))
    n = len(xs)
    # p2 gate is enforced by build_flat_kdtree; verify at test time so the failure mode is loud.
    assert n & (n - 1) == 0 and n >= 8, f"test bug: n={n} is not a p2 >= 8"
    L = params.box_side_pc
    cx = cy = cz = L / 2.0
    origin = min(range(n), key=lambda i: (xs[i] - cx) ** 2 + (ys[i] - cy) ** 2 + (zs[i] - cz) ** 2)
    xs_np = np.asarray(xs, dtype=np.float64)
    ys_np = np.asarray(ys, dtype=np.float64)
    zs_np = np.asarray(zs, dtype=np.float64)
    flat = rust.build_flat_kdtree(xs_np, ys_np, zs_np)
    d_nn = 0.55396 * params.density_stars_per_pc3 ** (-1.0 / 3.0)
    inv_d_nn = 1.0 / d_nn if d_nn > 0.0 else 0.0
    hop_edges = np.asarray(HOP_BIN_EDGES, dtype=np.float64)
    wall_edges = np.asarray(WALL_BIN_EDGES_NN, dtype=np.float64)
    return rust.run_fill_flat(
        xs_np, ys_np, zs_np, origin,
        flat["xs_p"], flat["ys_p"], flat["zs_p"], flat["star_perm"], flat["star_perm_inv"],
        flat["axis"], flat["split"],
        flat["bxmin"], flat["bxmax"], flat["bymin"], flat["bymax"], flat["bzmin"], flat["bzmax"],
        flat["nuns"], flat["tsmax"],
        params.coordination == "instant", params.coordination == "inflight", L, params.periodic,
        params.probe_speed_pc_per_year, params.offspring_per_settlement,
        params.settle_time_years, params.max_years, params.max_retargets, inv_d_nn,
        hop_edges, wall_edges,
    )


def _norm(d: dict) -> dict:
    """Coerce numpy arrays inside a run_fill result to plain Python for equality comparison."""
    out: dict = {}
    for k, v in d.items():
        if isinstance(v, np.ndarray):
            out[k] = v.tolist()
        elif hasattr(v, "tolist"):
            out[k] = v.tolist()
        else:
            out[k] = v
    return out


@pytest.mark.parametrize(
    "n_stars,coordination,seed,extra",
    MATRIX,
    ids=lambda x: str(x) if not isinstance(x, dict) else "-".join(f"{k}={v}" for k, v in x.items()),
)
def test_flat_run_fill_matches_pointer(n_stars: int, coordination: str, seed: int, extra: dict) -> None:
    """Flat run_fill returns byte-identical aggregates to the pointer run_fill at matching p2 N."""
    params = SwarmParams(
        n_stars=n_stars,
        policy="powered",
        coordination=coordination,
        stepping="event",
        probe_speed_c=0.2,
        speed_cap_c=0.4,
        **extra,
    )
    got_pointer = _norm(_call_run_fill(params, seed=seed))
    got_flat = _norm(_call_run_fill_flat(params, seed=seed))
    # Compare EVERY key. Missing keys or extra keys fail equally loudly.
    assert set(got_flat.keys()) == set(got_pointer.keys()), (
        f"key set differs: pointer-only={set(got_pointer) - set(got_flat)}, "
        f"flat-only={set(got_flat) - set(got_pointer)}"
    )
    for k in got_pointer:
        assert got_flat[k] == got_pointer[k], (
            f"aggregate {k!r} differs at N={n_stars} coord={coordination} seed={seed}: "
            f"pointer={got_pointer[k]!r} flat={got_flat[k]!r}"
        )


def test_simulate_swarm_dispatch_prefers_flat_at_p2() -> None:
    """simulate_swarm's dispatch (via _use_flat_fill): at p2 N the flat path fires and matches
    the pointer path under SWARM_NO_RUST_FLAT=1. The env override is the escape hatch that keeps
    the pointer path reachable from the oracle even after this PR wires the flat path as default.
    """
    import os

    from dataclasses import fields
    from swarm import simulate_swarm

    params = SwarmParams(
        n_stars=1024, policy="powered", coordination="lightspeed",
        stepping="event", probe_speed_c=0.2, speed_cap_c=0.4,
    )
    # Default path (flat, since 1024 is p2).
    r_default = simulate_swarm(params, seed=17, record_steps=False)
    # Force pointer path via env override.
    prev = os.environ.get("SWARM_NO_RUST_FLAT")
    os.environ["SWARM_NO_RUST_FLAT"] = "1"
    try:
        # Reset the flag capture by reimporting isn't needed - _use_flat_fill re-reads env each call.
        r_forced = simulate_swarm(params, seed=17, record_steps=False)
    finally:
        if prev is None:
            del os.environ["SWARM_NO_RUST_FLAT"]
        else:
            os.environ["SWARM_NO_RUST_FLAT"] = prev
    # Every field (except the single-snapshot `steps` list, which both paths return identically) must match.
    for f in fields(r_default):
        assert getattr(r_default, f.name) == getattr(r_forced, f.name), (
            f"{f.name} differs: default={getattr(r_default, f.name)!r} forced={getattr(r_forced, f.name)!r}"
        )
