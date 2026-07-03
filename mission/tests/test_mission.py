"""End-to-end behavior tests for the mission fold.

These assert on real numbers and the regimes that matter (CLAUDE.md §2): the chain
reaches target near Earth, is power-starved far out, stalls when no power goes to
manufacturing, obeys the inverse-square law, and prices the launch payoff from closure.
Not "it ran" - what it computed.
"""

from __future__ import annotations

import math

import pytest

from mission import MissionResult, default_mission_scenario, run_mission


@pytest.fixture
def baseline() -> MissionResult:
    return run_mission(default_mission_scenario())


def test_baseline_closure_matches_scenario(baseline: MissionResult) -> None:
    # The lunar-regolith seed factory closes at ~97.08% (closure-sim ground truth).
    assert baseline.closure_ratio == pytest.approx(0.970833, abs=1e-5)


def test_baseline_delivers_scenario_power_at_1au(baseline: MissionResult) -> None:
    # The array is sized to reproduce the scenario's ~4 MW at 1 AU.
    assert baseline.distance_au == 1.0
    assert baseline.irradiance_w_m2 == pytest.approx(1360.8, abs=1e-3)
    assert baseline.delivered_power_w == pytest.approx(4_000_000.0, rel=1e-4)


def test_power_split_sums_to_delivered(baseline: MissionResult) -> None:
    # 70/20/10 split of delivered power, exactly.
    total = (
        baseline.manufacturing_w + baseline.compute_w + baseline.housekeeping_w
    )
    assert total == pytest.approx(baseline.delivered_power_w, rel=1e-9)
    assert baseline.manufacturing_w == pytest.approx(0.70 * baseline.delivered_power_w, rel=1e-9)


def test_baseline_reaches_target_near_earth(baseline: MissionResult) -> None:
    # With ~2.8 MW to manufacturing, the factory reaches target output; the known
    # figure for this scenario is ~10512 days, and it ends resupply-limited.
    assert baseline.reaches_target is True
    assert baseline.time_to_target_days == pytest.approx(10512.289, abs=1.0)
    assert baseline.binding_regime == "resupply-limited"


def test_compute_leg_scales_with_efficiency_and_share() -> None:
    # compute FLOPS = compute_W * efficiency; brain-equivalents = FLOPS / 1e18.
    r = run_mission(default_mission_scenario())
    assert r.compute_flops == pytest.approx(
        r.compute_w * 1e11, rel=1e-9
    )
    assert r.brain_equivalents == pytest.approx(r.compute_flops / 1e18, rel=1e-9)


def test_inverse_square_power_falloff() -> None:
    # Doubling heliocentric distance quarters delivered power.
    near = run_mission(default_mission_scenario(distance_au=1.0)).delivered_power_w
    far = run_mission(default_mission_scenario(distance_au=2.0)).delivered_power_w
    assert near / far == pytest.approx(4.0, rel=1e-9)


def test_power_starved_far_from_sun_fails_to_replicate() -> None:
    # At Jupiter's distance the array delivers ~150 kW; the manufacturing share is too
    # little for the factory to ever reach target - a real edge, not a crash.
    r = run_mission(default_mission_scenario(distance_au=5.203))
    assert r.delivered_power_w < 200_000.0
    assert r.reaches_target is False
    assert r.time_to_target_days is None


def test_all_power_to_compute_stalls_manufacturing() -> None:
    # Route 100% of power to thinking: the factory gets nothing and cannot build,
    # while compute throughput is maxed. The stall is reported, not simulated at 0 W.
    r = run_mission(
        default_mission_scenario(
            fraction_manufacturing=0.0,
            fraction_compute=1.0,
            fraction_housekeeping=0.0,
        )
    )
    assert r.manufacturing_w == pytest.approx(0.0)
    assert r.reaches_target is False
    assert r.time_to_target_days is None
    assert r.compute_flops == pytest.approx(r.delivered_power_w * 1e11, rel=1e-9)


def test_launch_payoff_from_closure(baseline: MissionResult) -> None:
    # Vitamins follow from closure: (1 - C) * (target - seed). Leverage = target/launched.
    built = baseline.target_installed_mass_kg - baseline.seed_mass_kg
    expected_vitamins = (1.0 - baseline.closure_ratio) * built
    assert baseline.vitamin_mass_kg == pytest.approx(expected_vitamins, rel=1e-9)
    assert baseline.launched_mass_kg == pytest.approx(
        baseline.seed_mass_kg + baseline.vitamin_mass_kg, rel=1e-9
    )
    assert baseline.mass_leverage == pytest.approx(
        baseline.target_installed_mass_kg / baseline.launched_mass_kg, rel=1e-9
    )
    # Replicating in place is far cheaper than launching the finished installation.
    assert baseline.cost_savings_usd > 0.0
    assert 0.0 < baseline.cost_ratio < 1.0


def test_seed_mass_comes_from_the_factory() -> None:
    # The seam fix: the launch comparison's seed is the factory's own seed, not a
    # second unlinked number.
    s = default_mission_scenario()
    r = run_mission(s)
    assert r.seed_mass_kg == s.factory.replication.seed_mass_kg == 12000.0


def test_leverage_grows_with_target_mass() -> None:
    lo = run_mission(default_mission_scenario(target_installed_mass_kg=100_000.0)).mass_leverage
    hi = run_mission(default_mission_scenario(target_installed_mass_kg=2_000_000.0)).mass_leverage
    assert hi > lo


def test_propellant_fraction_is_physical(baseline: MissionResult) -> None:
    # Tsiolkovsky: for Δv=9400 m/s, Isp=311 s, most of the launch mass is propellant.
    assert 0.0 < baseline.propellant_fraction < 1.0
    assert baseline.propellant_fraction == pytest.approx(0.95414, abs=1e-4)
    assert math.isfinite(baseline.propellant_fraction)
