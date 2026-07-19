"""Step invariants for swarm.sim.step / step_event (issue #48, phase A).

Swarm mutates state in place; the verifier compares a snapshot taken before the
step to the post-step state. Positive + negative per invariant. Tags match
REFERENCES.md.
"""

import pytest

from swarm import SwarmParams, initial_state, simulate_swarm
from swarm.models import Probe
from swarm.sim import _snapshot_invariant_state, _verify_step_invariants, step, step_event


def _fresh():
    params = SwarmParams(n_stars=300)
    state = initial_state(params, seed=1)
    return state, params


# --- [inv:sw-year-monotone] year_new >= year_old ---

def test_inv_sw_year_monotone_positive():
    state, params = _fresh()
    snap = _snapshot_invariant_state(state)
    step(state, params)
    _verify_step_invariants(snap, state)


def test_inv_sw_year_monotone_negative():
    state, params = _fresh()
    snap = _snapshot_invariant_state(state)
    state.year = snap.year - 1.0
    with pytest.raises(AssertionError, match=r"inv:sw-year-monotone"):
        _verify_step_invariants(snap, state)


# --- [inv:sw-settled-monotone] settled_count monotone ---

def test_inv_sw_settled_monotone_positive():
    state, params = _fresh()
    snap = _snapshot_invariant_state(state)
    step(state, params)
    _verify_step_invariants(snap, state)


def test_inv_sw_settled_monotone_negative():
    state, params = _fresh()
    snap = _snapshot_invariant_state(state)
    state.year = snap.year + 1.0
    state.settled_count = snap.settled_count - 1  # illegal
    with pytest.raises(AssertionError, match=r"inv:sw-settled-monotone"):
        _verify_step_invariants(snap, state)


# --- [inv:sw-settled-latch] once settled, never unsettled ---

def test_inv_sw_settled_latch_positive():
    state, params = _fresh()
    step(state, params)
    step(state, params)
    snap = _snapshot_invariant_state(state)
    step(state, params)
    _verify_step_invariants(snap, state)


def test_inv_sw_settled_latch_negative():
    state, params = _fresh()
    step(state, params)  # let the origin get settled
    snap = _snapshot_invariant_state(state)
    # Unlatch a settled star.
    for i, y in enumerate(state.settled_year):
        if y >= 0.0:
            state.settled_year[i] = -1.0
            break
    state.year = snap.year + 1.0
    with pytest.raises(AssertionError, match=r"inv:sw-settled-latch"):
        _verify_step_invariants(snap, state)


# --- [inv:sw-front-monotone] front_radius monotone ---

def test_inv_sw_front_monotone_positive():
    state, params = _fresh()
    snap = _snapshot_invariant_state(state)
    step(state, params)
    _verify_step_invariants(snap, state)


def test_inv_sw_front_monotone_negative():
    state, params = _fresh()
    step(state, params)
    snap = _snapshot_invariant_state(state)
    state.year = snap.year + 1.0
    state.front_radius = snap.front_radius - 1.0  # any decrease is illegal
    with pytest.raises(AssertionError, match=r"inv:sw-front-monotone"):
        _verify_step_invariants(snap, state)


# --- [inv:sw-launched-monotone] total_launched monotone ---

def test_inv_sw_launched_monotone_positive():
    state, params = _fresh()
    snap = _snapshot_invariant_state(state)
    step(state, params)
    _verify_step_invariants(snap, state)


def test_inv_sw_launched_monotone_negative():
    state, params = _fresh()
    snap = _snapshot_invariant_state(state)
    state.year = snap.year + 1.0
    state.total_launched = snap.total_launched - 1
    with pytest.raises(AssertionError, match=r"inv:sw-launched-monotone"):
        _verify_step_invariants(snap, state)


# --- [inv:sw-probe-ids-unique] no probe id twice ---

def test_inv_sw_probe_ids_unique_positive():
    state, params = _fresh()
    snap = _snapshot_invariant_state(state)
    step(state, params)
    _verify_step_invariants(snap, state)


def test_inv_sw_probe_ids_unique_negative():
    state, params = _fresh()
    step(state, params)
    snap = _snapshot_invariant_state(state)
    state.year = snap.year + 1.0
    # The dict key is unique by construction; the invariant checks the *Probe.id*
    # values. Insert a probe under a fresh key but with a duplicated .id.
    state.probes[999_999_001] = Probe(id=42, target=0, arrive_year=1.0, speed_pc_yr=0.01)
    state.probes[999_999_002] = Probe(id=42, target=1, arrive_year=1.0, speed_pc_yr=0.01)
    with pytest.raises(AssertionError, match=r"inv:sw-probe-ids-unique"):
        _verify_step_invariants(snap, state)


# --- integration: live runs do not trip any invariant ---

def test_simulate_swarm_does_not_trip_invariants():
    for stepping in ("fixed", "event"):
        simulate_swarm(SwarmParams(n_stars=200, stepping=stepping), seed=1)


def test_step_event_does_not_trip_invariants():
    state, params = _fresh()
    for _ in range(50):
        snap = _snapshot_invariant_state(state)
        step_event(state, params)
        _verify_step_invariants(snap, state)
