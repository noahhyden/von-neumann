"""End-to-end behavior tests for the deterministic swarm fold (slice 1).

Assert on real numbers and the regimes that matter (CLAUDE.md §2): seeded determinism,
a physical exploration timescale, monotonic settlement, the settlement front never
outrunning the box, and the expected dependence on offspring count and probe speed.
Not "it ran" — what it computed.
"""

from __future__ import annotations

import pytest

from swarm import C_PC_PER_YEAR, SwarmParams, simulate_swarm
from swarm.sim import initial_state, step

SEED = 0x9E3739B9  # a fixed seed for the regression baseline
BASE_SEED = 0x9E3779B9


def test_light_speed_constant_is_physical() -> None:
    # c ≈ 0.3066 pc/yr; the fiducial cruise speed is 0.1c.
    assert C_PC_PER_YEAR == pytest.approx(0.3066, abs=1e-3)


def test_baseline_regression() -> None:
    # A fixed run — pins the deterministic output so a refactor can't silently change it.
    r = simulate_swarm(SwarmParams(n_stars=400), seed=BASE_SEED)
    assert r.final_settled == 400
    assert r.total_probes_launched == 797
    assert r.t50_years == 625.0
    assert r.t90_years == 825.0
    assert r.t100_years == 1025.0
    assert r.front_radius_pc == pytest.approx(12.097583, abs=1e-4)
    assert len(r.steps) == 64


def test_same_seed_is_bit_identical() -> None:
    p = SwarmParams(n_stars=300)
    a = simulate_swarm(p, seed=123)
    b = simulate_swarm(p, seed=123)
    assert [s.n_settled for s in a.steps] == [s.n_settled for s in b.steps]
    assert a.t100_years == b.t100_years
    assert a.front_radius_pc == b.front_radius_pc


def test_different_seed_changes_the_field_but_still_fills() -> None:
    p = SwarmParams(n_stars=300)
    a = simulate_swarm(p, seed=1)
    b = simulate_swarm(p, seed=2)
    assert [s.n_settled for s in a.steps] != [s.n_settled for s in b.steps]
    assert a.final_settled == b.final_settled == 300  # a connected field always fills


def test_whole_reachable_field_fills_with_offspring() -> None:
    r = simulate_swarm(SwarmParams(n_stars=250, offspring_per_settlement=2))
    assert r.final_settled == r.n_stars
    assert r.t100_years is not None


def test_no_offspring_settles_only_the_homeworld() -> None:
    r = simulate_swarm(SwarmParams(n_stars=250, offspring_per_settlement=0))
    assert r.final_settled == 1
    assert r.t100_years is None  # never reaches 100%
    assert r.total_probes_launched == 0


def test_settlement_and_front_are_monotonic() -> None:
    r = simulate_swarm(SwarmParams(n_stars=300), seed=7)
    pops = [s.n_settled for s in r.steps]
    fronts = [s.front_radius_pc for s in r.steps]
    assert all(b >= a for a, b in zip(pops, pops[1:]))  # stars are never un-settled
    assert all(b >= a - 1e-9 for a, b in zip(fronts, fronts[1:]))  # the front only expands
    assert pops[0] == 1 and fronts[0] == 0.0  # starts as one homeworld at the origin


def test_thresholds_are_ordered() -> None:
    r = simulate_swarm(SwarmParams(n_stars=400))
    assert r.t50_years is not None and r.t90_years is not None and r.t100_years is not None
    assert r.t50_years <= r.t90_years <= r.t100_years


def test_more_offspring_settles_faster() -> None:
    times = [simulate_swarm(SwarmParams(n_stars=400, offspring_per_settlement=o)).t100_years for o in (1, 2, 4)]
    assert times[0] > times[1] > times[2]  # strictly faster with more offspring


def test_faster_probes_settle_faster() -> None:
    slow = simulate_swarm(SwarmParams(n_stars=400, probe_speed_c=0.1)).t100_years
    fast = simulate_swarm(SwarmParams(n_stars=400, probe_speed_c=0.2)).t100_years
    assert fast < slow


def test_front_never_exceeds_the_box_diagonal() -> None:
    p = SwarmParams(n_stars=400)
    r = simulate_swarm(p, seed=BASE_SEED)
    diagonal = p.box_side_pc * (3 ** 0.5)
    assert r.front_radius_pc <= diagonal + 1e-9


def test_higher_density_makes_a_smaller_box() -> None:
    sparse = SwarmParams(n_stars=400, density_stars_per_pc3=0.05).box_side_pc
    dense = SwarmParams(n_stars=400, density_stars_per_pc3=0.5).box_side_pc
    assert dense < sparse


def test_step_settles_only_at_or_after_arrival() -> None:
    # No star (other than the homeworld) is settled before a probe could have reached it.
    p = SwarmParams(n_stars=200)
    s = initial_state(p, seed=5)
    assert s.settled_year[s.origin] == 0.0
    assert s.n_settled() == 1
    # advancing one step settles only stars whose probes have arrived by then.
    step(s, p)
    for i, yr in enumerate(s.settled_year):
        if yr >= 0.0 and i != s.origin:
            assert yr <= s.year
