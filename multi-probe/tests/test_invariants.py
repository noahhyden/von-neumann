"""Fold-level invariants for multi_probe.fleet.step (issue #48, phase A).

Positive + negative test per invariant. Invariant tags match REFERENCES.md.
"""

import copy

import pytest

from multi_probe.fleet import _verify_step_invariants, initial_state, simulate_fleet, step
from multi_probe.models import FleetParams, FleetState, Probe, ProbeStatus


def _params(**overrides) -> FleetParams:
    base = dict(
        seed_mass_kg=100.0,
        closure_ratio=0.9,
        e_local_kwh_per_kg=1.0,
        local_build_rate_kg_per_day=1.0,
        array_area_m2=10.0,
        array_efficiency=0.3,
        manufacturing_fraction=0.5,
        vitamin_pool_kg=1_000_000.0,
        max_probes=64,
    )
    base.update(overrides)
    return FleetParams(**base)


def _before(params: FleetParams | None = None) -> FleetState:
    return initial_state(params or _params(), seed=42)


# --- [inv:mp-vitamin-conservation] pool_new + N_new * v_per_child == pool_old ---

def test_inv_mp_vitamin_conservation_positive():
    params = _params()
    before = _before(params)
    after = step(before, params, dt=200.0)
    _verify_step_invariants(before, after, params=params, dt=200.0)


def test_inv_mp_vitamin_conservation_negative():
    params = _params()
    before = _before(params)
    # Legal after, then perturb the pool to fake a bookkeeping error.
    after = step(before, params, dt=200.0)
    bad = FleetState(
        rng=after.rng,
        day=after.day,
        probes=after.probes,
        vitamin_pool_kg=after.vitamin_pool_kg + 1.0,  # extra vitamins from thin air
        next_id=after.next_id,
    )
    with pytest.raises(AssertionError, match=r"inv:mp-vitamin-conservation"):
        _verify_step_invariants(before, bad, params=params, dt=200.0)


# --- [inv:mp-vitamin-nonneg] pool_new >= 0 ---

def test_inv_mp_vitamin_nonneg_positive():
    params = _params()
    before = _before(params)
    after = step(before, params, dt=10.0)
    _verify_step_invariants(before, after, params=params, dt=10.0)


def test_inv_mp_vitamin_nonneg_negative():
    params = _params()
    before = _before(params)
    bad = FleetState(
        rng=before.rng,
        day=before.day + 10.0,
        probes=before.probes,
        vitamin_pool_kg=-1.0,
        next_id=before.next_id,
    )
    with pytest.raises(AssertionError, match=r"inv:mp-vitamin-nonneg"):
        _verify_step_invariants(before, bad, params=params, dt=10.0)


# --- [inv:mp-cap] len(probes_new) <= max_probes ---

def test_inv_mp_cap_positive():
    params = _params(max_probes=64)
    before = _before(params)
    after = step(before, params, dt=100.0)
    _verify_step_invariants(before, after, params=params, dt=100.0)


def test_inv_mp_cap_negative():
    params = _params(max_probes=2)
    before = _before(params)
    fake_probes = [Probe(id=i, distance_au=1.0, status=ProbeStatus.ACTIVE, arrival_day=0.0)
                   for i in range(5)]
    bad = FleetState(
        rng=before.rng,
        day=before.day + 1.0,
        probes=fake_probes,
        vitamin_pool_kg=before.vitamin_pool_kg,
        next_id=5,
    )
    with pytest.raises(AssertionError, match=r"inv:mp-cap"):
        _verify_step_invariants(before, bad, params=params, dt=1.0)


# --- [inv:mp-day] day_new == day_old + dt ---

def test_inv_mp_day_positive():
    params = _params()
    before = _before(params)
    after = step(before, params, dt=7.5)
    _verify_step_invariants(before, after, params=params, dt=7.5)


def test_inv_mp_day_negative():
    params = _params()
    before = _before(params)
    bad = FleetState(
        rng=before.rng,
        day=before.day + 999.0,  # dt asked for 1.0
        probes=before.probes,
        vitamin_pool_kg=before.vitamin_pool_kg,
        next_id=before.next_id,
    )
    with pytest.raises(AssertionError, match=r"inv:mp-day"):
        _verify_step_invariants(before, bad, params=params, dt=1.0)


