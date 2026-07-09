"""End-to-end behavior tests for the deterministic swarm fold (slice 1).

Assert on real numbers and the regimes that matter (CLAUDE.md §2): seeded determinism,
a physical exploration timescale, monotonic settlement, the settlement front never
outrunning the box, and the expected dependence on offspring count and probe speed.
Not "it ran" - what it computed.
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
    # A fixed run - pins the deterministic output so a refactor can't silently change it.
    r = simulate_swarm(SwarmParams(n_stars=400), seed=BASE_SEED)
    assert r.final_settled == 400
    assert r.total_probes_launched == 797
    # ~1.5 Myr to fill a 400-star, 1 star/pc^3 box at N&F's 3e-5c - Myr-scale, as in the paper.
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
    # speedup is larger - see REFERENCES.md.)
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
    # Eq. 4 falls off for fast probes, and speed_cap_c backstops - no runaway.
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


# --- light-speed-limited coordination (FRONTIER #1) --------------------------------------
# Probes decide against a light-delayed BELIEF of what's settled, not global truth, so they
# race for the same star from stale views. "instant" is the perfect-info limit (c→∞), by
# construction bit-identical to the paper's model; "lightspeed" is the novel extension.


def test_instant_mode_is_the_perfect_info_baseline() -> None:
    # "instant" is c→∞ by construction: the light-cone term drops out. It MUST reproduce the
    # default (perfect-info) run bit-for-bit - the keystone reduction. (The whole existing
    # suite already runs under the default "instant", so this pins the explicit form too.)
    explicit = simulate_swarm(SwarmParams(n_stars=300, coordination="instant", policy="slingshot_nearest"), seed=BASE_SEED)
    default = simulate_swarm(SwarmParams(n_stars=300, policy="slingshot_nearest"), seed=BASE_SEED)
    assert [s.n_settled for s in explicit.steps] == [s.n_settled for s in default.steps]
    assert explicit.t100_years == default.t100_years
    assert explicit.wasted_arrivals == default.wasted_arrivals


def test_lightspeed_still_fills_the_connected_field() -> None:
    # Lag slows exploration but doesn't strand a connected field: re-targeting guarantees
    # every star is eventually reached (no spurious Aurora plateau from lag alone).
    r = simulate_swarm(SwarmParams(n_stars=300, coordination="lightspeed", policy="slingshot_nearest"), seed=BASE_SEED)
    assert r.final_settled == r.n_stars == 300
    assert r.t100_years is not None


def test_lightspeed_slows_slingshot_exploration() -> None:
    # The finding: in the fast (slingshot) regime, stale views make probes waste trips, so
    # the field fills LATER than with perfect info. Pinned deterministic numbers.
    inst = simulate_swarm(SwarmParams(n_stars=300, coordination="instant", policy="slingshot_nearest"), seed=BASE_SEED)
    ls = simulate_swarm(SwarmParams(n_stars=300, coordination="lightspeed", policy="slingshot_nearest"), seed=BASE_SEED)
    assert inst.t100_years == 80_000.0
    assert ls.t100_years == 110_000.0  # +37.5% - the cost of no coordination
    assert ls.t100_years > inst.t100_years  # monotonic penalty: lag never speeds it up


def test_lightspeed_adds_wasted_trips() -> None:
    # Wasted arrivals (landing on an already-settled star) are the direct cost of stale info;
    # perfect-info racing is the floor, lag only adds.
    inst = simulate_swarm(SwarmParams(n_stars=300, coordination="instant", policy="slingshot_nearest"), seed=BASE_SEED)
    ls = simulate_swarm(SwarmParams(n_stars=300, coordination="lightspeed", policy="slingshot_nearest"), seed=BASE_SEED)
    assert inst.wasted_arrivals == 1705
    assert ls.wasted_arrivals == 2042
    assert ls.wasted_arrivals > inst.wasted_arrivals


def test_lightspeed_penalty_grows_with_speed() -> None:
    # The scoping insight Λ ≈ v_probe/c: at N&F's powered cruise (3e-5 c) the lag is
    # negligible - the timescale is unchanged; it only bites when probes move fast
    # (slingshots). Light-speed coordination is a slingshot-era phenomenon.
    for pol, expect_penalty in (("powered", False), ("slingshot_nearest", True)):
        inst = simulate_swarm(SwarmParams(n_stars=300, coordination="instant", policy=pol), seed=BASE_SEED)
        ls = simulate_swarm(SwarmParams(n_stars=300, coordination="lightspeed", policy=pol), seed=BASE_SEED)
        if expect_penalty:
            assert ls.t100_years > inst.t100_years
        else:
            assert ls.t100_years == inst.t100_years  # powered: negligible, timescale unchanged


def test_lightspeed_is_deterministic() -> None:
    p = SwarmParams(n_stars=300, coordination="lightspeed", policy="slingshot_nearest")
    a = simulate_swarm(p, seed=7)
    b = simulate_swarm(p, seed=7)
    assert [s.n_settled for s in a.steps] == [s.n_settled for s in b.steps]
    assert a.t100_years == b.t100_years and a.wasted_arrivals == b.wasted_arrivals


def test_lightspeed_offspring_zero_is_a_noop() -> None:
    # With no offspring there are no races to lose; lag changes nothing.
    r = simulate_swarm(SwarmParams(n_stars=250, coordination="lightspeed", offspring_per_settlement=0))
    assert r.final_settled == 1 and r.t100_years is None and r.total_probes_launched == 0


def test_max_retargets_zero_retires_losers() -> None:
    # With no re-aiming allowed, a probe that loses a race dies on the spot (retarget_count
    # == 0) - bounding bounce chains. A connected field with offspring still fills (redundancy).
    r = simulate_swarm(SwarmParams(n_stars=300, coordination="lightspeed", policy="slingshot_nearest", max_retargets=0), seed=BASE_SEED)
    assert r.retarget_count == 0
    assert r.wasted_arrivals > 0  # losers are still counted as wasted
    assert r.final_settled == r.n_stars  # offspring redundancy still fills it


def test_wasted_arrival_counters_are_consistent() -> None:
    r = simulate_swarm(SwarmParams(n_stars=300, coordination="lightspeed", policy="slingshot_nearest"), seed=BASE_SEED)
    assert r.wasted_arrivals >= 0
    assert r.total_arrivals >= r.wasted_arrivals  # wasted is a subset of arrivals
    # every settled star except the homeworld required a (winning) arrival
    assert r.total_arrivals - r.wasted_arrivals >= r.final_settled - 1
    assert r.coordination == "lightspeed"


# --- coverage fractions, effective speed, hop locality (referee-driven observables) ------


def test_coverage_fractions_are_ordered() -> None:
    # t25 <= t50 <= t75 <= t90 <= t99 <= t100: reporting the penalty at earlier, more
    # robust coverage fractions than the fragile t100 tail requires them to be monotone.
    r = simulate_swarm(SwarmParams(n_stars=400, policy="slingshot_nearest"), seed=BASE_SEED)
    ts = [r.t25_years, r.t50_years, r.t75_years, r.t90_years, r.t99_years, r.t100_years]
    assert all(t is not None for t in ts)
    assert all(a <= b for a, b in zip(ts, ts[1:]))


def test_effective_launch_speed_matches_the_regime() -> None:
    # The mean launch speed is the speed probes actually depart at (so Lambda_eff = v/c can
    # be checked). Powered = the 9 km/s cruise; slingshots accumulate far past it.
    powered = simulate_swarm(SwarmParams(n_stars=300, policy="powered"), seed=BASE_SEED)
    sling = simulate_swarm(SwarmParams(n_stars=300, policy="slingshot_nearest"), seed=BASE_SEED)
    assert powered.mean_launch_speed_km_s == pytest.approx(8.99, abs=0.05)  # = 3e-5 c cruise
    assert sling.mean_launch_speed_km_s > 100 * powered.mean_launch_speed_km_s


def test_maxboost_wasted_hops_are_longer_than_nearest() -> None:
    # The mechanism behind the tax: max-boost reaches past its neighbours, so BOTH its
    # winning and its wasted trips are longer than nearest-star's. This is the "hop
    # non-locality" that the penalty tracks (not raw speed).
    near = simulate_swarm(SwarmParams(n_stars=300, coordination="lightspeed", policy="slingshot_nearest"), seed=BASE_SEED)
    maxb = simulate_swarm(SwarmParams(n_stars=300, coordination="lightspeed", policy="slingshot_maxboost"), seed=BASE_SEED)
    assert maxb.mean_wasted_hop_pc > near.mean_wasted_hop_pc
    assert maxb.mean_settle_hop_pc > near.mean_settle_hop_pc
    assert near.mean_wasted_hop_pc > 0.0  # some races are lost under lag


def test_new_observables_do_not_perturb_the_pinned_fold() -> None:
    # The read-only accumulators must not have changed the fold: the pinned baseline holds.
    r = simulate_swarm(SwarmParams(n_stars=400), seed=BASE_SEED)
    assert r.final_settled == 400 and r.t100_years == 1_515_000.0  # test_baseline_regression values


# --- event-driven stepping (dt-independent) ------------------------------------------------
# "event" jumps to the next arrival instead of a fixed dt, so it is the exact continuum limit.
# It is required in the boosted/slingshot regime, where a fixed dt >> hop time over-synchronizes
# launches and inflates the measured coordination tax (see REFERENCES.md).


def test_event_mode_is_deterministic_and_fills() -> None:
    p = SwarmParams(n_stars=300, policy="slingshot_nearest", coordination="lightspeed", stepping="event")
    a = simulate_swarm(p, seed=7)
    b = simulate_swarm(p, seed=7)
    assert [s.n_settled for s in a.steps] == [s.n_settled for s in b.steps]
    assert a.t100_years == b.t100_years
    assert a.final_settled == a.n_stars == 300  # a connected field still fills


def test_event_mode_resolves_a_shorter_timescale_than_coarse_fixed_dt() -> None:
    # Boosted hops are far shorter than dt=5000 yr, so the fixed-step run quantizes each hop
    # up to a whole step and overstates the fill time; the event fold gives the true, shorter one.
    fixed = simulate_swarm(SwarmParams(n_stars=300, policy="slingshot_nearest", stepping="fixed"), seed=BASE_SEED)
    event = simulate_swarm(SwarmParams(n_stars=300, policy="slingshot_nearest", stepping="event"), seed=BASE_SEED)
    assert event.t100_years is not None and fixed.t100_years is not None
    assert event.t100_years < fixed.t100_years / 2  # the coarse timestep inflates it several-fold


def test_event_mode_penalty_is_far_smaller_than_coarse_dt_penalty() -> None:
    # The central correction: the light-speed coordination penalty measured with the coarse
    # fixed dt is largely a discretization artifact. At the resolved (event) limit it nearly
    # vanishes for a 300-star field, well below the inflated coarse-dt figure.
    def pen(stepping: str) -> float:
        i = simulate_swarm(SwarmParams(n_stars=300, policy="slingshot_nearest", coordination="instant", stepping=stepping), seed=BASE_SEED)
        l = simulate_swarm(SwarmParams(n_stars=300, policy="slingshot_nearest", coordination="lightspeed", stepping=stepping), seed=BASE_SEED)
        return (l.t100_years - i.t100_years) / i.t100_years * 100.0
    coarse = pen("fixed")   # dt=5000: the inflated ~37% single-seed figure
    resolved = pen("event")  # dt -> 0: near zero
    assert coarse > 25.0
    assert abs(resolved) < 10.0
    assert resolved < coarse  # resolving the timestep shrinks the apparent tax
