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
    # ~1.5 Myr to fill a 400-star, 1 star/pc^3 box at N&F's 3e-5c — Myr-scale, as in the paper.
    assert r.t50_years == 895_000.0
    assert r.t90_years == 1_170_000.0
    assert r.t100_years == 1_515_000.0
    assert r.front_radius_pc == pytest.approx(6.281663, abs=1e-4)
    assert len(r.steps) == 521


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
    # Speeds in the resolved regime (hop time >> dt); doubling the speed roughly halves the time.
    slow = simulate_swarm(SwarmParams(n_stars=400, probe_speed_c=3e-5)).t100_years
    fast = simulate_swarm(SwarmParams(n_stars=400, probe_speed_c=6e-5)).t100_years
    assert fast is not None and slow is not None and fast < slow


def test_front_never_exceeds_the_box_diagonal() -> None:
    p = SwarmParams(n_stars=400)
    r = simulate_swarm(p, seed=BASE_SEED)
    diagonal = p.box_side_pc * (3 ** 0.5)
    assert r.front_radius_pc <= diagonal + 1e-9


def test_higher_density_makes_a_smaller_box() -> None:
    sparse = SwarmParams(n_stars=400, density_stars_per_pc3=0.05).box_side_pc
    dense = SwarmParams(n_stars=400, density_stars_per_pc3=0.5).box_side_pc
    assert dense < sparse


def test_powered_default_unchanged_by_slingshot_feature() -> None:
    # Adding slingshots must not perturb the powered baseline (star speeds are drawn in a
    # separate RNG pass after positions). Explicit policy="powered" == the default.
    a = simulate_swarm(SwarmParams(n_stars=300, policy="powered"), seed=BASE_SEED)
    b = simulate_swarm(SwarmParams(n_stars=300), seed=BASE_SEED)
    assert [s.n_settled for s in a.steps] == [s.n_settled for s in b.steps]
    assert a.t100_years == b.t100_years
    assert a.max_probe_speed_km_s == pytest.approx(8.99, abs=0.05)  # = 3e-5 c, the cruise


def test_slingshots_far_outrun_powered_flight() -> None:
    # The paper's headline: slingshot probes accumulate speed from stellar motion and
    # explore far faster than powered flight. (Observed ratio is dt-limited; the true
    # speedup is larger — see REFERENCES.md.)
    powered = simulate_swarm(SwarmParams(n_stars=400, policy="powered"), seed=BASE_SEED)
    sling = simulate_swarm(SwarmParams(n_stars=400, policy="slingshot_nearest"), seed=BASE_SEED)
    assert sling.t100_years is not None and powered.t100_years is not None
    assert sling.t100_years < powered.t100_years / 5  # dramatically faster
    assert sling.max_probe_speed_km_s > 10 * powered.max_probe_speed_km_s  # speed accumulates
    assert sling.final_settled == sling.n_stars  # still fills the field


def test_nearest_slingshot_beats_max_boost_on_time() -> None:
    # N&F's key finding: chasing maximum boost reaches higher speeds but wastes travel,
    # so nearest-neighbour slingshot remains the most time-effective policy.
    nearest = simulate_swarm(SwarmParams(n_stars=400, policy="slingshot_nearest"), seed=BASE_SEED)
    maxboost = simulate_swarm(SwarmParams(n_stars=400, policy="slingshot_maxboost"), seed=BASE_SEED)
    assert nearest.t100_years < maxboost.t100_years  # nearest fills sooner
    assert maxboost.max_probe_speed_km_s > nearest.max_probe_speed_km_s  # but goes faster


def test_boost_self_limits_below_cap() -> None:
    # Eq. 4 falls off for fast probes, and speed_cap_c backstops — no runaway.
    r = simulate_swarm(SwarmParams(n_stars=400, policy="slingshot_maxboost"), seed=BASE_SEED)
    cap_km_s = 0.05 * 299792.458
    assert r.max_probe_speed_km_s <= cap_km_s


def test_slingshot_is_deterministic() -> None:
    a = simulate_swarm(SwarmParams(n_stars=300, policy="slingshot_nearest"), seed=7)
    b = simulate_swarm(SwarmParams(n_stars=300, policy="slingshot_nearest"), seed=7)
    assert [s.n_settled for s in a.steps] == [s.n_settled for s in b.steps]
    assert a.max_probe_speed_km_s == b.max_probe_speed_km_s


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
