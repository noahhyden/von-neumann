"""Leverage as a function of closure - the launch-economics × closure-sim coupling."""

import pytest
from closure_sim.models import Factory, Subsystem

from launch_economics.from_closure import comparison_from_closure, vitamin_mass_for_build


def factory_with_closure(local_kg: float, vitamin_kg: float) -> Factory:
    """A minimal factory with a chosen closure = local / (local + vitamin)."""
    subs = [
        Subsystem(name="local", mass_kg=local_kg, category="structure", producible_locally=True),
    ]
    if vitamin_kg > 0:
        subs.append(
            Subsystem(name="chips", mass_kg=vitamin_kg, category="electronics", producible_locally=False)
        )
    return Factory(name="test", subsystems=subs)


def test_vitamin_mass_for_build_mass_balance():
    assert vitamin_mass_for_build(1.0, 1000.0) == pytest.approx(0.0)  # full closure, no imports
    assert vitamin_mass_for_build(0.0, 1000.0) == pytest.approx(1000.0)  # no closure, all imported
    assert vitamin_mass_for_build(0.7, 1000.0) == pytest.approx(300.0)


def test_vitamin_mass_for_build_rejects_bad_inputs():
    with pytest.raises(ValueError):
        vitamin_mass_for_build(1.5, 1000.0)
    with pytest.raises(ValueError):
        vitamin_mass_for_build(0.5, -1.0)


def test_full_closure_launches_only_the_seed():
    c = comparison_from_closure(
        factory_with_closure(1000.0, 0.0),  # C = 1.0
        target_installed_mass_kg=1_000_000.0,
        seed_mass_kg=10_000.0,
        cost_per_kg_usd=3_000.0,
    )
    assert c.vitamin_mass_total_kg == pytest.approx(0.0)
    assert c.mass_leverage == pytest.approx(100.0)  # target / seed


def test_partial_closure_needs_vitamins():
    # C = 700 / 1000 = 0.7; build mass = target - seed = 990,000.
    c = comparison_from_closure(
        factory_with_closure(700.0, 300.0),
        target_installed_mass_kg=1_000_000.0,
        seed_mass_kg=10_000.0,
        cost_per_kg_usd=3_000.0,
    )
    assert c.vitamin_mass_total_kg == pytest.approx(0.3 * 990_000.0)
    launched = 10_000.0 + 0.3 * 990_000.0
    assert c.mass_leverage == pytest.approx(1_000_000.0 / launched)


def test_higher_closure_gives_more_leverage():
    kw = dict(target_installed_mass_kg=1_000_000.0, seed_mass_kg=10_000.0, cost_per_kg_usd=3_000.0)
    low = comparison_from_closure(factory_with_closure(500.0, 500.0), **kw)   # C=0.5
    high = comparison_from_closure(factory_with_closure(950.0, 50.0), **kw)   # C=0.95
    assert high.mass_leverage > low.mass_leverage
    # And full closure beats both.
    full = comparison_from_closure(factory_with_closure(1000.0, 0.0), **kw)
    assert full.mass_leverage > high.mass_leverage
