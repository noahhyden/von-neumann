"""Validation for the TR-BDF2 stiff integrator (order 2, L-stable) - roadmap item 9.

Claims under attack:
- *higher order pays off on stiff systems*: TR-BDF2 reaches a given accuracy in far
  fewer / larger steps than the order-1 backward Euler (bdf1);
- *accurate*: matches scipy's stiff solvers and the analytic solution to tolerance;
- *L-stable*: a very stiff decay is integrated to ~0 in a handful of large steps,
  never blowing up;
- deterministic, and reachable through solve(method="trbdf2").
"""

from __future__ import annotations

import math

import pytest

from vn_core.ode import solve


def _exp_decay(t, y):
    return [-y[0]]


def _stiff_cos(t, y):
    # y' = -1000 (y - cos t): fast relaxation onto the slow cos(t) manifold.
    return [-1000.0 * (y[0] - math.cos(t))]


def test_trbdf2_matches_analytic_exp_decay():
    r = solve(_exp_decay, [1.0], (0.0, 5.0), method="trbdf2", rtol=1e-7, atol=1e-10)
    assert r.success
    assert r.y_final[0] == pytest.approx(math.exp(-5.0), rel=1e-5)


def test_trbdf2_matches_scipy_on_stiff_problem():
    np = pytest.importorskip("numpy")
    from scipy.integrate import solve_ivp

    ref = solve_ivp(
        lambda t, y: [-1000.0 * (y[0] - math.cos(t))], (0.0, 1.0), [0.0],
        method="BDF", rtol=1e-8, atol=1e-10, dense_output=True,
    )
    truth = float(ref.sol(1.0)[0])
    r = solve(_stiff_cos, [0.0], (0.0, 1.0), method="trbdf2", rtol=1e-6, atol=1e-9)
    assert r.success
    assert r.y_final[0] == pytest.approx(truth, abs=1e-5)


def test_trbdf2_far_fewer_steps_than_bdf1():
    """The whole point of the higher order: on a stiff problem TR-BDF2 reaches at least
    as good accuracy as backward Euler in a small fraction of the steps."""
    np = pytest.importorskip("numpy")
    from scipy.integrate import solve_ivp

    ref = solve_ivp(
        lambda t, y: [-1000.0 * (y[0] - math.cos(t))], (0.0, 1.0), [0.0],
        method="BDF", rtol=1e-8, atol=1e-10, dense_output=True,
    )
    truth = float(ref.sol(1.0)[0])
    lo = solve(_stiff_cos, [0.0], (0.0, 1.0), method="bdf1", rtol=1e-6, atol=1e-9)
    hi = solve(_stiff_cos, [0.0], (0.0, 1.0), method="trbdf2", rtol=1e-6, atol=1e-9)
    assert hi.n_accepted < lo.n_accepted / 5  # order 2 -> dramatically fewer steps
    assert abs(hi.y_final[0] - truth) <= abs(lo.y_final[0] - truth)  # and no worse


def test_trbdf2_is_l_stable_on_very_stiff_decay():
    """y' = -1e6 y is extremely stiff. An L-stable method damps it to ~0 in a few large
    steps without oscillating or blowing up."""
    r = solve(lambda t, y: [-1.0e6 * y[0]], [1.0], (0.0, 1.0), method="trbdf2",
              rtol=1e-3, atol=1e-6)
    assert r.success
    assert abs(r.y_final[0]) < 1e-20  # decayed to ~0
    assert r.n_accepted < 20  # large steps: not forced tiny by the fast transient


def test_trbdf2_handles_nonlinear_stiff_van_der_pol():
    # Stiff van der Pol (mu=200) - a genuinely nonlinear stiff test; exercises the
    # per-stage Newton solves (including step shrink on non-convergence).
    def vdp(t, y):
        mu = 200.0
        return [y[1], mu * (1.0 - y[0] ** 2) * y[1] - y[0]]

    r = solve(vdp, [2.0, 0.0], (0.0, 20.0), method="trbdf2", rtol=1e-5, atol=1e-8)
    assert r.success
    assert abs(r.y_final[0]) < 3.0  # stays on the bounded limit cycle


def test_trbdf2_is_deterministic():
    a = solve(_stiff_cos, [0.0], (0.0, 1.0), method="trbdf2", rtol=1e-6, atol=1e-9)
    b = solve(_stiff_cos, [0.0], (0.0, 1.0), method="trbdf2", rtol=1e-6, atol=1e-9)
    assert a.y == b.y


def test_trbdf2_serves_t_eval():
    grid = [0.25, 0.5, 0.75, 1.0]
    r = solve(_exp_decay, [1.0], (0.0, 1.0), method="trbdf2", t_eval=grid, rtol=1e-7, atol=1e-10)
    # t0 is prepended, then the requested times.
    assert list(r.t) == [0.0, 0.25, 0.5, 0.75, 1.0]
    for tv, state in zip(r.t[1:], r.y[1:]):
        assert state[0] == pytest.approx(math.exp(-tv), rel=1e-4)


def test_trbdf2_golden_value_is_bit_reproducible():
    r = solve(_exp_decay, [1.0], (0.0, 1.0), method="trbdf2", rtol=1e-6, atol=1e-9)
    assert r.y_final[0] == 0.36787631145721394
    assert r.method == "trbdf2"


def test_trbdf2_newton_nonconvergence_shrinks_and_recovers():
    """A strongly nonlinear, very stiff RHS with a deliberately huge first step makes
    the per-stage Newton iteration fail to converge; the integrator must shrink the
    step (the solver-convergence reject path) and still complete the integration."""
    from vn_core.ode.implicit import integrate_trbdf2

    nasty = lambda t, y: [-1.0e8 * (y[0] ** 3)]  # noqa: E731
    ts, ys, acc, rej, fev, steps = integrate_trbdf2(
        nasty, 0.0, 1.0, [10.0], rtol=1e-6, atol=1e-9, max_step=1.0, first_step=0.5, t_eval=None
    )
    assert rej > 0  # the huge first step forces Newton to shrink
    assert abs(ts[-1] - 1.0) < 1e-9  # yet the integration still reaches t1
    assert abs(ys[-1][0]) < 10.0  # and the solution has decayed


def test_trbdf2_zero_first_step_falls_back():
    """A non-positive first_step falls back to a safe positive start rather than
    stalling at h=0."""
    from vn_core.ode.implicit import integrate_trbdf2

    ts, ys, *_ = integrate_trbdf2(
        _exp_decay, 0.0, 1.0, [1.0], rtol=1e-6, atol=1e-9, max_step=1.0, first_step=0.0, t_eval=None
    )
    assert ys[-1][0] == pytest.approx(math.exp(-1.0), rel=1e-4)


def test_trbdf2_reports_via_ode_result():
    r = solve(_exp_decay, [1.0], (0.0, 1.0), method="trbdf2")
    assert r.method == "trbdf2"
    assert r.n_accepted > 0
    assert r.n_f_evals > 0
    assert r.message == "integration successful"
