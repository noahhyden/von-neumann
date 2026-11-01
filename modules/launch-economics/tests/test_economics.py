"""The self-replication launch payoff: leverage, cost ratio, savings."""

import pytest
from pydantic import ValidationError

from launch_economics.economics import ReplicationLaunchComparison


def make_case() -> ReplicationLaunchComparison:
    # Want 1000 t installed; land a 10 t seed, import 3 t of vitamins; $3000/kg.
    return ReplicationLaunchComparison(
        target_installed_mass_kg=1_000_000.0,
        seed_mass_kg=10_000.0,
        vitamin_mass_total_kg=3_000.0,
        cost_per_kg_usd=3_000.0,
    )


def test_launched_mass_is_seed_plus_vitamins():
    c = make_case()
    assert c.launched_mass_kg == pytest.approx(13_000.0)


def test_costs():
    c = make_case()
    assert c.direct_launch_cost_usd == pytest.approx(1_000_000.0 * 3_000.0)
    assert c.replication_launch_cost_usd == pytest.approx(13_000.0 * 3_000.0)
    assert c.cost_savings_usd == pytest.approx(
        c.direct_launch_cost_usd - c.replication_launch_cost_usd
    )


def test_mass_leverage_and_cost_ratio_are_reciprocal():
    c = make_case()
    # 1,000,000 / 13,000 ~= 76.9 installed kg per launched kg.
    assert c.mass_leverage == pytest.approx(1_000_000.0 / 13_000.0)
    assert c.mass_leverage == pytest.approx(76.92, rel=1e-3)
    # cost ratio is the inverse of mass leverage (same $/kg both sides).
    assert c.cost_ratio == pytest.approx(1.0 / c.mass_leverage)


def test_zero_vitamins_is_pure_closure():
    # Full closure (no imports): leverage = target / seed.
    c = ReplicationLaunchComparison(
        target_installed_mass_kg=1_000_000.0,
        seed_mass_kg=10_000.0,
        vitamin_mass_total_kg=0.0,
        cost_per_kg_usd=3_000.0,
    )
    assert c.mass_leverage == pytest.approx(100.0)


def test_more_vitamins_lowers_leverage():
    # Lower closure -> more imported vitamins -> less leverage.
    low_vitamins = ReplicationLaunchComparison(
        target_installed_mass_kg=1_000_000.0,
        seed_mass_kg=10_000.0,
        vitamin_mass_total_kg=3_000.0,
        cost_per_kg_usd=3_000.0,
    )
    high_vitamins = ReplicationLaunchComparison(
        target_installed_mass_kg=1_000_000.0,
        seed_mass_kg=10_000.0,
        vitamin_mass_total_kg=90_000.0,
        cost_per_kg_usd=3_000.0,
    )
    assert high_vitamins.mass_leverage < low_vitamins.mass_leverage


def test_invalid_inputs_raise():
    with pytest.raises(ValidationError):
        ReplicationLaunchComparison(
            target_installed_mass_kg=0.0,
            seed_mass_kg=10_000.0,
            cost_per_kg_usd=3_000.0,
        )
    with pytest.raises(ValidationError):
        ReplicationLaunchComparison(
            target_installed_mass_kg=1_000.0,
            seed_mass_kg=-1.0,
            cost_per_kg_usd=3_000.0,
        )
