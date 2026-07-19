"""End-to-end integration test: the whole vn_core.uq toolkit on a REAL finding.

Every other UQ test exercises one surface on a synthetic function. This one drives
*all* of them - monte_carlo, uq_and_gsa, sobol (first+total+CI), pce_fit
(quadrature / regression / arbitrary-PCE), qmc_mean, pce_control_variate - on a
real launch-economics finding and checks the independent methods agree with each
other and with the closed-form mean.

Finding: cost_savings_usd, the launch cost saved by replicating a factory in place
instead of launching the finished mass, over two real-shaped inputs:
  - launch cost per kg ~ LogUniform (LAUNCH_COST_STARSHIP_DIST) -> arbitrary PCE
  - mass closure ratio ~ Uniform                                -> Legendre PCE

It is the guard that unit tests miss: this workload (a large mean with a modest
spread) is exactly what exposed the un-centered first-order Sobol bug that every
synthetic-function test passed straight through.
"""

from __future__ import annotations

import math

import pytest

from launch_economics.distributions import LAUNCH_COST_STARSHIP_DIST
from launch_economics.economics import ReplicationLaunchComparison
from vn_core.uq import (
    Uniform,
    monte_carlo,
    pce_control_variate,
    pce_fit,
    qmc_mean,
    sobol_total_order,
    uq_and_gsa,
)

_TARGET, _SEED = 100_000.0, 10_000.0
_BUILT = _TARGET - _SEED
_INPUTS = {"cost_per_kg": LAUNCH_COST_STARSHIP_DIST, "closure": Uniform(0.5, 0.95)}


def _finding(s):
    vitamins = (1.0 - s["closure"]) * _BUILT
    return ReplicationLaunchComparison(
        target_installed_mass_kg=_TARGET,
        seed_mass_kg=_SEED,
        vitamin_mass_total_kg=vitamins,
        cost_per_kg_usd=s["cost_per_kg"],
    ).cost_savings_usd  # = BUILT * closure * cost_per_kg (bilinear, analytic)


# Closed-form mean: BUILT * E[closure] * E[cost], E[LogUniform] = (b-a)/ln(b/a).
_E_COST = (1000.0 - 100.0) / math.log(1000.0 / 100.0)
_MEAN = _BUILT * (0.5 * (0.5 + 0.95)) * _E_COST


# --- each surface recovers the truth ------------------------------------------


def test_monte_carlo_recovers_the_closed_form_mean():
    mc = monte_carlo(_INPUTS, _finding, n=8000, seed=1)
    assert abs(mc.mean - _MEAN) < 4 * mc.stderr_of_mean


def test_uq_and_gsa_shares_samples_and_agrees():
    a = uq_and_gsa(_INPUTS, _finding, n=4000, seed=2)
    assert a.uq.mean == a.gsa.mean  # one Saltelli design, two readouts
    assert abs(a.uq.mean - _MEAN) < 4 * a.uq.stderr_of_mean


def test_sobol_indices_are_sane_and_rank_the_driver():
    """Regression guard for the first-order centering fix, on a REAL low-CoV
    finding: cost dominates, both indices stay in range, first <= total, CI brackets."""
    s = sobol_total_order(_INPUTS, _finding, n=4000, seed=3, bootstrap=150)
    assert s.total_order["cost_per_kg"] > s.total_order["closure"] > 0.0
    for nm in _INPUTS:
        assert -0.02 <= s.first_order[nm] <= s.total_order[nm] + 0.03
        lo, hi = s.total_order_ci[nm]
        assert lo <= s.total_order[nm] <= hi


def test_pce_handles_the_loguniform_via_apce():
    """cost_per_kg is LogUniform -> the arbitrary-PCE path; closure is Uniform ->
    Legendre. Both fit methods must be trustworthy and hit the closed form."""
    pq = pce_fit(_INPUTS, _finding, degree=4, method="quadrature")
    pr = pce_fit(_INPUTS, _finding, degree=4, method="regression", seed=4)
    assert pq.is_trustworthy() and pr.is_trustworthy()
    assert pq.mean == pytest.approx(_MEAN, rel=1e-3)
    assert pr.mean == pytest.approx(pq.mean, rel=5e-3)
    assert pq.total_order["cost_per_kg"] > pq.total_order["closure"]


def test_qmc_and_control_variate_are_tight_and_correct():
    q = qmc_mean(_INPUTS, _finding, n=256, seed=5, replicates=24)
    cv = pce_control_variate(_INPUTS, _finding, degree=4, n=2000, seed=6)
    # RQMC agrees with the truth within a few of its own standard errors (a 90% CI
    # would legitimately miss ~10% of the time, so assert the wider band instead).
    assert abs(q.mean - _MEAN) < 5 * q.stderr
    assert q.stderr < 0.01 * _MEAN  # and it is tight
    assert cv.mean == pytest.approx(_MEAN, rel=1e-3)
    assert cv.variance_reduction > 1.0
    assert cv.stderr < 0.01 * _MEAN  # control variate is tight


# --- and they all agree with each other ---------------------------------------


def test_all_six_methods_agree_on_the_mean():
    mc = monte_carlo(_INPUTS, _finding, n=12000, seed=1).mean
    uq = uq_and_gsa(_INPUTS, _finding, n=6000, seed=2).uq.mean
    pq = pce_fit(_INPUTS, _finding, degree=4).mean
    pr = pce_fit(_INPUTS, _finding, degree=4, method="regression", seed=4).mean
    qm = qmc_mean(_INPUTS, _finding, n=256, seed=5, replicates=16).mean
    cv = pce_control_variate(_INPUTS, _finding, degree=4, n=2000, seed=6).mean
    vals = [mc, uq, pq, pr, qm, cv]
    # Deterministic surfaces (PCE, CV) are exact for this bilinear finding; the
    # MC-based ones carry ~1% sampling noise at these N. All within 2% of truth.
    for v in vals:
        assert abs(v - _MEAN) / _MEAN < 0.02
    assert (max(vals) - min(vals)) / _MEAN < 0.03
