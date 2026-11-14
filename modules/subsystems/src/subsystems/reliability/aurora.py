"""The Aurora steady-state: how much of a region stays settled at equilibrium."""

from __future__ import annotations

from vn_core.ode import solve


def aurora_equilibrium(t_launch: float, t_settle: float) -> float:
    """Equilibrium settled fraction X_eq = 1 - T_l/T_s, floored at 0."""
    if t_launch <= 0 or t_settle <= 0:
        raise ValueError("t_launch and t_settle must be positive")
    x_eq = 1.0 - t_launch / t_settle
    return x_eq if x_eq > 0.0 else 0.0


def aurora_rate(x: float, t_launch: float, t_settle: float) -> float:
    """The Aurora RHS dX/dt = (1/T_l) X (1-X) - (1/T_s) X. Deterministic, pure."""
    if t_launch <= 0 or t_settle <= 0:
        raise ValueError("t_launch and t_settle must be positive")
    return (1.0 / t_launch) * x * (1.0 - x) - (1.0 / t_settle) * x


def aurora_integrate(
    x0: float,
    t_launch: float,
    t_settle: float,
    *,
    t_end: float,
    rtol: float = 1e-8,
    atol: float = 1e-11,
) -> float:
    """Integrate the Aurora ODE from x0 to time t_end; returns the final X."""
    if not 0.0 <= x0 <= 1.0:
        raise ValueError("x0 must be in [0, 1]")
    if t_end < 0:
        raise ValueError("t_end must be non-negative")
    if t_launch <= 0 or t_settle <= 0:
        raise ValueError("t_launch and t_settle must be positive")
    result = solve(
        lambda t, y: [aurora_rate(y[0], t_launch, t_settle)],
        [x0],
        (0.0, t_end),
        rtol=rtol,
        atol=atol,
    )
    if not result.success:
        raise RuntimeError(f"aurora integration failed: {result.message}")
    return result.y_final[0]
