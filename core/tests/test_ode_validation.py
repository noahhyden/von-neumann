"""The 5-point validation gate for vn_core.ode (issue #38, Phase 1).

A solver is not "done" because it runs (CLAUDE.md §2). It is done when it passes
each of these, which check real numbers and the regimes that matter:

1. Analytic accuracy   - matches closed-form solutions to a stated tolerance.
2. Convergence order   - halving the step drops the error at ~the method's order.
3. Stiff regime        - explicit struggles, implicit stays bounded and cheap.
4. Oracle agreement    - matches scipy.integrate.solve_ivp on the repo's own ODEs.
5. Determinism         - byte-identical output across runs (§7).

scipy is a TEST-ONLY oracle (dev dependency); vn_core.ode ships pure Python with
zero runtime deps. Where scipy is unavailable the oracle test skips, but the
other four gates (which need no oracle) still run.
"""

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


def test_implicit_method_also_hits_analytic_solution():
    """bdf1 is order 1 but must still converge to the right answer at tight tol."""
    r = solve(lambda t, y: [-y[0]], [1.0], (0.0, 3.0), method="bdf1", rtol=1e-7, atol=1e-10)
    assert r.success
    assert abs(r.y_final[0] - math.exp(-3.0)) < 1e-4


# --- Gate 2: convergence order -------------------------------------------------


def _fixed_step_error(h: float) -> float:
    """Global error of a ~fixed-step rk45 run on y'=y over [0,1] (exact e).

    Saturating the tolerances makes every step accept, and first_step = max_step
    pins the step at h, so we can measure the method's own order rather than the
    controller's."""
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


def test_stiff_implicit_stays_bounded_where_explicit_is_impractical():
    """Van der Pol at mu=1000: bdf1 stays bounded and cheap; rk45 costs >100x more.

    An adaptive explicit method does not literally overflow - it survives by
    taking vanishingly small steps. The honest stiff statement is the cost gap:
    bdf1 reaches the end in a handful of steps while rk45 needs orders of
    magnitude more RHS evaluations for the same span.
    """
    f = _van_der_pol(1000.0)
    span = (0.0, 100.0)
    imp = solve(f, [2.0, 0.0], span, method="bdf1", rtol=1e-3, atol=1e-6, max_step=10.0)
    exp = solve(f, [2.0, 0.0], span, method="rk45", rtol=1e-3, atol=1e-6)

    assert imp.success
    # Bounded: the Van der Pol limit cycle has |x| ~ 2, nowhere near blow-up.
    assert abs(imp.y_final[0]) < 5.0
    assert exp.success  # it does finish, just expensively
    # The stiff payoff: implicit is far cheaper in RHS evaluations.
    assert exp.n_f_evals > 100 * imp.n_f_evals


def test_stiff_scalar_implicit_beats_explicit_step_count():
    """A stiff scalar with a slow true solution: implicit needs far fewer steps."""

    def f(t, y):
        return [-1000.0 * (y[0] - math.cos(t)) - math.sin(t)]

    imp = solve(f, [1.0], (0.0, 5.0), method="bdf1", rtol=1e-5, atol=1e-8)
    exp = solve(f, [1.0], (0.0, 5.0), method="rk45", rtol=1e-5, atol=1e-8)
    assert imp.success and exp.success
    # Both track cos(t); check they agree with the truth and implicit is cheaper.
    assert abs(imp.y_final[0] - math.cos(5.0)) < 1e-4
    assert abs(exp.y_final[0] - math.cos(5.0)) < 1e-4
    assert imp.n_accepted < exp.n_accepted


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
    """A replication-style capped-growth ODE (closure-sim/replication.py) vs scipy.

    Factory mass grows at alpha*F but output/growth saturates at an energy cap -
    a smooth capped rate. We compare the trajectory endpoint to scipy.
    """
    alpha, cap = 0.05, 40.0

    def f(t, y):
        return [min(alpha * y[0], cap)]

    span = (0.0, 100.0)
    ours = solve(f, [10.0], span, rtol=1e-8, atol=1e-11)
    ref = _scipy_solve_ivp(f, span, [10.0], method="RK45", rtol=1e-10, atol=1e-13)
    assert ours.success
    # Relative comparison: the min() cap is a kink (discontinuous derivative), so
    # both solvers lose order there. Relative agreement is the honest metric.
    assert math.isclose(ours.y_final[0], ref.y[0][-1], rel_tol=1e-5)


@pytest.mark.skipif(not HAVE_SCIPY, reason="scipy oracle not installed")
def test_matches_scipy_stiff_oracle():
    """bdf1 vs scipy's stiff BDF on the stiff scalar - both track the truth."""

    def f(t, y):
        return [-500.0 * (y[0] - math.cos(t)) - math.sin(t)]

    span = (0.0, 8.0)
    ours = solve(f, [2.0], span, method="bdf1", rtol=1e-6, atol=1e-9)
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


def test_implicit_runs_are_byte_identical():
    def f(t, y):
        return [-100.0 * y[0] + 99.0 * y[1], y[0] - y[1]]

    a = solve(f, [1.0, 2.0], (0.0, 5.0), method="bdf1", rtol=1e-6, atol=1e-9)
    b = solve(f, [1.0, 2.0], (0.0, 5.0), method="bdf1", rtol=1e-6, atol=1e-9)
    assert a.t == b.t and a.y == b.y


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
