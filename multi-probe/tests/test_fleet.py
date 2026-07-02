"""End-to-end behavior tests for the deterministic multi-probe fold.

These assert on real numbers and the regimes that matter (CLAUDE.md §2): sourced
params, seeded determinism, geometric growth near the Sun, the two emergent ceilings
(vitamin pool = electronics wall; 1/d² power = spatial wall), mass balance, dispersal,
and the fleet cap. Not "it ran" — what it computed.
"""

from __future__ import annotations

import pathlib

import closure_sim
import pytest
from closure_sim.scenarios import load_factory

from multi_probe import FleetParams, params_from_factory, simulate_fleet
from multi_probe.fleet import _build_rate_kg_per_day, initial_state, step

_ROOT = pathlib.Path(closure_sim.__file__).resolve().parents[2]


@pytest.fixture
def factory():
    return load_factory(_ROOT / "scenarios" / "lunar_regolith_seed.yaml")


@pytest.fixture
def params(factory) -> FleetParams:
    return params_from_factory(factory)


def vitamins_per_child(p: FleetParams) -> float:
    return (1.0 - p.closure_ratio) * p.seed_mass_kg


def local_per_child(p: FleetParams) -> float:
    return p.closure_ratio * p.seed_mass_kg


def test_params_are_sourced_from_the_factory(params: FleetParams) -> None:
    # seed mass and machinery rate come straight from the scenario; closure/e_local
    # are closure-sim's own derived numbers.
    assert params.seed_mass_kg == 12000.0
    assert params.local_build_rate_kg_per_day == 20.0
    assert params.closure_ratio == pytest.approx(0.970833, abs=1e-5)
    assert params.e_local_kwh_per_kg == pytest.approx(18.112, abs=1e-2)


def test_build_rate_is_machinery_limited_near_sun_energy_limited_far(params: FleetParams) -> None:
    # Near the Sun the machinery binds (can't use all the power); far out 1/d² power
    # binds. The crossover for this scenario is ~13.6 AU.
    assert _build_rate_kg_per_day(params, 1.0) == pytest.approx(params.local_build_rate_kg_per_day)
    assert _build_rate_kg_per_day(params, 5.203) == pytest.approx(params.local_build_rate_kg_per_day)
    far = _build_rate_kg_per_day(params, 30.0)
    assert far < params.local_build_rate_kg_per_day
    # Beyond the crossover the rate is the energy cap ∝ 1/d²: doubling distance quarters it.
    assert _build_rate_kg_per_day(params, 20.0) / _build_rate_kg_per_day(params, 40.0) == pytest.approx(4.0, rel=1e-9)


def test_seeded_run_is_reproducible_with_jitter(factory) -> None:
    # Same seed + jitter → bit-identical trajectory (the whole point of threading the RNG).
    p = params_from_factory(factory, transit_jitter_frac=0.3)
    a = simulate_fleet(p, seed=12345, duration_days=3650)
    b = simulate_fleet(p, seed=12345, duration_days=3650)
    assert [s.population for s in a.steps] == [s.population for s in b.steps]
    assert a.final_population == b.final_population
    assert a.max_distance_au == b.max_distance_au


def test_no_jitter_run_is_independent_of_seed(factory) -> None:
    # With jitter = 0 the RNG is never consumed, so the run must not depend on the seed.
    p = params_from_factory(factory)  # jitter defaults to 0
    a = simulate_fleet(p, seed=1, duration_days=3650)
    b = simulate_fleet(p, seed=999_999, duration_days=3650)
    assert [s.population for s in a.steps] == [s.population for s in b.steps]


def test_geometric_growth_near_sun(params: FleetParams) -> None:
    # One probe at 1 AU builds a child in ~local/rate = 11650/20 ≈ 582 days, then the
    # fleet doubles on roughly that cadence until a ceiling.
    r = simulate_fleet(params, duration_days=14600, dt_days=1.0)
    expected_first_child_day = local_per_child(params) / params.local_build_rate_kg_per_day
    assert r.doubling_time_days == pytest.approx(expected_first_child_day, abs=2.0)
    # population is monotonic non-decreasing and actually grows past the seed count.
    pops = [s.population for s in r.steps]
    assert all(b >= a for a, b in zip(pops, pops[1:]))
    assert r.final_population > 1


def test_fleet_cap_is_respected(factory) -> None:
    p = params_from_factory(factory, max_probes=16)
    r = simulate_fleet(p, duration_days=14600)
    assert r.final_population <= 16
    assert r.binding.cap_limited is True


def test_spatial_power_wall_far_from_sun(factory) -> None:
    # Start the fleet at 30 AU: sunlight is ~1/900 of Earth's, build rate collapses, so
    # a probe barely (or never) copies within the run — far fewer than near the Sun.
    near = simulate_fleet(params_from_factory(factory, max_probes=256), duration_days=3650)
    far = simulate_fleet(params_from_factory(factory, start_distance_au=30.0, max_probes=256), duration_days=3650)
    assert far.final_population < near.final_population
    assert far.binding.power_limited is True
    assert near.binding.power_limited is False


def test_electronics_wall_caps_the_fleet_via_vitamin_pool(params: FleetParams, factory) -> None:
    # A finite vitamin pool is the electronics wall re-instantiated at fleet scale:
    # exactly floor(pool / vitamins_per_child) children can ever be built.
    vpc = vitamins_per_child(params)
    k = 5
    pool = k * vpc + 0.5  # room for exactly k children
    p = params_from_factory(factory, vitamin_pool_kg=pool, max_probes=256)
    r = simulate_fleet(p, duration_days=14600)
    assert r.total_children == k
    assert r.binding.vitamin_limited is True
    # mass balance: consumed exactly k children worth, pool never negative.
    assert r.vitamins_consumed_kg == pytest.approx(k * vpc, rel=1e-9)
    assert r.vitamins_remaining_kg >= 0.0
    assert min(s.vitamin_pool_kg for s in r.steps) >= 0.0


def test_mass_balance_pool_conserved(params: FleetParams) -> None:
    r = simulate_fleet(params, duration_days=7300)
    assert r.vitamins_consumed_kg + r.vitamins_remaining_kg == pytest.approx(params.vitamin_pool_kg, rel=1e-9)
    assert r.vitamins_consumed_kg == pytest.approx(r.total_children * vitamins_per_child(params), rel=1e-9)


def test_children_disperse_outward_and_clamp(factory) -> None:
    p = params_from_factory(factory, dispersal_factor=1.5, max_distance_au=10.0, max_probes=256)
    r = simulate_fleet(p, duration_days=14600)
    # once there are children, the farthest probe is beyond the 1 AU start, never past the clamp.
    assert r.max_distance_au > 1.0
    assert r.max_distance_au <= 10.0 + 1e-9


def test_single_step_is_pure(params: FleetParams) -> None:
    # step() must not mutate its input state (needed for exact speculate / replay).
    s0 = initial_state(params, seed=7)
    before_day, before_pop = s0.day, len(s0.probes)
    _ = step(s0, params, 1.0)
    assert s0.day == before_day
    assert len(s0.probes) == before_pop
