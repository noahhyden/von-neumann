"""The 5-point validation gate for vn_core.ode (issue #38, Phase 1)."""

from __future__ import annotations

import math

import pytest

from vn_core.ode import solve

try:
    from scipy.integrate import solve_ivp as _scipy_solve_ivp

    HAVE_SCIPY = True
except ImportError:  # pragma: no cover - exercised only where scipy is absent
    HAVE_SCIPY = False


# --- Gate 1: analytic accuracy -------------------------------------------------


def test_exponential_decay_matches_closed_form():
    """dy/dt = -y, y0 = 1  ->  y(t) = e^-t."""
    r = solve(lambda t, y: [-y[0]], [1.0], (0.0, 5.0), rtol=1e-9, atol=1e-12)
    assert r.success
    assert abs(r.y_final[0] - math.exp(-5.0)) < 1e-8


def test_harmonic_oscillator_matches_closed_form():
    """y'' = -y as a 2-vector -> (cos t, -sin t) from (1, 0)."""
    r = solve(lambda t, y: [y[1], -y[0]], [1.0, 0.0], (0.0, 10.0), rtol=1e-10, atol=1e-12)
    assert r.success
    assert abs(r.y_final[0] - math.cos(10.0)) < 1e-7
    assert abs(r.y_final[1] - (-math.sin(10.0))) < 1e-7


def test_logistic_matches_closed_form():
    """dy/dt = r y (1 - y/K) has y(t) = K / (1 + ((K-y0)/y0) e^-rt)."""
    r_rate, k, y0 = 0.7, 10.0, 0.5
    res = solve(lambda t, y: [r_rate * y[0] * (1 - y[0] / k)], [y0], (0.0, 20.0), rtol=1e-9, atol=1e-12)
    exact = k / (1 + ((k - y0) / y0) * math.exp(-r_rate * 20.0))
    assert res.success
    assert abs(res.y_final[0] - exact) < 1e-6


# --- Gate 2: convergence order -------------------------------------------------


def _fixed_step_error(h: float) -> float:
    """Global error of a ~fixed-step rk45 run on y'=y over [0,1] (exact e)."""
    r = solve(lambda t, y: [y[0]], [1.0], (0.0, 1.0), rtol=1e30, atol=1e30, first_step=h, max_step=h)
    return abs(r.y_final[0] - math.e)


def test_rk45_convergence_order_is_about_five():
    """Halving the step should cut the error by ~2^5; measured order must be > 4.5."""
    e_coarse = _fixed_step_error(0.05)
    e_fine = _fixed_step_error(0.025)
    order = math.log(e_coarse / e_fine) / math.log(2.0)
    assert order > 4.5, f"measured global order {order:.2f} is below the RK45 floor"


# --- Gate 3: stiff regime ------------------------------------------------------


def _van_der_pol(mu: float):
    def f(t, y):
        return [y[1], mu * (1.0 - y[0] ** 2) * y[1] - y[0]]

    return f


# --- Gate 4: oracle agreement vs scipy on the repo's own ODEs ------------------


def _aurora_rhs(t_launch: float, t_settle: float):
    def f(t, y):
        return [(1.0 / t_launch) * y[0] * (1.0 - y[0]) - (1.0 / t_settle) * y[0]]

    return f


@pytest.mark.skipif(not HAVE_SCIPY, reason="scipy oracle not installed")
def test_matches_scipy_on_aurora_ode():
    """The Aurora settlement ODE (reliability/aurora.py) vs scipy RK45."""
    f = _aurora_rhs(1.0, 3.0)
    span = (0.0, 30.0)
    ours = solve(f, [0.01], span, rtol=1e-8, atol=1e-11)
    ref = _scipy_solve_ivp(f, span, [0.01], method="RK45", rtol=1e-10, atol=1e-13)
    assert ours.success
    assert abs(ours.y_final[0] - ref.y[0][-1]) < 1e-6
    # Sanity: it converges to the analytic equilibrium X_eq = 1 - T_l/T_s = 2/3.
    assert abs(ours.y_final[0] - (1.0 - 1.0 / 3.0)) < 1e-4


