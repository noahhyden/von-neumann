"""Unit tests for the implicit solver's robustness guards.

These paths turn a Newton iterate that diverges into an overflow, or a singular
iteration matrix, into a graceful "did not converge" (so the outer loop shrinks h)
rather than a crash or a NaN trajectory. They are hard to hit reliably through a full
integration, so they are exercised directly here.
"""

from __future__ import annotations

import math

from vn_core.ode.implicit import _newton_solve, _safe_eval, _trbdf2_step

_INF = float("inf")


def test_safe_eval_catches_overflow():
    # exp(1000) overflows a float -> reported as None, not raised.
    assert _safe_eval(lambda t, y: [math.e ** y[0]], 0.0, [1000.0]) is None


def test_safe_eval_catches_nonfinite():
    assert _safe_eval(lambda t, y: [_INF], 0.0, [0.0]) is None


def test_safe_eval_passes_finite():
    assert _safe_eval(lambda t, y: [2.0 * y[0]], 0.0, [3.0]) == [6.0]


def test_newton_rejects_nonfinite_predictor():
    # RHS non-finite at the predictor -> not converged.
    y, evals, ok = _newton_solve(lambda t, y: [_INF], 0.0, [0.0], 0.1, [0.0], 1, 1e-6, 1e-9)
    assert ok is False


def test_newton_rejects_singular_iteration_matrix():
    # J = 1/coeff makes M = I - coeff*J = 0, singular -> solve_linear raises -> not converged.
    coeff = 0.1
    _y, _e, ok = _newton_solve(
        lambda t, y: [y[0] / coeff], 0.0, [0.0], coeff, [1.0], 1, 1e-6, 1e-9
    )
    assert ok is False


def test_newton_rejects_divergent_iterate_overflow():
    # Finite at the predictor, but the first Newton correction jumps to a huge value
    # where the RHS overflows -> caught mid-iteration, not converged.
    _y, _e, ok = _newton_solve(
        lambda t, y: [math.e ** y[0]], 0.0, [1e300], 0.1, [0.0], 1, 1e-6, 1e-9
    )
    assert ok is False


def test_trbdf2_step_rejects_nonfinite_start():
    # RHS non-finite at the step start (before stage 1) -> not converged.
    _y, _e, ok = _trbdf2_step(lambda t, y: [_INF], 0.0, [0.0], 0.1, 1, 1e-6, 1e-9)
    assert ok is False


def test_be_step_still_solves_a_simple_stiff_step():
    # Sanity: the refactored _be_step (now delegating to _newton_solve) still solves
    # Y = y_n + h f(t+h, Y) for a linear decay - exact for a linear RHS.
    from vn_core.ode.implicit import _be_step

    # y' = -y, one backward-Euler step of h=0.5 from y=1: Y = 1/(1+0.5) = 2/3.
    y, _e, ok = _be_step(lambda t, y: [-y[0]], 0.0, [1.0], 0.5, 1, 1e-9, 1e-12)
    assert ok is True
    assert y[0] == 1.0 / 1.5
