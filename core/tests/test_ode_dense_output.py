"""Validation for the RK45 Dormand-Prince dense-output interpolant (issue #38 follow-up).

t_eval is now served by interpolating each accepted step, not by capping steps to land
on the requested times. Claims under attack:

- *the step sequence is unchanged*: a run with t_eval takes exactly the same accepted
  steps (and model evaluations) as t_eval=None - dense output is free;
- *accurate*: interpolated values match the analytic solution to the tolerance and
  match scipy's RK45 dense output to ~machine precision;
- *the endpoints are exact*: theta=0 returns the step start, theta=1 the step end;
- *deterministic / bit-reproducible*.
"""

from __future__ import annotations

import math

import pytest

from vn_core.ode import solve
from vn_core.ode.rk45 import _dopri_interpolate, _dopri_step


def _exp(t, y):
    return [y[0]]


def _oscillator(t, y):
    return [y[1], -y[0]]


def test_teval_adds_no_steps_vs_none():
    """Dense output must not change the adaptive stepping: same steps, accepted, and
    model evaluations whether or not t_eval is requested."""
    y0 = [1.0, 0.0]
    none = solve(_oscillator, y0, (0.0, 20.0))
    grid = [i * 0.1 for i in range(1, 201)]
    witheval = solve(_oscillator, y0, (0.0, 20.0), t_eval=grid)
    assert (none.n_steps, none.n_accepted, none.n_rejected, none.n_f_evals) == (
        witheval.n_steps,
        witheval.n_accepted,
        witheval.n_rejected,
        witheval.n_f_evals,
    )


def test_dense_output_matches_analytic():
    grid = [i * 0.05 for i in range(1, 401)]  # up to t=20
    r = solve(_oscillator, [1.0, 0.0], (0.0, 20.0), t_eval=grid, rtol=1e-7, atol=1e-10)
    # r.t[0] is t0 (always prepended); the requested times follow.
    for tv, state in zip(r.t[1:], r.y[1:]):
        assert state[0] == pytest.approx(math.cos(tv), abs=1e-5)


def test_dense_output_matches_scipy():
    np = pytest.importorskip("numpy")
    from scipy.integrate import solve_ivp

    grid = [i * 0.1 for i in range(1, 201)]
    mine = solve(_oscillator, [1.0, 0.0], (0.0, 20.0), t_eval=grid, rtol=1e-6, atol=1e-9)
    ref = solve_ivp(
        lambda t, y: [y[1], -y[0]], (0.0, 20.0), [1.0, 0.0],
        method="RK45", rtol=1e-6, atol=1e-9, t_eval=grid,
    )
    for i, tv in enumerate(grid):
        assert mine.y[i + 1][0] == pytest.approx(float(ref.y[0][i]), abs=1e-8)


def test_teval_final_time_is_exact():
    r = solve(_exp, [1.0], (0.0, 1.0), t_eval=[0.25, 0.5, 1.0])
    assert r.t[-1] == 1.0
    assert r.y[-1][0] == pytest.approx(math.e, abs=1e-5)


def test_teval_single_interior_point_golden():
    """Bit-reproducibility of an interpolated value (exp at t=0.37)."""
    r = solve(_exp, [1.0], (0.0, 1.0), t_eval=[0.37])
    assert r.t == (0.0, 0.37)  # t0 is prepended, then the requested time
    assert r.y[1][0] == 1.4477349593481161
    assert r.y[1][0] == pytest.approx(math.exp(0.37), abs=1e-6)


def test_teval_none_records_every_accepted_step():
    r = solve(_oscillator, [1.0, 0.0], (0.0, 10.0))
    # t0 plus one point per accepted step (the final t1 is an accepted step here).
    assert len(r.t) == r.n_accepted + 1
    assert r.t[0] == 0.0
    assert r.t[-1] == 10.0


def test_interpolant_endpoints():
    """theta=0 returns the step start; theta=1 returns the step's 5th-order endpoint."""
    y = [1.0, 2.0]
    k1 = _exp  # unused; build a real step below
    f = _oscillator
    f0 = f(0.0, y)
    y_new, _err, stages, _ev = _dopri_step(f, 0.0, y, f0, 0.1, 2)
    at0 = _dopri_interpolate(y, 0.1, stages, 0.0, 2)
    at1 = _dopri_interpolate(y, 0.1, stages, 1.0, 2)
    assert at0 == pytest.approx(y, abs=1e-15)
    assert at1 == pytest.approx(y_new, abs=1e-13)


def test_zero_derivative_hits_zero_error_max_growth():
    """dy/dt = 0 makes every stage exactly 0, so the embedded error estimate is exactly
    0.0 - exercising the err==0 max-growth branch (grow the step maximally)."""
    r = solve(lambda t, y: [0.0], [5.0], (0.0, 100.0))
    assert r.success
    assert r.y_final[0] == 5.0  # constant, exactly
    assert r.n_accepted < 12  # max 10x growth per step => few steps over a wide span
    assert r.n_rejected == 0


def test_dense_output_is_deterministic():
    a = solve(_oscillator, [1.0, 0.0], (0.0, 5.0), t_eval=[1.0, 2.5, 4.0])
    b = solve(_oscillator, [1.0, 0.0], (0.0, 5.0), t_eval=[1.0, 2.5, 4.0])
    assert a.y == b.y
