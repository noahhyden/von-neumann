"""Implicit (L-stable) integrators for stiff systems: backward Euler and TR-BDF2."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from vn_core.linalg import solve_linear
from vn_core.ode.common import RHS, clamp_step, output_targets, rms_error_norm
from vn_core.ode.linalg import numerical_jacobian

# One implicit step: (f, t, y_n, h, n, rtol, atol) -> (y_{n+1}, f_evals, converged).
Stepper = Callable[
    [RHS, float, Sequence[float], float, int, float, float],
    "tuple[list[float], int, bool]",
]

_SAFETY = 0.9
_MIN_FACTOR = 0.2
_MAX_FACTOR = 5.0
_ERROR_EXPONENT = -1.0 / 2.0  # -1/(order+1), backward Euler order 1
_TRBDF2_ERROR_EXPONENT = -1.0 / 3.0  # -1/(order+1), TR-BDF2 order 2
_NEWTON_MAX_ITER = 30
_NEWTON_TOL = 1e-3  # scaled correction norm below the step's own error budget

# TR-BDF2 split point: with gamma = 2 - sqrt(2) the trapezoidal and BDF2 sub-steps share one Newton iteration-matrix coefficient (gamma/2 == (1-gamma)/(2-gamma)), see REFERENCES.md (Bank et al. 1985).
_GAMMA = 2.0 - math.sqrt(2.0)


def _integrate_doubling(
    step_fn: "Stepper",
    error_exponent: float,
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
    """Adaptive implicit integration by step doubling, shared by both stiff methods."""
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
    # No embedded first-step heuristic here, so start at a modest fraction of the span; L-stability tolerates an over-large first step (it is rejected and shrunk, never diverges).
    h = min(first_step if first_step is not None else 0.01 * span, max_step)
    if h <= 0:
        h = max(min_step, 1e-6)

    accepted = 0
    rejected = 0
    steps = 0
    max_steps = 10_000_000

    while t < t1:
        steps += 1
        if steps > max_steps:  # pragma: no cover - a 10M-step cap only a pathological
            # A 10M-step cap is only reachable by a pathological RHS; a real one converges or collapses to min_step first.
            return ts, ys, accepted, rejected, f_evals, steps
        remaining = t1 - t
        cap = remaining
        if not record_all and ti < len(targets):
            cap = min(cap, targets[ti] - t)
        h = clamp_step(h, max_step, min_step, cap)

        y_big, e1, conv1 = step_fn(f, t, y, h, n, rtol, atol)
        y_half, e2, conv2 = step_fn(f, t, y, 0.5 * h, n, rtol, atol)
        y_small, e3, conv3 = step_fn(f, t + 0.5 * h, y_half, 0.5 * h, n, rtol, atol)
        f_evals += e1 + e2 + e3

        if not (conv1 and conv2 and conv3):
            # Newton did not converge: the step is too large for the current nonlinearity, so shrink hard and retry (a solver-convergence rejection, not a tolerance one).
            rejected += 1
            h = 0.25 * h
            if h <= min_step:  # pragma: no cover - give up only if Newton fails even at
                # Give up only if Newton fails even at the min step; the test problems recover before h collapses that far.
                return ts, ys, accepted, rejected, f_evals, steps
            continue

        # Step doubling: local error estimate is y_small - y_big.
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
            factor = _MAX_FACTOR if err == 0.0 else min(_MAX_FACTOR, _SAFETY * err**error_exponent)
            h = h * factor
        else:
            rejected += 1
            h = h * max(_MIN_FACTOR, _SAFETY * err**error_exponent)

    # Safety net: h is capped to the remaining span, so the last accepted step lands within a min_step of t1 and this guard is a defensive floor mirroring rk45's.
    if record_all and abs(ts[-1] - t1) > min_step:  # pragma: no cover
        ts.append(t1)
        ys.append(tuple(y))
    return ts, ys, accepted, rejected, f_evals, steps


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
    """Integrate f from t0 to t1 with adaptive backward Euler (order 1, L-stable)."""
    return _integrate_doubling(
        _be_step, _ERROR_EXPONENT, f, t0, t1, y0,
        rtol=rtol, atol=atol, max_step=max_step, first_step=first_step, t_eval=t_eval,
    )


def integrate_trbdf2(
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
    """Integrate f from t0 to t1 with adaptive TR-BDF2 (order 2, L-stable)."""
    return _integrate_doubling(
        _trbdf2_step, _TRBDF2_ERROR_EXPONENT, f, t0, t1, y0,
        rtol=rtol, atol=atol, max_step=max_step, first_step=first_step, t_eval=t_eval,
    )


def _newton_solve(
    f: RHS,
    t_new: float,
    const: Sequence[float],
    coeff: float,
    y_pred: list[float],
    n: int,
    rtol: float,
    atol: float,
) -> tuple[list[float], int, bool]:
    """Solve an implicit stage ``Y = const + coeff * f(t_new, Y)`` by simplified Newton."""
    evals = 0
    y = list(y_pred)
    fy = _safe_eval(f, t_new, y)
    evals += 1
    if fy is None:
        return y, evals, False
    jac = numerical_jacobian(f, t_new, y, fy)
    evals += n
    m = [[(1.0 if i == j else 0.0) - coeff * jac[i][j] for j in range(n)] for i in range(n)]

    for _ in range(_NEWTON_MAX_ITER):
        g = [y[i] - const[i] - coeff * fy[i] for i in range(n)]
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
        if _scaled_norm(dy, y, rtol, atol) < _NEWTON_TOL:
            return y, evals, True
    return y, evals, False


def _be_step(
    f: RHS, t: float, y_n: Sequence[float], h: float, n: int, rtol: float, atol: float
) -> tuple[list[float], int, bool]:
    """One backward-Euler step: solve Y = y_n + h f(t+h, Y). Returns (Y, evals, ok)."""
    return _newton_solve(f, t + h, list(y_n), h, list(y_n), n, rtol, atol)


def _trbdf2_step(
    f: RHS, t: float, y_n: Sequence[float], h: float, n: int, rtol: float, atol: float
) -> tuple[list[float], int, bool]:
    """One TR-BDF2 step: trapezoid to t + gamma*h, then BDF2 to t + h. (Y, evals, ok)."""
    gamma = _GAMMA
    gh = gamma * h
    f_n = _safe_eval(f, t, y_n)
    evals = 1
    if f_n is None:
        return list(y_n), evals, False

    # Stage 1: trapezoidal rule to t + gamma*h. coeff = gamma*h/2, const = y_n + coeff*f_n.
    coeff1 = 0.5 * gh
    const1 = [y_n[i] + coeff1 * f_n[i] for i in range(n)]
    y_gamma, e1, ok1 = _newton_solve(f, t + gh, const1, coeff1, list(y_n), n, rtol, atol)
    evals += e1
    if not ok1:
        return y_gamma, evals, False

    # Stage 2: BDF2 to t + h. coeff = c*h, const = a*y_gamma - b*y_n.
    a = 1.0 / (gamma * (2.0 - gamma))
    b = (1.0 - gamma) ** 2 / (gamma * (2.0 - gamma))
    c = (1.0 - gamma) / (2.0 - gamma)
    const2 = [a * y_gamma[i] - b * y_n[i] for i in range(n)]
    y_new, e2, ok2 = _newton_solve(f, t + h, const2, c * h, list(y_gamma), n, rtol, atol)
    evals += e2
    return y_new, evals, ok2


def _safe_eval(f: RHS, t: float, y: Sequence[float]) -> list[float] | None:
    """Evaluate the RHS, returning None if it overflows or is non-finite."""
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
