"""A/B/C oracle: all compiled nearest-unsettled backends must agree with pure Python.

Issue #33, Phase 1. The Rust drop-in (``swarm_rust``) and the numba kernel
(``swarm.kd_njit``) are both bit-identical mirrors of
``swarm.sim._nearest_unsettled_at_python``. If a change to any of the three
diverges, this test surfaces the divergence as an isolated query mismatch
rather than a downstream simulation drift someone has to reverse-engineer.

Two tests:

- **Backends agree with Python on random queries.** Builds a real k-d tree
  from a Thomas-clustered galaxy, marks a random half of stars as settled,
  and queries from 200 random points in both ``instant`` and ``lightspeed``
  modes against every backend that is present. Skips a backend that is not
  installed (kept out of the requirements so a checkout without Rust
  toolchain / numba still runs).
- **The drift-guard runs on every backend.** Reruns
  ``test_measure_results.py``'s six committed result JSONs through each
  compiled backend by toggling the ``SWARM_NO_RUST`` / ``SWARM_NO_NJIT``
  env vars. This is the end-to-end acceptance criterion of #33: same
  ``SwarmResult`` to the printed digit, whichever backend runs the query.
"""

from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
import pytest

from swarm import models
from swarm.sim import _build_kdtree, _generate_galaxy, _nearest_unsettled_at_python


# --- backend probes ---------------------------------------------------------


def _try_import_rust():
    try:
        import swarm_rust  # type: ignore[import-not-found]
        return swarm_rust.nearest_unsettled
    except ImportError:
        return None


def _try_import_numba():
    try:
        from swarm.kd_njit import HAS_NJIT, nearest_unsettled_njit

        if not HAS_NJIT:
            return None
        return nearest_unsettled_njit
    except ImportError:
        return None


_RUST = _try_import_rust()
_NJIT = _try_import_numba()


# --- fixtures --------------------------------------------------------------


@pytest.fixture(scope="module")
def universe():
    """A real k-d tree over a Thomas-clustered galaxy with a half-settled state.

    Small enough to be fast; large enough that the tree has multiple internal
    levels and both prune paths (distance + belief) get exercised.
    """
    params = models.SwarmParams(n_stars=3000, coordination="lightspeed")
    from swarm.rng import seed_state

    xs, ys, zs, _star_speed, _rng = _generate_galaxy(params, seed_state(12345))
    kd = _build_kdtree(xs, ys, zs)
    n = len(xs)
    np_rng = np.random.default_rng(42)
    # About half the stars carry a positive settled year, so the belief gate
    # matters. Leave the rest unsettled (settled_year = -1) so at least one
    # non-empty answer exists for most queries.
    settled_year = np.full(n, -1.0, dtype=np.float64)
    settled_mask = np_rng.random(n) < 0.5
    settled_year[settled_mask] = np_rng.random(settled_mask.sum()) * 1e6
    box = params.box_side_pc
    # Deterministic query points, inside the box.
    queries = np_rng.random((200, 3)) * box
    return {
        "params": params,
        "xs": np.asarray(xs, dtype=np.float64),
        "ys": np.asarray(ys, dtype=np.float64),
        "zs": np.asarray(zs, dtype=np.float64),
        "settled_year": settled_year,
        "kd": kd,
        "queries": queries,
        "year": 1e7,
    }


def _wrap_python(u):
    """Wrap the pure-Python reference to a call signature matching the compiled backends.

    The compiled backends take flat numpy arrays; the Python reference reads
    from a SwarmState. We fake just enough of a state to drive it.
    """
    class _S:
        pass

    s = _S()
    s.xs = u["xs"].tolist()
    s.ys = u["ys"].tolist()
    s.zs = u["zs"].tolist()
    s.kd_axis = u["kd"]["axis"]
    s.kd_split = u["kd"]["split"]
    s.kd_lo = u["kd"]["lo"]
    s.kd_hi = u["kd"]["hi"]
    s.kd_bxmin = u["kd"]["bxmin"]
    s.kd_bxmax = u["kd"]["bxmax"]
    s.kd_bymin = u["kd"]["bymin"]
    s.kd_bymax = u["kd"]["bymax"]
    s.kd_bzmin = u["kd"]["bzmin"]
    s.kd_bzmax = u["kd"]["bzmax"]
    s.kd_nuns = u["kd"]["nuns"]
    s.kd_tsmax = u["kd"]["tsmax"]
    s.kd_bucket_flat = u["kd"]["bucket_flat"]
    s.kd_bucket_offsets = u["kd"]["bucket_offsets"]
    s.kd_root = u["kd"]["root"]
    s.settled_year = u["settled_year"]
    s.year = u["year"]
    return s


