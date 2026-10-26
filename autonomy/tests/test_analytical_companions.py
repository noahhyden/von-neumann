"""Analytical companion for autonomy (issue #50, Phase 2)."""

import math

import pytest

from autonomy.autonomy import affordable_compute_at, autonomy_wall_au


# ---------- (3) matches sqrt(S_1AU / D) ----------

def test_wall_matches_closed_form():
    S = 1e14
    D = 1e12
    expected = math.sqrt(S / D)
    assert autonomy_wall_au(S, D) == pytest.approx(expected, rel=1e-12)


# ---------- Supply exactly meets demand at d = d_wall ----------

def test_supply_meets_demand_at_wall():
    S = 1e14
    D = 1e12
    d_wall = autonomy_wall_au(S, D)
    assert affordable_compute_at(S, d_wall) == pytest.approx(D, rel=1e-9)


# ---------- Absolute magnitude cancels: S and D can be rescaled together ----------

@pytest.mark.parametrize("alpha", [0.001, 0.5, 1.0, 100.0, 1e9])
def test_wall_invariant_under_joint_rescaling(alpha):
    S = 1e14
    D = 1e12
    d_ref = autonomy_wall_au(S, D)
    d_rescaled = autonomy_wall_au(alpha * S, alpha * D)
    assert d_rescaled == pytest.approx(d_ref, rel=1e-9)


# ---------- Doubling demand shrinks the wall by sqrt(2) ----------

def test_wall_scales_as_inverse_sqrt_demand():
    S = 1e14
    D = 1e12
    d0 = autonomy_wall_au(S, D)
    d1 = autonomy_wall_au(S, 2.0 * D)
    assert d1 == pytest.approx(d0 / math.sqrt(2.0), rel=1e-9)


# ---------- Doubling supply extends the wall by sqrt(2) ----------

def test_wall_scales_as_sqrt_supply():
    S = 1e14
    D = 1e12
    d0 = autonomy_wall_au(S, D)
    d1 = autonomy_wall_au(2.0 * S, D)
    assert d1 == pytest.approx(d0 * math.sqrt(2.0), rel=1e-9)


# ---------- Below wall, supply exceeds demand; above, it falls short ----------

def test_supply_exceeds_demand_inside_wall():
    S = 1e14
    D = 1e12
    d_wall = autonomy_wall_au(S, D)
    assert affordable_compute_at(S, d_wall * 0.5) > D


def test_supply_falls_short_outside_wall():
    S = 1e14
    D = 1e12
    d_wall = autonomy_wall_au(S, D)
    assert affordable_compute_at(S, d_wall * 2.0) < D
