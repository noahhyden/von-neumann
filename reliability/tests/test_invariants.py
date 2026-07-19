"""Fold-level invariants for reliability.mortality.step (issue #48, phase A).

Every invariant listed in the issue #48 spec (posted as an issue comment) has a
positive test (a normal run does not trip the assertion) and a negative test (a
hand-built state that violates the invariant does trip). The invariant tags
match the entries added to REFERENCES.md.

These tests are the contract; the assertions live in mortality._verify_step_invariants.
"""

import pytest

from reliability.mortality import (
    FleetState,
    _verify_step_invariants,
    simulate,
    step,
)


def _before() -> FleetState:
    return FleetState.initial(1000, seed=42)


# --- [inv:rl-alive-monotone] alive_new <= alive_old ---

def test_inv_rl_alive_monotone_positive():
    before = _before()
    after = step(before, hazard_per_day=1e-3)
    _verify_step_invariants(before, after)


def test_inv_rl_alive_monotone_negative():
    before = _before()
    after = FleetState(rng=before.rng, alive=before.alive + 1, day=before.day + 1)
    with pytest.raises(AssertionError, match=r"inv:rl-alive-monotone"):
        _verify_step_invariants(before, after)


# --- [inv:rl-alive-nonneg] alive_new >= 0 ---

def test_inv_rl_alive_nonneg_positive():
    before = _before()
    after = step(before, hazard_per_day=1e-3)
    _verify_step_invariants(before, after)


def test_inv_rl_alive_nonneg_negative():
    before = _before()
    after = FleetState(rng=before.rng, alive=-1, day=before.day + 1)
    with pytest.raises(AssertionError, match=r"inv:rl-alive-nonneg"):
        _verify_step_invariants(before, after)


# --- [inv:rl-day-monotone] day_new == day_old + 1 ---

def test_inv_rl_day_monotone_positive():
    before = _before()
    after = step(before, hazard_per_day=1e-3)
    _verify_step_invariants(before, after)


def test_inv_rl_day_monotone_negative():
    before = _before()
    same_day = FleetState(rng=before.rng, alive=before.alive, day=before.day)
    with pytest.raises(AssertionError, match=r"inv:rl-day-monotone"):
        _verify_step_invariants(before, same_day)
    jumped = FleetState(rng=before.rng, alive=before.alive, day=before.day + 2)
    with pytest.raises(AssertionError, match=r"inv:rl-day-monotone"):
        _verify_step_invariants(before, jumped)


# --- integration: a live run trips no assertion ---

def test_simulate_does_not_trip_invariants_across_hazards():
    for hazard in (0.0, 1e-4, 1e-3, 1e-2, 0.1):
        simulate(1000, days=100, hazard_per_day=hazard, seed=7)


def test_simulate_does_not_trip_invariants_at_boundaries():
    simulate(0, days=100, hazard_per_day=0.1, seed=1)
    simulate(1, days=1, hazard_per_day=1.0, seed=1)