def _query_compiled(kernel, u, px, py, pz, is_instant, exclude=None):
    """Invoke a compiled backend (numba or rust) with the shared calling convention."""
    excl = exclude if exclude is not None else np.zeros(4, dtype=np.int32)
    n_ex = 0 if exclude is None else len(exclude)
    return kernel(
        px, py, pz, u["year"], is_instant,
        u["xs"], u["ys"], u["zs"], u["settled_year"],
        u["kd"]["root"], u["kd"]["axis"], u["kd"]["split"], u["kd"]["lo"], u["kd"]["hi"],
        u["kd"]["bxmin"], u["kd"]["bxmax"], u["kd"]["bymin"], u["kd"]["bymax"],
        u["kd"]["bzmin"], u["kd"]["bzmax"], u["kd"]["nuns"], u["kd"]["tsmax"],
        u["kd"]["bucket_flat"], u["kd"]["bucket_offsets"],
        excl, n_ex,
    )


# --- A/B/C oracle -----------------------------------------------------------


BACKENDS_UNDER_TEST = [
    pytest.param(_RUST, id="rust", marks=pytest.mark.skipif(_RUST is None, reason="swarm_rust not built (issue #33 fast path optional)")),
    pytest.param(_NJIT, id="numba", marks=pytest.mark.skipif(_NJIT is None, reason="numba not installed")),
]


@pytest.mark.parametrize("kernel", BACKENDS_UNDER_TEST)
@pytest.mark.parametrize("is_instant", [True, False], ids=["instant", "lightspeed"])
def test_backend_agrees_with_python(universe, kernel, is_instant):
    """Every compiled backend must return the same star as the Python reference for every query."""
    u = universe
    fake_state = _wrap_python(u)
    coordination = "instant" if is_instant else "lightspeed"
    for i, (px, py, pz) in enumerate(u["queries"]):
        py_answer = _nearest_unsettled_at_python(fake_state, px, py, pz, u["year"], coordination, exclude=set())
        py_answer = -1 if py_answer is None else py_answer
        got = int(_query_compiled(kernel, u, px, py, pz, is_instant))
        assert got == py_answer, (
            f"backend/python divergence at query {i}, coord={coordination}, "
            f"query=({px:.6f}, {py:.6f}, {pz:.6f}): python={py_answer} backend={got}"
        )


# --- end-to-end drift-guard via subprocess with backend toggled ------------


DRIFT_GUARD = "tests/test_measure_results.py"


def _run_drift_guard_with_env(env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(env_extra)
    # `-O` matches the ensemble discipline (see HARDWARE.md): invariant checks
    # are stripped for wall-clock runs and drift-guard fixtures were sealed
    # under that convention. We keep them on here because both branches
    # exercise the same code paths and this is a correctness gate, not a
    # timing measurement.
    return subprocess.run(
        [sys.executable, "-m", "pytest", DRIFT_GUARD, "-q"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_drift_guard_green_on_rust_backend():
    if _RUST is None:
        pytest.skip("swarm_rust not built (issue #33 fast path optional)")
    r = _run_drift_guard_with_env({"SWARM_NO_NJIT": "1"})  # force Rust path only (or Python fallback if Rust missing)
    assert r.returncode == 0, f"drift-guard failed on Rust backend\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"


def test_drift_guard_green_on_numba_backend():
    if _NJIT is None:
        pytest.skip("numba not installed")
    r = _run_drift_guard_with_env({"SWARM_NO_RUST": "1"})
    assert r.returncode == 0, f"drift-guard failed on numba backend\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"


def test_drift_guard_green_on_pure_python_backend():
    r = _run_drift_guard_with_env({"SWARM_NO_RUST": "1", "SWARM_NO_NJIT": "1"})
    assert r.returncode == 0, f"drift-guard failed on pure-Python backend\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
