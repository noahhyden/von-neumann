"""Shared pieces for the ODE integrators: result type, error norm, step sizing."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

# The right-hand side of dy/dt = f(t, y), with the same signature as scipy.solve_ivp so scipy is a drop-in oracle in the tests.
RHS = Callable[[float, Sequence[float]], Sequence[float]]


@dataclass(frozen=True)
class ODEResult:
    """The integrated trajectory plus honest work counters."""

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
    """Scaled RMS norm of a local error estimate (the standard adaptive metric)."""
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
    """Automatic first-step size (Hairer/Wanner II.4), returns (h, extra_f_evals)."""
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
    """Validate and order requested output times inside (t0, t1]. Empty if None."""
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
