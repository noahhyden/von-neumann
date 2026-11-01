import math

import pytest

from closure_sim import Factory, Subsystem, compute_closure


def make_factory(**kw) -> Factory:
    subs = [
        Subsystem(name="frame", mass_kg=900, category="structure",
                  producible_locally=True, energy_to_produce_kwh_per_kg=2.0),
        Subsystem(name="chips", mass_kg=100, category="compute",
                  producible_locally=False, energy_to_produce_kwh_per_kg=1000.0,
                  processes=["semiconductor_fab"]),
    ]
    return Factory(name="t", subsystems=subs, **kw)


def test_closure_ratio_basic():
    r = compute_closure(make_factory())
    assert r.total_mass_kg == 1000
    assert r.local_mass_kg == 900
    assert r.vitamin_mass_kg == 100
    assert r.closure_ratio == pytest.approx(0.9)


def test_full_closure():
    f = Factory(
        name="closed",
        subsystems=[
            Subsystem(name="a", mass_kg=500, category="structure",
                      producible_locally=True),
            Subsystem(name="b", mass_kg=500, category="power",
                      producible_locally=True),
        ],
    )
    r = compute_closure(f)
    assert r.closure_ratio == pytest.approx(1.0)
    assert r.vitamins == []
    assert r.vitamin_mass_kg == 0


def test_zero_closure():
    f = Factory(
        name="open",
        subsystems=[
            Subsystem(name="a", mass_kg=500, category="compute",
                      producible_locally=False),
        ],
    )
    assert compute_closure(f).closure_ratio == pytest.approx(0.0)


def test_vitamin_breakdown_and_share():
    r = compute_closure(make_factory())
    assert len(r.vitamins) == 1
    v = r.vitamins[0]
    assert v.name == "chips"
    assert v.mass_share == pytest.approx(0.1)
    assert "semiconductor_fab" in v.processes


def test_vitamins_sorted_heaviest_first():
    f = Factory(
        name="multi",
        subsystems=[
            Subsystem(name="small", mass_kg=10, category="compute",
                      producible_locally=False),
            Subsystem(name="big", mass_kg=300, category="electronics",
                      producible_locally=False),
            Subsystem(name="mid", mass_kg=50, category="sensors",
                      producible_locally=False),
        ],
    )
    masses = [v.mass_kg for v in compute_closure(f).vitamins]
    assert masses == [300, 50, 10]


def test_build_energy():
    r = compute_closure(make_factory())
    # frame: 900 * 2 = 1800 ; chips: 100 * 1000 = 100000
    assert r.total_build_energy_kwh == pytest.approx(101800)
    assert r.local_build_energy_kwh == pytest.approx(1800)
