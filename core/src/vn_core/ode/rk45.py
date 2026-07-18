"""Dormand-Prince RK45 (DOPRI5): explicit, adaptive, the non-stiff workhorse.

A 5th-order Runge-Kutta step with an embedded 4th-order solution. The difference
between the two orders is a local error estimate that drives the step size, so the
caller states a tolerance (rtol/atol) instead of guessing dt - which is the whole
point of issue #38 (the hand-rolled Euler sites picked dt "small enough for the
regimes we report", an unjustified number by CLAUDE.md §1).

The tableau is the standard Dormand & Prince (1980) FSAL pair; coefficients are
written as exact rationals so anyone can check them against the reference. FSAL
("first same as last") means the last stage of an accepted step is the first
stage of the next, saving one RHS evaluation per step.

Pure deterministic fold (§7): no RNG, fixed operation order, so identical inputs
give byte-identical output on any machine.
"""

from __future__ import annotations

from collections.abc import Sequence

from vn_core.ode.common import (
    RHS,
    clamp_step,
    output_targets,
    rms_error_norm,
    select_initial_step,
)

# --- Dormand-Prince (DOPRI5) Butcher tableau, exact rationals ------------------
C2, C3, C4, C5 = 1 / 5, 3 / 10, 4 / 5, 8 / 9
A21 = 1 / 5
A31, A32 = 3 / 40, 9 / 40
A41, A42, A43 = 44 / 45, -56 / 15, 32 / 9
A51, A52, A53, A54 = 19372 / 6561, -25360 / 2187, 64448 / 6561, -212 / 729
A61, A62, A63, A64, A65 = 9017 / 3168, -355 / 33, 46732 / 5247, 49 / 176, -5103 / 18656
# 5th-order weights (also the 7th-stage a-row, hence FSAL).
B1, B3, B4, B5, B6 = 35 / 384, 500 / 1113, 125 / 192, -2187 / 6784, 11 / 84
# Error weights e = b(5th) - bhat(4th); only the nonzero entries.
E1 = 35 / 384 - 5179 / 57600
E3 = 500 / 1113 - 7571 / 16695
E4 = 125 / 192 - 393 / 640
E5 = -2187 / 6784 - (-92097 / 339200)
E6 = 11 / 84 - 187 / 2100
E7 = -1 / 40

# Step controller constants (Hairer/Wanner defaults, matching scipy's RK45).
_SAFETY = 0.9
_MIN_FACTOR = 0.2
_MAX_FACTOR = 10.0
_ERROR_EXPONENT = -1.0 / 5.0  # -1/(estimator_order+1), estimator order 4


def integrate_rk45(
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
    """Integrate f from t0 to t1. Returns (ts, ys, accepted, rejected, f_evals, steps).

    If ``t_eval`` is given, steps are capped so the integrator lands exactly on
    each requested time and only those are recorded; otherwise every accepted
    step is recorded. Capping keeps error control on every (sub)step, so accuracy
    is preserved - the only cost is more steps when t_eval is dense, an honest
    Phase-1 trade vs. building a continuous interpolant.
    """
    n = len(y0)
    y = list(y0)
    t = t0
    f0 = list(f(t, y))
    f_evals = 1

    ts: list[float] = [t0]
    ys: list[tuple[float, ...]] = [tuple(y)]

    # Requested output times strictly inside (t0, t1], consumed in order.
    targets = output_targets(t0, t1, t_eval)
    record_all = t_eval is None
    ti = 0

    min_step = 10 * abs(t1 - t0) * 2.220446049250313e-16  # ~10 ulp of the span
    if first_step is not None:
        h = min(first_step, max_step)
    else:
        h, extra = select_initial_step(f, t0, y, f0, 5, rtol, atol, max_step)
        f_evals += extra

    accepted = 0
    rejected = 0
    steps = 0
    max_steps = 10_000_000  # a real cap so a bad RHS cannot spin forever

    while t < t1:
        steps += 1
        if steps > max_steps:
            return ts, ys, accepted, rejected, f_evals, steps
        remaining = t1 - t
        # Cap the step so it does not overshoot the next requested output time.
        cap = remaining
        if not record_all and ti < len(targets):
            cap = min(cap, targets[ti] - t)
        h = clamp_step(h, max_step, min_step, cap)

        y_new, err_vec, k7, evals = _dopri_step(f, t, y, f0, h, n)
        f_evals += evals
        err = rms_error_norm(err_vec, y, y_new, rtol, atol)

        if err <= 1.0:
            # Accept.
            t = t + h
            y = y_new
            f0 = k7  # FSAL: last stage derivative is next step's first stage.
            accepted += 1
            landed_on_target = not record_all and ti < len(targets) and abs(t - targets[ti]) <= min_step
            if record_all:
                ts.append(t)
                ys.append(tuple(y))
            elif landed_on_target:
                ts.append(targets[ti])
                ys.append(tuple(y))
                ti += 1
            # Grow the step for next time (error 0 -> max growth).
            if err == 0.0:
                factor = _MAX_FACTOR
            else:
                factor = min(_MAX_FACTOR, _SAFETY * err**_ERROR_EXPONENT)
            h = h * factor
        else:
            # Reject: shrink and retry from the same point (do not grow).
            rejected += 1
            factor = max(_MIN_FACTOR, _SAFETY * err**_ERROR_EXPONENT)
            h = h * factor

    # Guarantee the final time is present and exact even under record_all.
    if record_all and abs(ts[-1] - t1) > min_step:
        ts.append(t1)
        ys.append(tuple(y))
    return ts, ys, accepted, rejected, f_evals, steps


def _dopri_step(
    f: RHS, t: float, y: Sequence[float], k1: Sequence[float], h: float, n: int
) -> tuple[list[float], list[float], list[float], int]:
    """One DOPRI5 step from (t, y) with k1 = f(t, y) already known (FSAL/first).

    Returns (y5, error_vector, k7, f_evals). y5 is the 5th-order solution; the
    error vector is h * sum(e_i k_i), the embedded 4(5) estimate; k7 = f(t+h, y5)
    is returned for FSAL reuse as the next step's k1.
    """
    y2 = [y[i] + h * (A21 * k1[i]) for i in range(n)]
    k2 = f(t + C2 * h, y2)
    y3 = [y[i] + h * (A31 * k1[i] + A32 * k2[i]) for i in range(n)]
    k3 = f(t + C3 * h, y3)
    y4 = [y[i] + h * (A41 * k1[i] + A42 * k2[i] + A43 * k3[i]) for i in range(n)]
    k4 = f(t + C4 * h, y4)
    y5s = [
        y[i] + h * (A51 * k1[i] + A52 * k2[i] + A53 * k3[i] + A54 * k4[i])
        for i in range(n)
    ]
    k5 = f(t + C5 * h, y5s)
    y6 = [
        y[i] + h * (A61 * k1[i] + A62 * k2[i] + A63 * k3[i] + A64 * k4[i] + A65 * k5[i])
        for i in range(n)
    ]
    k6 = f(t + h, y6)
    # 5th-order solution (b2 = 0), which is also the point where k7 is evaluated.
    y_new = [
        y[i] + h * (B1 * k1[i] + B3 * k3[i] + B4 * k4[i] + B5 * k5[i] + B6 * k6[i])
        for i in range(n)
    ]
    k7 = f(t + h, y_new)
    err = [
        h * (E1 * k1[i] + E3 * k3[i] + E4 * k4[i] + E5 * k5[i] + E6 * k6[i] + E7 * k7[i])
        for i in range(n)
    ]
    return y_new, err, list(k7), 6
