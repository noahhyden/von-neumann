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

Integration is delegated to the shared adaptive solver `vn_core.ode` (issue #38):
the old hand-rolled forward-Euler loop picked its timestep by feel ("dt small
enough"), an unjustified number by CLAUDE.md §1. The adaptive RK45 solver takes a
tolerance instead, so the reported approach-to-equilibrium is accurate by
construction rather than by a lucky dt.
"""

from __future__ import annotations

from vn_core.ode import solve


def aurora_equilibrium(t_launch: float, t_settle: float) -> float:
    """Equilibrium settled fraction X_eq = 1 - T_l/T_s, floored at 0.

    T_l = launch/spread time, T_s = settlement lifetime. If T_l >= T_s the settlement
    cannot sustain itself and X_eq = 0 (no plateau).
    """
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
    """Integrate the Aurora ODE from x0 to time t_end; returns the final X.

    Uses the shared adaptive solver `vn_core.ode` (RK45) - the step size is chosen
    to meet (rtol, atol), so there is no dt to guess. Converges to
    `aurora_equilibrium(t_launch, t_settle)` when T_l < T_s, and decays to 0 when
    T_l >= T_s. ``t_end`` must be long enough to reach the plateau you want to
    report (the approach is exponential with time constant ~min(T_l, T_s)).
    """
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
