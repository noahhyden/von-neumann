"""End-to-end integration test: the whole vn_core.uq toolkit on a REAL finding."""

from __future__ import annotations

import math

import pytest

from launch_economics.distributions import LAUNCH_COST_STARSHIP_DIST
from launch_economics.economics import ReplicationLaunchComparison
from vn_core.uq import (
    Uniform,
    monte_carlo,
    sobol_total_order,
    uq_and_gsa,
    verify_finding,
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
    """Regression guard for the first-order centering fix, on a REAL low-CoV finding: cost dominates, both indices stay in range, first <= total, CI brackets."""
    s = sobol_total_order(_INPUTS, _finding, n=4000, seed=3, bootstrap=150)
    assert s.total_order["cost_per_kg"] > s.total_order["closure"] > 0.0
    for nm in _INPUTS:
        assert -0.02 <= s.first_order[nm] <= s.total_order[nm] + 0.03
        lo, hi = s.total_order_ci[nm]
        assert lo <= s.total_order[nm] <= hi


def test_verify_finding_agrees_on_the_loguniform_apce_path():
    """cost_per_kg is LogUniform (arbitrary PCE), closure Uniform (Legendre); all three means hit the closed form."""
    r = verify_finding(_INPUTS, _finding, seed=4, pce_degree=4)
    assert r.agree and r.pce_trustworthy and r.sobol_rank_agrees
    assert r.pce_mean == pytest.approx(_MEAN, rel=1e-3)
    assert r.sobol_pce[0][0] == "cost_per_kg"
    assert abs(r.qmc_mean - _MEAN) / _MEAN < 0.02
