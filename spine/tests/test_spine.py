"""End-to-end validation for the cross-scale spine (CLAUDE.md §2: assert on behavior).

These check the *seam*, not just that code runs: that one factory drives every scale,
that the swarm dwell is genuinely derived from the factory (not a re-guessed number), that
the derived copy cadence really is the fleet's doubling clock, and that the same dwell is a
negligible - but resolvable, and policy-ordered - tax on galactic exploration.
"""

from __future__ import annotations

import pytest

from closure_sim.closure import compute_closure
from multi_probe.fleet import params_from_factory, time_to_build_one_copy_days

from spine import (
    DAYS_PER_JULIAN_YEAR,
    SpineScenario,
    derive_settle_time_years,
    measure_dwell_tax,
    run_spine,
)


@pytest.fixture
def scenario() -> SpineScenario:
    return SpineScenario.default()


def test_one_factory_drives_every_scale(scenario: SpineScenario) -> None:
    # The closure ratio the spine reports IS the shared factory's closure ratio, and the
    # fleet params derived for scale 2 carry the exact same number. One source, three scales.
    r = run_spine(scenario)
    factory_closure = compute_closure(scenario.factory).closure_ratio
    fleet_closure = params_from_factory(scenario.factory).closure_ratio
    assert r.closure_ratio == pytest.approx(factory_closure)
    assert r.closure_ratio == pytest.approx(fleet_closure)
    assert r.closure_ratio == pytest.approx(0.970833, abs=1e-5)


def test_settle_time_is_derived_from_the_factory_not_guessed(scenario: SpineScenario) -> None:
    # The swarm dwell (once an ungrounded [ESTIMATE] of 0.0) equals the fleet's 1-AU copy
    # time in years, exactly - it is factory physics re-used, with no free parameter.
    fp = params_from_factory(scenario.factory)
    copy_days = time_to_build_one_copy_days(fp, 1.0)
    expected_years = copy_days / DAYS_PER_JULIAN_YEAR
    assert derive_settle_time_years(scenario) == pytest.approx(expected_years)
    r = run_spine(scenario)
    assert r.copy_time_days == pytest.approx(copy_days)
    assert r.settle_time_years == pytest.approx(expected_years)
    assert r.settle_time_years > 0.0  # a real dwell, not the old zero


def test_derived_dwell_depends_only_on_the_factory(scenario: SpineScenario) -> None:
    # It is a property of the factory, so the galaxy knobs (policy, star count) must not
    # change it. Same factory -> same dwell.
    powered = derive_settle_time_years(SpineScenario.default(policy="powered", n_stars=800))
    sling = derive_settle_time_years(SpineScenario.default(policy="slingshot_nearest", n_stars=1600))
    assert powered == pytest.approx(sling)


def test_the_copy_cadence_is_the_fleets_doubling_clock(scenario: SpineScenario) -> None:
    # The leg that makes the seam meaningful: at fleet scale (transit is days) the factory
    # build time IS the clock - the first doubling lands within a timestep of the copy time.
    r = run_spine(scenario)
    assert r.fleet_doubling_days is not None
    assert r.fleet_doubling_days == pytest.approx(r.copy_time_days, abs=2.0)
    assert r.fleet_final_population > 1


def test_dwell_is_negligible_at_galactic_scale_for_powered(scenario: SpineScenario) -> None:
    # The cross-scale punchline: the same ~1.6 yr dwell is a vanishing fraction of a
    # multi-million-year powered fill - interstellar transit dominates by orders of magnitude.
    r = run_spine(scenario)  # default policy = powered
    assert r.swarm_t100_years is not None and r.swarm_t100_years > 1e5
    assert r.final_settled == r.n_stars  # a connected field still fills to 100%
    assert r.dwell_fraction_of_t100 is not None
    assert r.dwell_fraction_of_t100 < 1e-5


def test_dwell_tax_is_small_positive_and_ordered_by_speed(scenario: SpineScenario) -> None:
    # Measured A/B (fine dt, small field): turning the derived dwell on can only slow the
    # fill, and for fast slingshot probes it costs a small - but real and resolvable -
    # fraction of the exploration time.
    tx = measure_dwell_tax(SpineScenario.default(policy="slingshot_nearest"))
    assert tx.t100_with_dwell is not None and tx.t100_zero_dwell is not None
    assert tx.t100_with_dwell >= tx.t100_zero_dwell  # dwell never speeds exploration up
    assert tx.tax_fraction is not None
    assert 0.0 < tx.tax_fraction < 0.01  # real, positive, and tiny

    # Ordered by speed: the powered dwell fraction (from the coarse full run) is far below
    # the slingshot tax - faster transit shrinks the hop the dwell competes with, so the
    # faster policy pays the larger (still negligible) tax.
    powered_frac = run_spine(SpineScenario.default(policy="powered")).dwell_fraction_of_t100
    assert powered_frac is not None
    assert powered_frac < tx.tax_fraction


def test_dwell_tax_is_deterministic() -> None:
    # Seeded folds: the measured tax must be reproducible bit-for-bit.
    a = measure_dwell_tax(SpineScenario.default(policy="slingshot_nearest"))
    b = measure_dwell_tax(SpineScenario.default(policy="slingshot_nearest"))
    assert a.tax_fraction == b.tax_fraction
    assert a.t100_with_dwell == b.t100_with_dwell


def test_no_offspring_settles_only_the_homeworld() -> None:
    # Boundary: with zero offspring the front cannot spread - only the homeworld is settled
    # and there is no 100% time (the field never fills).
    r = run_spine(SpineScenario.default(offspring_per_settlement=0))
    assert r.final_settled == 1
    assert r.swarm_t100_years is None
    assert r.dwell_fraction_of_t100 is None


def test_run_spine_is_deterministic(scenario: SpineScenario) -> None:
    a = run_spine(scenario)
    b = run_spine(scenario)
    assert a.swarm_t100_years == b.swarm_t100_years
    assert a.settle_time_years == b.settle_time_years
    assert a.fleet_final_population == b.fleet_final_population


def test_verdict_is_plain_ascii(scenario: SpineScenario) -> None:
    # Repo typography rule (CLAUDE.md §5): no em-dash, no emoji in any string we emit.
    v = run_spine(scenario).verdict
    assert v and chr(0x2014) not in v  # U+2014 em-dash is banned repo-wide
    assert all(ord(c) < 0x2190 or c in "≈≥≤" for c in v)
