"""`solve` - the one entry point callers use to integrate an ODE.

Picks an integrator by name and wraps its output in an ``ODEResult``. The RHS
convention (`f(t, y) -> dy/dt`) and the (rtol, atol, t_eval) knobs mirror
scipy.solve_ivp on purpose: scipy stays a drop-in oracle in the tests, and the
existing hand-rolled Euler sites migrate without callers learning a new shape.

Methods:
- ``"rk45"``   - Dormand-Prince, explicit, adaptive. Default; non-stiff workhorse.
- ``"bdf1"``   - backward Euler, implicit, L-stable, order 1. For stiff systems.
- ``"trbdf2"`` - TR-BDF2, implicit, L-stable, order 2. The accurate stiff choice.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from vn_core.ode.common import RHS, ODEResult
from vn_core.ode.implicit import integrate_bdf1, integrate_trbdf2
from vn_core.ode.rk45 import integrate_rk45

_INTEGRATORS = {
    "rk45": integrate_rk45,
    "bdf1": integrate_bdf1,
    "trbdf2": integrate_trbdf2,
}


def solve(
    f: RHS,
    y0: Sequence[float],
    t_span: tuple[float, float],
    *,
    method: str = "rk45",
    rtol: float = 1e-6,
    atol: float = 1e-9,
    max_step: float | None = None,
    first_step: float | None = None,
    t_eval: Sequence[float] | None = None,
) -> ODEResult:
    """Integrate dy/dt = f(t, y) from t_span[0] to t_span[1] starting at y0.

    ``y0`` is the initial state vector (length 1 for a scalar ODE). ``method`` is
    "rk45" (default, explicit adaptive), "bdf1" (implicit, L-stable, order 1, for
    stiff systems), or "trbdf2" (implicit, L-stable, order 2 - the accurate stiff
    choice, far fewer steps than bdf1). ``rtol``/``atol`` set the per-step accuracy;
    the step size adapts to meet them, so there is no dt to guess. If ``t_eval`` is
    given, the result is sampled exactly at those times; otherwise at every accepted
    step.

    Raises ValueError on bad inputs. On a non-finite RHS value the returned
    ``ODEResult.success`` is False with an explanatory message rather than a
    silent NaN trajectory - a bad integration is a finding, not a number to trust.
    """
    if method not in _INTEGRATORS:
        raise ValueError(f"unknown method {method!r}; choose from {sorted(_INTEGRATORS)}")
    t0, t1 = t_span
    if not math.isfinite(t0) or not math.isfinite(t1):
        raise ValueError("t_span endpoints must be finite")
    if t1 < t0:
        raise ValueError("t_span must be increasing (t1 >= t0); backward integration is out of scope for Phase 1")
    if rtol <= 0 or atol <= 0:
        raise ValueError("rtol and atol must be positive")
    y0 = list(y0)
    if len(y0) == 0:
        raise ValueError("y0 must have at least one component")
    if any(not math.isfinite(v) for v in y0):
        raise ValueError("y0 must be finite")

    resolved_max_step = max_step if max_step is not None else (t1 - t0 if t1 > t0 else 1.0)
    if resolved_max_step <= 0:
        raise ValueError("max_step must be positive")

    # Degenerate zero-length span: nothing to integrate, echo the initial state.
    if t1 == t0:
        return ODEResult(
            t=(t0,),
            y=(tuple(y0),),
            method=method,
            success=True,
            n_steps=0,
            n_accepted=0,
            n_rejected=0,
            n_f_evals=0,
            message="empty span (t0 == t1); returned initial state",
        )

    integrator = _INTEGRATORS[method]
    try:
        ts, ys, accepted, rejected, f_evals, steps = integrator(
            f,
            t0,
            t1,
            y0,
            rtol=rtol,
            atol=atol,
            max_step=resolved_max_step,
            first_step=first_step,
            t_eval=t_eval,
        )
    except ValueError:
        raise

    reached = ts[-1] if ts else t0
    success = bool(ys) and abs(reached - t1) <= 1e-9 * max(1.0, abs(t1)) and all(
        math.isfinite(v) for v in ys[-1]
    )
    if success:
        message = "integration successful"
    elif not all(math.isfinite(v) for v in ys[-1]):  # pragma: no cover - defensive: the
        # integrators never *record* a non-finite state (a step producing inf/nan is
        # rejected, or the RHS guard shrinks it), so a stall shows up as the branch
        # below; this message is kept as a floor against a future integrator.
        message = "integration produced a non-finite state (RHS blew up); result is not trustworthy"
    else:
        message = f"integration stalled at t={reached!r} before t1={t1!r} (step size collapsed)"

    return ODEResult(
        t=tuple(ts),
        y=tuple(ys),
        method=method,
        success=success,
        n_steps=steps,
        n_accepted=accepted,
        n_rejected=rejected,
        n_f_evals=f_evals,
        message=message,
    )