# --- [inv:mp-next-id-monotone] next_id monotone, delta == N_newborn ---

def test_inv_mp_next_id_monotone_positive():
    params = _params()
    before = _before(params)
    after = step(before, params, dt=200.0)
    _verify_step_invariants(before, after, params=params, dt=200.0)


def test_inv_mp_next_id_monotone_negative():
    params = _params()
    before = _before(params)
    bad = FleetState(
        rng=before.rng,
        day=before.day + 1.0,
        probes=before.probes,
        vitamin_pool_kg=before.vitamin_pool_kg,
        next_id=before.next_id - 1,  # went backwards
    )
    with pytest.raises(AssertionError, match=r"inv:mp-next-id-monotone"):
        _verify_step_invariants(before, bad, params=params, dt=1.0)


# --- [inv:mp-status-transitions] no id disappears; ACTIVE stays ACTIVE ---

def test_inv_mp_status_transitions_positive():
    params = _params()
    before = _before(params)
    after = step(before, params, dt=200.0)
    _verify_step_invariants(before, after, params=params, dt=200.0)


def test_inv_mp_status_transitions_negative_id_vanished():
    params = _params()
    before = _before(params)
    bad = FleetState(
        rng=before.rng,
        day=before.day + 1.0,
        probes=[],  # a seed probe just disappeared
        vitamin_pool_kg=before.vitamin_pool_kg,
        next_id=before.next_id,
    )
    with pytest.raises(AssertionError, match=r"inv:mp-status-transitions"):
        _verify_step_invariants(before, bad, params=params, dt=1.0)


def test_inv_mp_status_transitions_negative_active_to_traveling():
    params = _params()
    before = _before(params)
    flipped = copy.deepcopy(before)
    flipped_probes = [
        Probe(
            id=p.id, distance_au=p.distance_au, status=ProbeStatus.TRAVELING,
            arrival_day=p.arrival_day, built_kg=p.built_kg, children=p.children,
        )
        for p in flipped.probes
    ]
    bad = FleetState(
        rng=before.rng,
        day=before.day + 1.0,
        probes=flipped_probes,
        vitamin_pool_kg=before.vitamin_pool_kg,
        next_id=before.next_id,
    )
    with pytest.raises(AssertionError, match=r"inv:mp-status-transitions"):
        _verify_step_invariants(before, bad, params=params, dt=1.0)


# --- [inv:mp-children-monotone] each probe's children counter monotone ---

def test_inv_mp_children_monotone_positive():
    params = _params()
    before = _before(params)
    after = step(before, params, dt=200.0)
    _verify_step_invariants(before, after, params=params, dt=200.0)


def test_inv_mp_children_monotone_negative():
    params = _params()
    before = _before(params)
    # A probe's children count went backwards - illegal.
    seed = before.probes[0]
    manipulated = FleetState(
        rng=before.rng,
        day=before.day,
        probes=[Probe(id=seed.id, distance_au=seed.distance_au, status=seed.status,
                       arrival_day=seed.arrival_day, built_kg=seed.built_kg, children=5)],
        vitamin_pool_kg=before.vitamin_pool_kg,
        next_id=before.next_id,
    )
    bad = FleetState(
        rng=manipulated.rng,
        day=manipulated.day + 1.0,
        probes=[Probe(id=seed.id, distance_au=seed.distance_au, status=seed.status,
                       arrival_day=seed.arrival_day, built_kg=seed.built_kg, children=3)],
        vitamin_pool_kg=manipulated.vitamin_pool_kg,
        next_id=manipulated.next_id,
    )
    with pytest.raises(AssertionError, match=r"inv:mp-children-monotone"):
        _verify_step_invariants(manipulated, bad, params=params, dt=1.0)


# --- integration: real runs do not trip any invariant ---

def test_simulate_fleet_does_not_trip_invariants():
    for closure in (0.5, 0.9, 0.99):
        params = _params(closure_ratio=closure, max_probes=16)
        simulate_fleet(params, seed=1, duration_days=1000.0, dt_days=10.0)
