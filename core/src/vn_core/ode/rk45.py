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

Requested output times (``t_eval``) are served by the Dormand-Prince quartic **dense
output** (Hairer/Wanner II.6): the integrator takes its normal adaptive steps and
interpolates the solution at each requested time from the stages it already computed,
so ``t_eval`` costs no extra steps and - crucially - the accepted-step sequence is
*identical* to a run with ``t_eval=None``. (Earlier this module capped steps to land
on each target, which changed the step sequence and cost extra steps.)

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

# Step controller constants. Gustafsson PI controller (Hairer/Wanner II.4), the same
# form and defaults as Hairer's reference DOPRI5. The step factor is
#   factor = clamp( SAFETY * err**(-alpha) * err_prev**beta,  MIN_FACTOR, MAX_FACTOR )
# with the beta (integral) term damping the oscillation a pure err**(-1/5) controller
# shows on problems with abruptly changing scales - fewer rejected steps, same accuracy.
_SAFETY = 0.9
_MIN_FACTOR = 0.2
_MAX_FACTOR = 10.0
_PI_BETA = 0.04  # integral-term gain (Hairer DOPRI5 default)
_PI_ALPHA = 1.0 / 5.0 - 0.75 * _PI_BETA  # = 0.17; current-error exponent, 1/(q+1) - 0.75*beta

# Dense-output interpolation matrix P (7 stages x 4 powers of theta), exact rationals.
# The quartic interpolant on an accepted step [t, t+h] is
#   y(t + theta*h) = y + h * sum_s K[s] * (sum_j P[s][j] * theta**(j+1)),  theta in [0,1],
# where K = [k1..k7] are the step's stage derivatives. These are the standard
# Dormand-Prince dense-output coefficients (Hairer/Wanner II.6); identical to the P
# matrix in scipy.integrate RK45 (BSD), against which the interpolant is validated
# bit-for-bit in the tests. theta=0 gives y, theta=1 gives the step's y_new.
_P: tuple[tuple[float, ...], ...] = (
    (1.0, -8048581381 / 2820520608, 8663915743 / 2820520608, -12715105075 / 11282082432),
    (0.0, 0.0, 0.0, 0.0),
    (0.0, 131558114200 / 32700410799, -68118460800 / 10900136933, 87487479700 / 32700410799),
    (0.0, -1754552775 / 470086768, 14199869525 / 1410260304, -10690763975 / 1880347072),
    (0.0, 127303824393 / 49829197408, -318862633887 / 49829197408, 701980252875 / 199316789632),
    (0.0, -282668133 / 205662961, 2019193451 / 616988883, -1453857185 / 822651844),
    (0.0, 40617522 / 29380423, -110615467 / 29380423, 69997945 / 29380423),
)


