import pytest

from closure_sim import Factory, ReplicationParams, Subsystem, electronics_wall
from closure_sim.scenarios import load_factory
from pathlib import Path

SCEN = Path(__file__).resolve().parents[1] / "scenarios"


def params(**kw) -> ReplicationParams:
    base = dict(
        seed_mass_kg=1000.0,
        local_build_rate_kg_per_day=10.0,
        vitamin_resupply_mass_kg=5.0,
        resupply_cadence_days=1.0,
        available_power_kw=1e6,
        target_output_kg_per_day=80.0,
        duration_days=20000,
        dt_days=1.0,
    )
    base.update(kw)
    return ReplicationParams(**base)


def electronics_factory() -> Factory:
    return Factory(
        name="ew",
        subsystems=[
            Subsystem(name="frame", mass_kg=600, category="structure",
                      producible_locally=True, energy_to_produce_kwh_per_kg=2.0),
            Subsystem(name="chips", mass_kg=400, category="compute",
                      producible_locally=False,
                      energy_to_produce_kwh_per_kg=2000.0),
        ],
    )


def test_wall_raises_closure_and_ceiling():
    rep = electronics_wall(electronics_factory(), params())
    assert rep.before.closure_ratio == pytest.approx(0.6)
    assert rep.after.closure_ratio == pytest.approx(1.0)
    assert rep.electronics_mass_kg == pytest.approx(400)
    # Before: finite resupply ceiling; after full closure: unbounded.
    assert rep.after.resupply_ceiling_kg_per_day > rep.before.resupply_ceiling_kg_per_day


def test_wall_makes_target_reachable_or_faster():
    rep = electronics_wall(electronics_factory(), params())
    # Before is resupply-bottlenecked; after should reach target at least as fast.
    b = rep.before.time_to_target_days
    a = rep.after.time_to_target_days
    assert a is not None
    if b is not None:
        assert a <= b
        assert rep.time_to_target_delta_days == pytest.approx(b - a)


def test_wall_no_electronics_no_change():
    f = Factory(
        name="noelec",
        subsystems=[
            Subsystem(name="frame", mass_kg=600, category="structure",
                      producible_locally=True),
            Subsystem(name="alloy", mass_kg=400, category="structure",
                      producible_locally=False),
        ],
    )
    rep = electronics_wall(f, params())
    assert rep.electronics_mass_kg == 0
    assert rep.before.closure_ratio == pytest.approx(rep.after.closure_ratio)


def test_example_scenarios_load_and_run():
    for name in ("lunar_regolith_seed.yaml", "low_closure.yaml"):
        f = load_factory(SCEN / name)
        rep = electronics_wall(f)
        assert rep.after.closure_ratio >= rep.before.closure_ratio
