"""The end-to-end mission fold: one deterministic run over the four sibling modules.

Given a `MissionScenario`, this chains the whole story of launching a self-replicating
probe operation, in six stages, each a call into an existing module's public API
(CLAUDE.md §4) - no new physics, no new numbers:

  0. LAUNCH      launch-economics - seed + vitamins launched at $/kg; the rocket
                 equation's propellant fraction shows *why* that $/kg is what it is.
  1. CLOSURE     closure-sim      - the factory's mass closure ratio.
  2. ARRIVE      probe-sim        - solar power delivered at heliocentric distance d
                                    (inverse-square).
  3. SPLIT       power-budget     - divide that power into build / think / housekeeping.
  4. REPLICATE   closure-sim      - feed the *manufacturing* share into the replication
                                    sim; does output ever reach target?
  5. THINK       power-budget     - the compute the *compute* share buys (FLOPS,
                                    brain-equivalents).
  6. PAYOFF      launch-economics - launch-mass leverage and $ saved vs. launching the
                                    finished installation, with vitamins set by closure.

Pure, deterministic, plain data; zero pimas imports (CLAUDE.md §7). This is the ground
truth the frontend's TS port is parity-tested against.
"""

from __future__ import annotations

from dataclasses import dataclass

from closure_sim.closure import compute_closure
from closure_sim.replication import simulate
from launch_economics.from_closure import comparison_from_closure
from launch_economics.launch import (
    exhaust_velocity_m_s,
    propellant_fraction,
)
from power_budget.budget import PowerBudget, compute_capacity_flops
from power_budget.physics import brain_equivalents
from probe_sim.environment import solar_irradiance_w_m2

from mission.scenario import MissionScenario


@dataclass
class MissionResult:
    """Every stage's headline numbers for one mission run."""

    # 1. closure
    closure_ratio: float

    # 0 / 6. launch + payoff
    seed_mass_kg: float
    target_installed_mass_kg: float
    vitamin_mass_kg: float
    launched_mass_kg: float
    mass_leverage: float  # installed kg per launched kg
    direct_launch_cost_usd: float
    replication_launch_cost_usd: float
    cost_savings_usd: float
    cost_ratio: float
    propellant_fraction: float  # physics context: fraction of wet mass that is propellant
    delta_v_m_s: float
    specific_impulse_s: float

    # 2. arrive (solar power at distance)
    distance_au: float
    irradiance_w_m2: float
    delivered_power_w: float

    # 3. split
    manufacturing_w: float
    compute_w: float
    housekeeping_w: float

    # 5. think
    compute_flops: float
    brain_equivalents: float

    # 4. replicate
    reaches_target: bool
    time_to_target_days: float | None
    final_output_kg_per_day: float
    doubling_time_days: float | None
    binding_regime: str | None


def run_mission(scenario: MissionScenario) -> MissionResult:
    """Run the whole chain once and return every stage's headline numbers."""
    factory = scenario.factory
    if factory.replication is None:
        raise ValueError("mission factory needs replication params")

    # 1. CLOSURE
    closure_ratio = compute_closure(factory).closure_ratio

    # 0 / 6. LAUNCH + PAYOFF - vitamins follow from closure; seed comes from the factory.
    comparison = comparison_from_closure(
        factory,
        target_installed_mass_kg=scenario.target_installed_mass_kg,
        seed_mass_kg=scenario.seed_mass_kg,
        cost_per_kg_usd=scenario.cost_per_kg_usd,
    )
    v_e = exhaust_velocity_m_s(scenario.specific_impulse_s)
    prop_frac = propellant_fraction(scenario.delta_v_m_s, v_e)

    # 2. ARRIVE - inverse-square solar power at the heliocentric distance.
    array = scenario.array
    delivered_w = array.power_w(scenario.distance_au)
    irradiance = solar_irradiance_w_m2(scenario.distance_au)

    # 3. SPLIT - one power split, routed to the two consumers below (reconciles the
    # modules: probe-sim's range.py gives the factory 100% of power; here the factory
    # gets only its manufacturing share, and compute gets its own).
    budget = PowerBudget(
        total_w=delivered_w,
        fraction_manufacturing=scenario.fraction_manufacturing,
        fraction_compute=scenario.fraction_compute,
        fraction_housekeeping=scenario.fraction_housekeeping,
    )

    # 5. THINK - the compute the compute-share buys.
    compute_flops = compute_capacity_flops(
        budget.compute_w, scenario.compute_efficiency_flops_per_w
    )

    # 4. REPLICATE - feed the manufacturing share (kW) into the replication sim. If the
    # split leaves no manufacturing power, the factory cannot build: report a stall
    # rather than asking the sim to run at zero power (ReplicationParams requires > 0).
    manufacturing_kw = budget.manufacturing_w / 1000.0
    if manufacturing_kw > 0.0:
        rep = factory.replication.model_copy(
            update={"available_power_kw": manufacturing_kw}
        )
        sim = simulate(factory, rep)
        reaches = sim.time_to_target_days is not None
        time_to_target = sim.time_to_target_days
        final_output = sim.final_output_kg_per_day
        doubling = sim.empirical_doubling_time_days
        binding_regime = (
            sim.regime_timeline[-1].regime.value if sim.regime_timeline else None
        )
    else:
        reaches = False
        time_to_target = None
        final_output = 0.0
        doubling = None
        binding_regime = None

    return MissionResult(
        closure_ratio=closure_ratio,
        seed_mass_kg=comparison.seed_mass_kg,
        target_installed_mass_kg=comparison.target_installed_mass_kg,
        vitamin_mass_kg=comparison.vitamin_mass_total_kg,
        launched_mass_kg=comparison.launched_mass_kg,
        mass_leverage=comparison.mass_leverage,
        direct_launch_cost_usd=comparison.direct_launch_cost_usd,
        replication_launch_cost_usd=comparison.replication_launch_cost_usd,
        cost_savings_usd=comparison.cost_savings_usd,
        cost_ratio=comparison.cost_ratio,
        propellant_fraction=prop_frac,
        delta_v_m_s=scenario.delta_v_m_s,
        specific_impulse_s=scenario.specific_impulse_s,
        distance_au=scenario.distance_au,
        irradiance_w_m2=irradiance,
        delivered_power_w=delivered_w,
        manufacturing_w=budget.manufacturing_w,
        compute_w=budget.compute_w,
        housekeeping_w=budget.housekeeping_w,
        compute_flops=compute_flops,
        brain_equivalents=brain_equivalents(compute_flops),
        reaches_target=reaches,
        time_to_target_days=time_to_target,
        final_output_kg_per_day=final_output,
        doubling_time_days=doubling,
        binding_regime=binding_regime,
    )
