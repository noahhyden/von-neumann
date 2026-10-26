"""Analytical companion for the Aurora ODE (issue #50, Phase 2)."""

import pytest

from reliability.aurora import aurora_equilibrium, aurora_integrate


# ---------- Approach time constant matches the linearization ----------

def test_approach_time_constant():
    """Start close to X_eq so the linearization applies; verify 1/e decay at t = tau."""
    import math

    T_l, T_s = 1000.0, 5000.0
    X_eq = aurora_equilibrium(T_l, T_s)
    tau = 1.0 / (1.0 / T_l - 1.0 / T_s)  # T_l T_s / (T_s - T_l)
    # Perturbation small enough that O(delta^2) is negligible over tau.
    x0 = X_eq - 0.001
    gap0 = X_eq - x0
    x_tau = aurora_integrate(x0, T_l, T_s, t_end=tau)
    gap_tau = X_eq - x_tau
    # Linearization predicts gap_tau = gap0 / e; allow 5% tolerance for the O(delta^2) correction and ODE tolerance.
    assert gap_tau == pytest.approx(gap0 / math.e, rel=0.05)


# ---------- Time symmetry: X_eq depends only on T_l/T_s ----------

@pytest.mark.parametrize("scale", [0.01, 1.0, 100.0, 1e6])
def test_equilibrium_depends_only_on_ratio(scale):
    T_l, T_s = 1000.0, 5000.0
    x_ref = aurora_equilibrium(T_l, T_s)
    x_scaled = aurora_equilibrium(T_l * scale, T_s * scale)
    assert x_scaled == pytest.approx(x_ref, rel=1e-12)


# ---------- Approach time also scales linearly with T_l, T_s ----------

def test_approach_time_scales_linearly():
    T_l, T_s = 1000.0, 5000.0
    tau_ref = 1.0 / (1.0 / T_l - 1.0 / T_s)
    scale = 3.0
    tau_scaled = 1.0 / (1.0 / (T_l * scale) - 1.0 / (T_s * scale))
    assert tau_scaled == pytest.approx(scale * tau_ref, rel=1e-12)


# ---------- Collapse at T_l >= T_s decays at rate 1/T_l - 1/T_s ----------

def test_collapse_rate_when_launch_exceeds_lifetime():
    """T_l > T_s: X = 0 is stable; the initial X decays exponentially."""
    T_l, T_s = 5000.0, 1000.0  # collapse regime
    tau_collapse = 1.0 / (1.0 / T_s - 1.0 / T_l)  # positive when T_l > T_s
    x0 = 0.1
    # After 5 collapse time constants, X should be << x0.
    x_5tau = aurora_integrate(x0, T_l, T_s, t_end=5.0 * tau_collapse)
    assert x_5tau < 0.01 * x0
    # And the plateau by definition is 0.
    assert aurora_equilibrium(T_l, T_s) == 0.0


# ---------- Critical case T_l == T_s: X decays but sub-exponentially ----------

def test_critical_case_still_collapses():
    """T_l = T_s: the linear coefficient at X=0 is zero; decay is sub-exponential."""
    T = 1000.0
    x0 = 0.5
    x_final = aurora_integrate(x0, T, T, t_end=100.0 * T)
    assert x_final < 0.05  # substantial decay but not exponentially fast
    assert aurora_equilibrium(T, T) == 0.0
