"""The Aurora steady-state: how much of a region stays settled at equilibrium.

A self-replicating fleet does not expand forever unopposed - settled sites also die off.
Carroll-Nellenback et al. (2019), "The Fermi Paradox and the Aurora Effect", give the
equilibrium settled fraction as a balance between spread and death:

    dX/dt = (1/T_l) X (1 - X) - (1/T_s) X      =>      X_eq = 1 - T_l / T_s     (their Eq. 32)

The symbols are counterintuitive and were verified against the paper (see REFERENCES.md):
**T_l is the launch / spread time** (how fast settlement spreads) and **T_s is the
settlement lifetime** (how long a settled site persists). A non-zero plateau needs
`T_l < T_s`: settlement must spread faster than sites die, or the fraction collapses to
zero. This is what turns the fleet models' unbounded growth into a real steady state.

Deterministic ODE - no RNG (that is mortality.py). Pure functions.
"""

from __future__ import annotations


def aurora_equilibrium(t_launch: float, t_settle: float) -> float:
    """Equilibrium settled fraction X_eq = 1 - T_l/T_s, floored at 0.

    T_l = launch/spread time, T_s = settlement lifetime. If T_l >= T_s the settlement
    cannot sustain itself and X_eq = 0 (no plateau).
    """
    if t_launch <= 0 or t_settle <= 0:
        raise ValueError("t_launch and t_settle must be positive")
    x_eq = 1.0 - t_launch / t_settle
    return x_eq if x_eq > 0.0 else 0.0


def aurora_step(x: float, t_launch: float, t_settle: float, dt: float) -> float:
    """One explicit-Euler step of dX/dt = (1/T_l) X (1-X) - (1/T_s) X. Deterministic."""
    if t_launch <= 0 or t_settle <= 0:
        raise ValueError("t_launch and t_settle must be positive")
    if dt <= 0:
        raise ValueError("dt must be positive")
    dxdt = (1.0 / t_launch) * x * (1.0 - x) - (1.0 / t_settle) * x
    return x + dxdt * dt


def aurora_integrate(
    x0: float, t_launch: float, t_settle: float, *, dt: float, steps: int
) -> float:
    """Integrate the Aurora ODE from x0 for a number of steps; returns the final X.

    Converges to `aurora_equilibrium(t_launch, t_settle)` when T_l < T_s.
    """
    if not 0.0 <= x0 <= 1.0:
        raise ValueError("x0 must be in [0, 1]")
    if steps < 0:
        raise ValueError("steps must be non-negative")
    x = x0
    for _ in range(steps):
        x = aurora_step(x, t_launch, t_settle, dt)
    return x
