"""Shared pieces for the ODE integrators: result type, error norm, step sizing.

These live apart from `solve` so both the explicit (rk45) and implicit integrators
can use them without importing the dispatcher (which imports them) - a plain
seam, no cycle.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

# The right-hand side of dy/dt = f(t, y). Same convention as scipy.solve_ivp:
# f takes the scalar time and the state vector, returns dy/dt as a sequence.
# Keeping the signature identical is deliberate - it makes scipy a drop-in
# oracle in the tests and eases migration of existing call sites.
RHS = Callable[[float, Sequence[float]], Sequence[float]]


@dataclass(frozen=True)
class ODEResult:
    """The integrated trajectory plus honest work counters.

    ``t[i]`` is the time of sample ``i`` and ``y[i]`` its state vector, so
    ``y[i][k]`` is component ``k`` at ``t[i]``. The counters are not decoration:
    they are the raw material for issue #38's Phase 2 (measure before Rust), so a
    caller can report f-evals per solve without re-instrumenting.
    """

    t: tuple[float, ...]
    y: tuple[tuple[float, ...], ...]
    method: str
    success: bool
    n_steps: int
    n_accepted: int
    n_rejected: int
    n_f_evals: int
    message: str

    @property
    def y_final(self) -> tuple[float, ...]:
        """The state vector at the final time - the common single-value readout."""
        return self.y[-1]


def rms_error_norm(
    err: Sequence[float], y0: Sequence[float], y1: Sequence[float], rtol: float, atol: float
) -> float:
    """Scaled RMS norm of a local error estimate (the standard adaptive metric).

    Each component is scaled by `atol + rtol * max(|y0|, |y1|)`, then combined as
    a root-mean-square. A returned value <= 1 means the step met tolerance. This
    is the norm used by Hairer/Wanner and by scipy, so our step acceptance tracks
    a well-understood reference rather than an ad-hoc rule.
    """
    n = len(err)
    total = 0.0
    for i in range(n):
        scale = atol + rtol * max(abs(y0[i]), abs(y1[i]))
        # scale is always > 0 while atol > 0, so no divide-by-zero.
        ratio = err[i] / scale
        total += ratio * ratio
    return math.sqrt(total / n)


def clamp_step(h: float, max_step: float, min_step: float, remaining: float) -> float:
    """Clamp a proposed step to [min_step, max_step] and to what remains of the span."""
    h = min(h, max_step, remaining)
    return max(h, min_step)


def select_initial_step(
    f: RHS,
    t0: float,
    y0: Sequence[float],
    f0: Sequence[float],
    order: int,
    rtol: float,
    atol: float,
    max_step: float,
) -> tuple[float, int]:
    """Automatic first-step size (Hairer/Wanner II.4), returns (h, extra_f_evals).

    Picks h so the first step is neither wastefully tiny nor an instant reject:
    it balances the scale of y against the scale of its derivative. Falls back to
    a small fraction of the span if the derivative is ~0. Returns the number of
    extra RHS evaluations it cost (one), so the caller keeps an honest count.
    """
    scale = [atol + abs(y0[i]) * rtol for i in range(len(y0))]
    d0 = _weighted_rms(y0, scale)
    d1 = _weighted_rms(f0, scale)
    if d0 < 1e-5 or d1 < 1e-5:
        h0 = 1e-6
    else:
        h0 = 0.01 * (d0 / d1)
    h0 = min(h0, max_step)
    # One explicit Euler probe to estimate the second derivative's scale.
    y1 = [y0[i] + h0 * f0[i] for i in range(len(y0))]
    f1 = f(t0 + h0, y1)
    d2 = _weighted_rms([f1[i] - f0[i] for i in range(len(f0))], scale) / h0
    if max(d1, d2) <= 1e-15:
        h1 = max(1e-6, h0 * 1e-3)
    else:
        h1 = (0.01 / max(d1, d2)) ** (1.0 / (order + 1))
    return min(100.0 * h0, h1, max_step), 1


def _weighted_rms(v: Sequence[float], scale: Sequence[float]) -> float:
    n = len(v)
    total = 0.0
    for i in range(n):
        r = v[i] / scale[i]
        total += r * r
    return math.sqrt(total / n)


def output_targets(
    t0: float, t1: float, t_eval: Sequence[float] | None
) -> list[float]:
    """Validate and order requested output times inside (t0, t1]. Empty if None.

    Shared by both integrators: when the caller asks for specific times, each
    integrator caps its steps to land on them exactly (see the integrators for
    the trade this makes vs. a continuous interpolant).
    """
    if t_eval is None:
        return []
    targets = sorted(t_eval)
    for tv in targets:
        if tv < t0 or tv > t1:
            raise ValueError(f"t_eval entry {tv!r} is outside the span [{t0}, {t1}]")
    out: list[float] = []
    for tv in targets:
        if tv <= t0:
            continue
        if not out or tv > out[-1]:
            out.append(tv)
    return out