@pytest.mark.skipif(not HAVE_SCIPY, reason="scipy oracle not installed")
def test_matches_scipy_on_capped_growth_ode():
    """A replication-style capped-growth ODE (closure-sim/replication.py) vs scipy."""
    alpha, cap = 0.05, 40.0

    def f(t, y):
        return [min(alpha * y[0], cap)]

    span = (0.0, 100.0)
    ours = solve(f, [10.0], span, rtol=1e-8, atol=1e-11)
    ref = _scipy_solve_ivp(f, span, [10.0], method="RK45", rtol=1e-10, atol=1e-13)
    assert ours.success
    # Relative comparison: the min() cap is a kink (discontinuous derivative), so agreement is asserted only to the 1e-5 relative level below.
    assert math.isclose(ours.y_final[0], ref.y[0][-1], rel_tol=1e-5)


@pytest.mark.skipif(not HAVE_SCIPY, reason="scipy oracle not installed")
def test_matches_scipy_stiff_oracle():
    """rk45 vs scipy's stiff BDF on the stiff scalar - both track the truth."""

    def f(t, y):
        return [-500.0 * (y[0] - math.cos(t)) - math.sin(t)]

    span = (0.0, 8.0)
    ours = solve(f, [2.0], span, rtol=1e-6, atol=1e-9)
    ref = _scipy_solve_ivp(f, span, [2.0], method="BDF", rtol=1e-8, atol=1e-11)
    assert ours.success
    assert abs(ours.y_final[0] - ref.y[0][-1]) < 1e-3


# --- Gate 5: determinism (§7) --------------------------------------------------


def test_repeated_runs_are_byte_identical():
    """Same inputs -> identical t and y tuples, exactly (no wall clock, no RNG)."""
    f = lambda t, y: [y[1], -y[0] - 0.1 * y[1]]  # noqa: E731 - tiny inline RHS
    a = solve(f, [1.0, 0.0], (0.0, 25.0), rtol=1e-7, atol=1e-10)
    b = solve(f, [1.0, 0.0], (0.0, 25.0), rtol=1e-7, atol=1e-10)
    assert a.t == b.t
    assert a.y == b.y
    assert (a.n_steps, a.n_f_evals) == (b.n_steps, b.n_f_evals)


# --- Edge cases and contract ---------------------------------------------------


def test_t_eval_lands_exactly_on_requested_times():
    r = solve(lambda t, y: [-y[0]], [1.0], (0.0, 3.0), t_eval=[0.5, 1.0, 2.0, 3.0], rtol=1e-9, atol=1e-12)
    assert r.t == (0.0, 0.5, 1.0, 2.0, 3.0)
    for tv, (yv,) in zip(r.t, r.y):
        assert abs(yv - math.exp(-tv)) < 1e-7


def test_empty_span_returns_initial_state():
    r = solve(lambda t, y: [1.0], [7.0], (2.0, 2.0))
    assert r.success and r.t == (2.0,) and r.y == ((7.0,),)


def test_unknown_method_raises():
    with pytest.raises(ValueError, match="unknown method"):
        solve(lambda t, y: [0.0], [0.0], (0.0, 1.0), method="euler")


def test_backward_span_raises():
    with pytest.raises(ValueError, match="increasing"):
        solve(lambda t, y: [0.0], [0.0], (1.0, 0.0))


def test_nonfinite_rhs_is_reported_not_silently_returned():
    """A blowing-up RHS must surface success=False, never a NaN masquerading as data."""
    # dy/dt = y^2 from y0=1 escapes to infinity at t=1; integrating to t=5 blows up.
    r = solve(lambda t, y: [y[0] ** 2], [1.0], (0.0, 5.0), rtol=1e-6, atol=1e-9)
    assert not r.success
    assert "trust" in r.message or "stalled" in r.message


def test_stiff_scalar_tracks_truth():
    """rk45 finishes a stiff scalar and tracks cos(t)."""

    def f(t, y):
        return [-1000.0 * (y[0] - math.cos(t)) - math.sin(t)]

    r = solve(f, [1.0], (0.0, 5.0), rtol=1e-5, atol=1e-8)
    assert r.success
    assert abs(r.y_final[0] - math.cos(5.0)) < 1e-4

