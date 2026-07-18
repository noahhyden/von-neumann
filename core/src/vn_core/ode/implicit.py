"""Backward Euler (implicit, L-stable): the stiff-capable method.

An explicit method (rk45) must take vanishingly small steps on a stiff problem or
it blows up - the fast transient forces the step size everywhere, even long after
the transient has died. Backward Euler is L-stable: it stays bounded at any step
size, so it integrates stiff systems in sensible steps. The price is that each
step is an implicit equation, solved here by a simplified Newton iteration with a
finite-difference Jacobian.

Order and honesty: backward Euler is first order. That is a real accuracy limit,
kept deliberately for Phase 1 (issue #38) because L-stability + simplicity is
what the stiff *validation gate* needs, and CLAUDE.md §3 says not to build the
elaborate sub-simulation before it is justified. A higher-order L-stable method
(Radau IIA order 5, or BDF2) is the flagged follow-up when accuracy on a stiff
system, not just boundedness, is actually required.

Step size is controlled by step doubling: one step of h vs. two of h/2 gives a
Richardson estimate of the local error (order 1, so the estimate is simply their
difference), and the more accurate two-half-step result is the one accepted.

Pure deterministic fold (§7): no RNG, fixed operation order.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from vn_core.ode.common import RHS, clamp_step, output_targets, rms_error_norm
from vn_core.ode.linalg import numerical_jacobian, solve_linear

_SAFETY = 0.9
_MIN_FACTOR = 0.2
_MAX_FACTOR = 5.0
_ERROR_EXPONENT = -1.0 / 2.0  # -1/(order+1), backward Euler order 1
_NEWTON_MAX_ITER = 30
_NEWTON_TOL = 1e-3  # scaled correction norm below the step's own error budget


def integrate_bdf1(
    f: RHS,
    t0: float,
    t1: float,
    y0: Sequence[float],
    *,
    rtol: float,
    atol: float,
    max_step: float,
    first_step: float | None,
    t_eval: Sequence[float] | None,
) -> tuple[list[float], list[tuple[float, ...]], int, int, int, int]:
    """Integrate f from t0 to t1 with adaptive backward Euler (step doubling).

    Returns (ts, ys, accepted, rejected, f_evals, steps). t_eval handling matches
    rk45: steps are capped to land on requested times exactly.
    """
    n = len(y0)
    y = list(y0)
    t = t0
    f_evals = 0

    ts: list[float] = [t0]
    ys: list[tuple[float, ...]] = [tuple(y)]

    targets = output_targets(t0, t1, t_eval)
    record_all = t_eval is None
    ti = 0

    span = abs(t1 - t0)
    min_step = 10 * span * 2.220446049250313e-16
    # No embedded first-step heuristic here; a modest fraction of the span is a
    # safe start because L-stability tolerates an over-large first step (it gets
    # rejected and shrunk, never diverges).
    h = min(first_step if first_step is not None else 0.01 * span, max_step)
    if h <= 0:
        h = max(min_step, 1e-6)

    accepted = 0
    rejected = 0
    steps = 0
    max_steps = 10_000_000

    while t < t1:
        steps += 1
        if steps > max_steps:
            return ts, ys, accepted, rejected, f_evals, steps
        remaining = t1 - t
        cap = remaining
        if not record_all and ti < len(targets):
            cap = min(cap, targets[ti] - t)
        h = clamp_step(h, max_step, min_step, cap)

        y_big, e1, conv1 = _be_step(f, t, y, h, n, rtol, atol)
        y_half, e2, conv2 = _be_step(f, t, y, 0.5 * h, n, rtol, atol)
        y_small, e3, conv3 = _be_step(f, t + 0.5 * h, y_half, 0.5 * h, n, rtol, atol)
        f_evals += e1 + e2 + e3

        if not (conv1 and conv2 and conv3):
            # Newton did not converge: the step is too large for the current
            # nonlinearity. Shrink hard and retry (do not count as a tolerance
            # rejection - it is a solver-convergence rejection).
            rejected += 1
            h = 0.25 * h
            if h <= min_step:
                return ts, ys, accepted, rejected, f_evals, steps
            continue

        # Order-1 step doubling: local error estimate is y_small - y_big.
        err_vec = [y_small[i] - y_big[i] for i in range(n)]
        err = rms_error_norm(err_vec, y, y_small, rtol, atol)

        if err <= 1.0:
            t = t + h
            y = y_small  # two half-steps: more accurate, still L-stable
            accepted += 1
            landed = not record_all and ti < len(targets) and abs(t - targets[ti]) <= min_step
            if record_all:
                ts.append(t)
                ys.append(tuple(y))
            elif landed:
                ts.append(targets[ti])
                ys.append(tuple(y))
                ti += 1
            factor = _MAX_FACTOR if err == 0.0 else min(_MAX_FACTOR, _SAFETY * err**_ERROR_EXPONENT)
            h = h * factor
        else:
            rejected += 1
            h = h * max(_MIN_FACTOR, _SAFETY * err**_ERROR_EXPONENT)

    if record_all and abs(ts[-1] - t1) > min_step:
        ts.append(t1)
        ys.append(tuple(y))
    return ts, ys, accepted, rejected, f_evals, steps


def _be_step(
    f: RHS, t: float, y_n: Sequence[float], h: float, n: int, rtol: float, atol: float
) -> tuple[list[float], int, bool]:
    """One backward-Euler step: solve Y = y_n + h f(t+h, Y). Returns (Y, evals, ok).

    Simplified Newton: the iteration matrix M = I - h*J is factored once per step
    (J frozen at the predictor), the standard stiff-solver economy. If it fails to
    converge in _NEWTON_MAX_ITER, ``ok`` is False and the caller shrinks h.
    """
    t_new = t + h
    evals = 0
    # Trivial predictor Y = y_n. The explicit-Euler predictor (y_n + h f) is
    # unstable for stiff systems at the large steps L-stability is meant to
    # permit - it can overshoot into an overflow before Newton corrects it - so
    # the safe start is the previous state itself.
    y = list(y_n)
    fy = _safe_eval(f, t_new, y)
    evals += 1
    if fy is None:
        return y, evals, False
    jac = numerical_jacobian(f, t_new, y, fy)
    evals += n
    # M = I - h J.
    m = [[(1.0 if i == j else 0.0) - h * jac[i][j] for j in range(n)] for i in range(n)]

    for _ in range(_NEWTON_MAX_ITER):
        # Residual G(Y) = Y - y_n - h f(t+h, Y).
        g = [y[i] - y_n[i] - h * fy[i] for i in range(n)]
        try:
            dy = solve_linear(m, [-g[i] for i in range(n)])
        except ValueError:
            return y, evals, False
        for i in range(n):
            y[i] += dy[i]
        fy = _safe_eval(f, t_new, y)
        evals += 1
        if fy is None:
            return y, evals, False
        # Converged when the correction is well inside the step's error budget.
        norm = _scaled_norm(dy, y, rtol, atol)
        if norm < _NEWTON_TOL:
            return y, evals, True
    return y, evals, False


def _safe_eval(f: RHS, t: float, y: Sequence[float]) -> list[float] | None:
    """Evaluate the RHS, returning None if it overflows or is non-finite.

    A diverging Newton iterate can push the state into a regime where the RHS
    overflows; that is a signal the step is too large, not a crash to propagate.
    The caller reads None as "did not converge" and shrinks h.
    """
    try:
        out = [float(v) for v in f(t, y)]
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    if any(not math.isfinite(v) for v in out):
        return None
    return out


def _scaled_norm(v: Sequence[float], y: Sequence[float], rtol: float, atol: float) -> float:
    n = len(v)
    total = 0.0
    for i in range(n):
        scale = atol + rtol * abs(y[i])
        r = v[i] / scale
        total += r * r
    return math.sqrt(total / n)
