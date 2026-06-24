import math

import pytest

from closure_sim import (
    Factory,
    Regime,
    ReplicationParams,
    Subsystem,
    simulate,
)


def factory(closure: float, *, local_energy=2.0, vit_energy=1000.0) -> Factory:
    """Build a factory whose mass closure equals `closure` (0..1)."""
    total = 1000.0
    local = total * closure
    vit = total - local
    subs = []
    if local > 0:
        subs.append(Subsystem(name="local", mass_kg=local, category="structure",
                              producible_locally=True,
                              energy_to_produce_kwh_per_kg=local_energy))
    if vit > 0:
        subs.append(Subsystem(name="chips", mass_kg=vit, category="compute",
                              producible_locally=False,
                              energy_to_produce_kwh_per_kg=vit_energy))
    return Factory(name=f"c{closure}", subsystems=subs)


def params(**kw) -> ReplicationParams:
    base = dict(
        seed_mass_kg=1000.0,
        local_build_rate_kg_per_day=10.0,
        vitamin_resupply_mass_kg=1e9,   # effectively unlimited unless overridden
        resupply_cadence_days=1.0,
        available_power_kw=1e9,         # effectively unlimited unless overridden
        target_output_kg_per_day=100.0,
        duration_days=2000,
        dt_days=0.25,
    )
    base.update(kw)
    return ReplicationParams(**base)


# --- Material-limited regime: exponential, doubling matches analytic ---

def test_material_limited_doubling_matches_analytic():
    C = 0.9
    f = factory(C)
    p = params()  # power + resupply effectively unlimited -> material-limited
    r = simulate(f, p)
    assert r.regime_timeline[0].regime == Regime.MATERIAL
    # analytic doubling = ln2 * C / alpha ; alpha = 10/1000 = 0.01
    assert r.analytic_doubling_time_days == pytest.approx(math.log(2) * C / 0.01)
    # empirical (Euler, small dt) should track analytic within a couple percent
    assert r.empirical_doubling_time_days == pytest.approx(
        r.analytic_doubling_time_days, rel=0.02
    )


def test_growth_is_monotonic():
    r = simulate(factory(0.9), params())
    masses = [s.factory_mass_kg for s in r.steps]
    assert all(b >= a for a, b in zip(masses, masses[1:]))


# --- Resupply-limited regime: linear ceiling at R/(1-C) ---

def test_resupply_ceiling_value_and_regime():
    C = 0.8
    f = factory(C)
    # R = 5/1 = 5 kg/day -> ceiling = 5 / (1-0.8) = 25 kg/day
    p = params(vitamin_resupply_mass_kg=5.0, resupply_cadence_days=1.0)
    r = simulate(f, p)
    assert r.resupply_ceiling_kg_per_day == pytest.approx(25.0)
    # eventually the constant ceiling binds and growth becomes resupply-limited
    assert r.regime_timeline[-1].regime == Regime.RESUPPLY
    # once resupply-limited, dF/dt should equal the ceiling
    last = r.steps[-1]
    assert last.growth_rate_kg_per_day == pytest.approx(25.0)


def test_resupply_zero_with_partial_closure_stalls():
    # No vitamins arriving and C < 1 -> cannot grow at all.
    r = simulate(factory(0.9), params(vitamin_resupply_mass_kg=0.0))
    assert r.resupply_ceiling_kg_per_day == pytest.approx(0.0)
    assert r.final_factory_mass_kg == pytest.approx(1000.0)
    assert r.time_to_target_days is None
    assert r.regime_timeline[0].regime == Regime.RESUPPLY


# --- Full closure: never resupply-limited, exponential even with no resupply ---

def test_full_closure_is_unbounded_by_resupply():
    r = simulate(factory(1.0), params(vitamin_resupply_mass_kg=0.0))
    assert math.isinf(r.resupply_ceiling_kg_per_day)
    assert r.regime_timeline[0].regime == Regime.MATERIAL
    # grows despite zero resupply
    assert r.final_factory_mass_kg > 1000.0
    assert r.time_to_target_days is not None


def test_zero_closure_is_pure_linear_resupply():
    # C = 0: nothing made locally; growth is exactly R per day, regardless of F.
    f = factory(0.0)
    p = params(vitamin_resupply_mass_kg=4.0, resupply_cadence_days=1.0)
    r = simulate(f, p)
    assert r.regime_timeline[0].regime == Regime.RESUPPLY
    # dF/dt = R/(1-0) = 4 kg/day, constant
    assert all(s.growth_rate_kg_per_day == pytest.approx(4.0) for s in r.steps)


# --- Energy-limited regime ---

def test_energy_limited_caps_local_production():
    C = 1.0  # full closure so resupply never binds; isolate energy
    f = factory(C, local_energy=10.0)
    # available power tiny: 1 kW * 24 h = 24 kWh/day ; e_local = 10 kWh/kg
    # -> energy cap = 2.4 kg/day local output
    p = params(available_power_kw=1.0, vitamin_resupply_mass_kg=0.0,
               duration_days=100)
    r = simulate(f, p)
    assert r.energy_cap_kg_per_day == pytest.approx(2.4)
    # alpha*F starts at 10 kg/day > 2.4 cap -> energy-limited from the start
    assert r.regime_timeline[0].regime == Regime.ENERGY
    # growth rate capped: dF/dt = energy_cap / C = 2.4
    assert r.steps[0].growth_rate_kg_per_day == pytest.approx(2.4)


# --- time-to-target ---

def test_time_to_target_reached_and_never():
    # Reached: generous everything.
    reached = simulate(factory(0.95), params(target_output_kg_per_day=50.0))
    assert reached.time_to_target_days is not None

    # Never: stalled factory can't reach target within the horizon.
    never = simulate(
        factory(0.9),
        params(vitamin_resupply_mass_kg=0.0, target_output_kg_per_day=50.0),
    )
    assert never.time_to_target_days is None


def test_higher_closure_replicates_faster():
    p = params(vitamin_resupply_mass_kg=5.0, resupply_cadence_days=1.0,
               target_output_kg_per_day=80.0)
    hi = simulate(factory(0.95), p)
    lo = simulate(factory(0.6), p)
    assert hi.time_to_target_days < lo.time_to_target_days
