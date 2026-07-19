"""Trace-level invariants for closure_sim.replication.simulate (issue #48, phase A).

Every invariant has a positive test (a live run's trace does not trip) and a
negative test (a hand-built SimStep list violating the invariant does trip).
"""

import pytest

from closure_sim import Factory, ReplicationParams, Subsystem
from closure_sim.replication import (
    Regime,
    SimStep,
    _verify_trace_invariants,
    simulate,
)


def _mk_factory(closure: float = 1.0) -> Factory:
    total = 1000.0
    local = total * closure
    vit = total - local
    subs = []
    if local > 0:
        subs.append(Subsystem(name="local", mass_kg=local, category="structure",
                              producible_locally=True, energy_to_produce_kwh_per_kg=2.0))
    if vit > 0:
        subs.append(Subsystem(name="chips", mass_kg=vit, category="compute",
                              producible_locally=False, energy_to_produce_kwh_per_kg=1000.0))
    return Factory(name=f"c{closure}", subsystems=subs)


def _params() -> ReplicationParams:
    return ReplicationParams(
        seed_mass_kg=1000.0,
        local_build_rate_kg_per_day=10.0,
        vitamin_resupply_mass_kg=1e9,
        resupply_cadence_days=1.0,
        available_power_kw=1e9,
        target_output_kg_per_day=100.0,
        duration_days=1000,
        dt_days=1.0,
    )


def _live_trace():
    result = simulate(_mk_factory(closure=1.0), _params())
    return result.steps, result.productivity_per_day, result.energy_cap_kg_per_day, 1000.0


# --- [inv:cs-mass-monotone] mass[i+1] >= mass[i] * (1 - 1e-8) ---

def test_inv_cs_mass_monotone_positive():
    steps, alpha, ecap, seed = _live_trace()
    _verify_trace_invariants(steps, alpha=alpha, energy_cap=ecap, seed_mass_kg=seed)


def test_inv_cs_mass_monotone_negative():
    # Both masses >= seed_mass so only the monotone check trips.
    steps = [
        SimStep(day=0.0, factory_mass_kg=1500.0, installed_capacity_kg_per_day=15.0,
                output_kg_per_day=15.0, growth_rate_kg_per_day=15.0, regime=Regime.MATERIAL),
        SimStep(day=10.0, factory_mass_kg=1200.0, installed_capacity_kg_per_day=12.0,
                output_kg_per_day=12.0, growth_rate_kg_per_day=12.0, regime=Regime.MATERIAL),
    ]
    with pytest.raises(AssertionError, match=r"inv:cs-mass-monotone"):
        _verify_trace_invariants(steps, alpha=0.01, energy_cap=1e9, seed_mass_kg=1000.0)


# --- [inv:cs-mass-nonneg] mass >= seed_mass ---

def test_inv_cs_mass_nonneg_positive():
    steps, alpha, ecap, seed = _live_trace()
    _verify_trace_invariants(steps, alpha=alpha, energy_cap=ecap, seed_mass_kg=seed)


def test_inv_cs_mass_nonneg_negative():
    steps = [
        SimStep(day=0.0, factory_mass_kg=500.0, installed_capacity_kg_per_day=5.0,
                output_kg_per_day=5.0, growth_rate_kg_per_day=5.0, regime=Regime.MATERIAL),
    ]
    with pytest.raises(AssertionError, match=r"inv:cs-mass-nonneg"):
        _verify_trace_invariants(steps, alpha=0.01, energy_cap=1e9, seed_mass_kg=1000.0)


# --- [inv:cs-installed] installed == alpha * F ---

def test_inv_cs_installed_positive():
    steps, alpha, ecap, seed = _live_trace()
    _verify_trace_invariants(steps, alpha=alpha, energy_cap=ecap, seed_mass_kg=seed)


def test_inv_cs_installed_negative():
    steps = [
        SimStep(day=0.0, factory_mass_kg=1000.0, installed_capacity_kg_per_day=999.0,
                output_kg_per_day=999.0, growth_rate_kg_per_day=1.0, regime=Regime.MATERIAL),
    ]
    with pytest.raises(AssertionError, match=r"inv:cs-installed"):
        _verify_trace_invariants(steps, alpha=0.01, energy_cap=1e9, seed_mass_kg=1000.0)


# --- [inv:cs-output] output == min(installed, energy_cap) ---

def test_inv_cs_output_positive():
    steps, alpha, ecap, seed = _live_trace()
    _verify_trace_invariants(steps, alpha=alpha, energy_cap=ecap, seed_mass_kg=seed)


def test_inv_cs_output_negative():
    steps = [
        SimStep(day=0.0, factory_mass_kg=1000.0, installed_capacity_kg_per_day=10.0,
                output_kg_per_day=99.0, growth_rate_kg_per_day=10.0, regime=Regime.MATERIAL),
    ]
    with pytest.raises(AssertionError, match=r"inv:cs-output"):
        _verify_trace_invariants(steps, alpha=0.01, energy_cap=1e9, seed_mass_kg=1000.0)


# --- [inv:cs-growth-nonneg] growth >= 0 ---

def test_inv_cs_growth_nonneg_positive():
    steps, alpha, ecap, seed = _live_trace()
    _verify_trace_invariants(steps, alpha=alpha, energy_cap=ecap, seed_mass_kg=seed)


def test_inv_cs_growth_nonneg_negative():
    steps = [
        SimStep(day=0.0, factory_mass_kg=1000.0, installed_capacity_kg_per_day=10.0,
                output_kg_per_day=10.0, growth_rate_kg_per_day=-1.0, regime=Regime.MATERIAL),
    ]
    with pytest.raises(AssertionError, match=r"inv:cs-growth-nonneg"):
        _verify_trace_invariants(steps, alpha=0.01, energy_cap=1e9, seed_mass_kg=1000.0)


# --- integration: live runs across regimes do not trip ---

def test_simulate_does_not_trip_invariants_across_regimes():
    # material-limited, energy-limited, resupply-limited
    cases = [
        (1.0, {}),
        (0.9, {"available_power_kw": 0.05}),
        (0.5, {"vitamin_resupply_mass_kg": 100.0}),
    ]
    for closure, overrides in cases:
        base = dict(seed_mass_kg=1000.0, local_build_rate_kg_per_day=10.0,
                    vitamin_resupply_mass_kg=1e9, resupply_cadence_days=1.0,
                    available_power_kw=1e9, target_output_kg_per_day=100.0,
                    duration_days=500, dt_days=1.0)
        base.update(overrides)
        simulate(_mk_factory(closure), ReplicationParams(**base))
