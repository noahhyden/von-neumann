"""Launch-mass leverage as a function of closure - the launch-economics × closure-sim tie."""

from __future__ import annotations

from closure_sim.closure import compute_closure
from closure_sim.models import Factory

from launch_economics.economics import ReplicationLaunchComparison


def vitamin_mass_for_build(closure_ratio: float, built_mass_kg: float) -> float:
    """Imported vitamin mass to locally build ``built_mass_kg`` at a given closure."""
    if not 0.0 <= closure_ratio <= 1.0:
        raise ValueError("closure_ratio must be in [0, 1]")
    if built_mass_kg < 0:
        raise ValueError("built_mass_kg must be non-negative")
    return (1.0 - closure_ratio) * built_mass_kg


def comparison_from_closure(
    factory: Factory,
    *,
    target_installed_mass_kg: float,
    seed_mass_kg: float,
    cost_per_kg_usd: float,
) -> ReplicationLaunchComparison:
    """Build a launch comparison whose vitamin mass is derived from ``factory``'s closure."""
    closure_ratio = compute_closure(factory).closure_ratio
    built_mass_kg = max(0.0, target_installed_mass_kg - seed_mass_kg)
    vitamins = vitamin_mass_for_build(closure_ratio, built_mass_kg)
    return ReplicationLaunchComparison(
        target_installed_mass_kg=target_installed_mass_kg,
        seed_mass_kg=seed_mass_kg,
        vitamin_mass_total_kg=vitamins,
        cost_per_kg_usd=cost_per_kg_usd,
    )