def _dopri_interpolate(
    y: Sequence[float], h: float, stages: Sequence[Sequence[float]], theta: float, n: int
) -> tuple[float, ...]:
    """Dense-output value at ``t + theta*h`` from the step's start ``y`` and stages.

    ``stages`` is [k1..k7]; ``theta`` in [0, 1]. theta=0 returns ``y`` and theta=1
    returns the step's 5th-order endpoint (verified against the direct step in tests).
    """
    powers = (theta, theta * theta, theta * theta * theta, theta * theta * theta * theta)
    out = list(y)
    for s in range(7):
        ws = _P[s][0] * powers[0] + _P[s][1] * powers[1] + _P[s][2] * powers[2] + _P[s][3] * powers[3]
        if ws == 0.0:  # stage 2 (index 1) has an all-zero P row - skip it.
            continue
        ks = stages[s]
        for i in range(n):
            out[i] += h * ks[i] * ws
    return tuple(out)


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

    If ``t_eval`` is given, the result is the solution at exactly those times, obtained
    by the quartic dense-output interpolant on each accepted step (no extra steps, and
    the step sequence is identical to ``t_eval=None``). Otherwise every accepted step
    is recorded.
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
    # Previous accepted step's error, the PI controller's "integral" memory. Hairer's
    # initial value; floored at 1e-4 so an exactly-zero error cannot zero the term.
    err_prev = 1e-4

    while t < t1:
        steps += 1
        if steps > max_steps:
            return ts, ys, accepted, rejected, f_evals, steps
        remaining = t1 - t
        # Cap only to the span end and max_step - NOT to output times, so the step
        # sequence is identical whether or not t_eval was requested.
        h = clamp_step(h, max_step, min_step, remaining)

        y_new, err_vec, stages, evals = _dopri_step(f, t, y, f0, h, n)
        f_evals += evals
        err = rms_error_norm(err_vec, y, y_new, rtol, atol)

        if err <= 1.0:
            # Accept.
            t_prev = t
            t = t + h
            accepted += 1
            if record_all:
                ts.append(t)
                ys.append(tuple(y_new))
            else:
                # Emit every requested time that falls in (t_prev, t_new] via the dense
                # interpolant - no extra model evaluations, exact step sequence. Because
                # the step covers exactly [t_prev, t_prev + h] = [t_prev, t], a target
                # with t_prev < target <= t gives theta = (target - t_prev)/h in (0, 1]
                # by construction, so no clamping is needed. The loop only exits once a
                # step reaches t >= t1, so the final requested time (<= t1) is always
                # covered by some step.
                while ti < len(targets) and targets[ti] <= t:
                    theta = (targets[ti] - t_prev) / h
                    ts.append(targets[ti])
                    ys.append(_dopri_interpolate(y, h, stages, theta, n))
                    ti += 1
            y = y_new
            f0 = stages[6]  # FSAL: k7 is the next step's first stage.
            # PI controller: err**(-alpha) is the proportional term, err_prev**beta the
            # integral term. err == 0 (an exactly-integrated step) means grow maximally.
            if err == 0.0:
                factor = _MAX_FACTOR
            else:
                factor = _SAFETY * err ** (-_PI_ALPHA) * err_prev**_PI_BETA
                factor = min(_MAX_FACTOR, max(_MIN_FACTOR, factor))
            err_prev = max(err, 1e-4)  # remember this step's error for the next PI update
            h = h * factor
        else:
            # Reject: shrink and retry from the same point. Pure proportional term (the
            # PI integral memory is not updated on a reject, per Hairer); err > 1 here so
            # the factor is < 1 (shrink), floored at _MIN_FACTOR.
            rejected += 1
            factor = max(_MIN_FACTOR, _SAFETY * err ** (-_PI_ALPHA))
            h = h * factor

    # Safety net: guarantee the final time is present under record_all. In practice
    # the last accepted step lands within ~1 ulp of t1 (h is capped to the remaining
    # span, and the only overshoot is the min_step floor, itself ~10 ulp), so the
    # >min_step guard is not taken - it is a defensive floor against a future change.
    if record_all and abs(ts[-1] - t1) > min_step:  # pragma: no cover
        ts.append(t1)
        ys.append(tuple(y))
    return ts, ys, accepted, rejected, f_evals, steps


def _dopri_step(
    f: RHS, t: float, y: Sequence[float], k1: Sequence[float], h: float, n: int
) -> tuple[list[float], list[float], list[list[float]], int]:
    """One DOPRI5 step from (t, y) with k1 = f(t, y) already known (FSAL/first).

    Returns (y5, error_vector, stages, f_evals). y5 is the 5th-order solution; the
    error vector is h * sum(e_i k_i), the embedded 4(5) estimate; ``stages`` is the
    full [k1..k7] list - k7 = f(t+h, y5) is the FSAL stage reused as the next step's
    k1, and all seven are needed for the dense-output interpolant.
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
    k7 = list(f(t + h, y_new))
    err = [
        h * (E1 * k1[i] + E3 * k3[i] + E4 * k4[i] + E5 * k5[i] + E6 * k6[i] + E7 * k7[i])
        for i in range(n)
    ]
    stages = [list(k1), list(k2), list(k3), list(k4), list(k5), list(k6), k7]
    return y_new, err, stages, 6
