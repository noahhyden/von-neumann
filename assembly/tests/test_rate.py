"""assembly validation: the derivation, the sourced band, and the doubling clock.

Anchors: WAAM/LPBF deposition rates, world-class OEE 0.85, and NASA AASM's 100 t/yr
self-copy (=> 274 kg/day). See REFERENCES.md and ROADMAP-PROPOSAL.md.
"""

import pytest

from assembly.rate import (
    AASM_SEED_MASS_KG,
    WORLD_CLASS_OEE,
    WORLD_CLASS_QUALITY,
    aasm_implied_rate_kg_per_day,
    build_rate_band,
    copy_time_days,
    machinery_build_rate_kg_per_day,
)


def test_derivation_is_the_product():
    # 2 arms x 1.5 kg/h x 24 h x 0.8 x 0.99 = 57.02 kg/day.
    r = machinery_build_rate_kg_per_day(
        manipulators=2, deposition_rate_kg_per_h=1.5, duty_cycle=0.8, first_pass_yield=0.99
    )
    assert r == pytest.approx(2 * 1.5 * 24 * 0.8 * 0.99)
    assert r == pytest.approx(57.024, rel=1e-4)


def test_anchor_reproduces_closure_sim_20_kg_per_day():
    # One slow WAAM head (1 kg/h) at world-class OEE (0.85) and quality (0.999)
    # lands on closure-sim's hand-set ~20 kg/day - the number this module retires.
    anchor = machinery_build_rate_kg_per_day(
        manipulators=1,
        deposition_rate_kg_per_h=1.0,
        duty_cycle=WORLD_CLASS_OEE,
        first_pass_yield=WORLD_CLASS_QUALITY,
    )
    assert anchor == pytest.approx(20.4, rel=0.02)
    # And it should be within a couple percent of the literal 20.0 it replaces.
    assert abs(anchor - 20.0) / 20.0 < 0.03


def test_nasa_aasm_implies_274_kg_per_day():
    # 100 tonnes / 365 days.
    assert aasm_implied_rate_kg_per_day() == pytest.approx(273.97, rel=1e-3)
    assert AASM_SEED_MASS_KG == 100_000.0


def test_band_brackets_the_anchor_and_is_over_10x_wide():
    band = build_rate_band()
    # low ~2.9, anchor ~20.4, high ~274 kg/day.
    assert band.low_kg_per_day == pytest.approx(2.877, rel=1e-2)
    assert band.anchor_kg_per_day == pytest.approx(20.4, rel=0.02)
    assert band.high_kg_per_day == pytest.approx(273.97, rel=1e-3)
    assert band.low_kg_per_day < band.anchor_kg_per_day < band.high_kg_per_day
    # The headline: the whole-factory anchor is >10x the single-head one.
    assert band.high_kg_per_day / band.anchor_kg_per_day > 10.0


def test_reproduces_the_582_day_lunar_doubling_clock():
    # Lunar seed: seed_mass 12000 kg, closure ~0.97, build_rate 20 kg/day
    # (closure-sim's lunar_regolith_seed scenario). copy_time = C*seed/rate.
    t = copy_time_days(build_rate_kg_per_day=20.0, seed_mass_kg=12_000.0, closure_ratio=0.97)
    assert t == pytest.approx(582.0, rel=1e-3)


def test_faster_rate_shortens_the_clock_proportionally():
    # The >10x rate disagreement is a >10x clock disagreement: copy_time ~ 1/rate.
    slow = copy_time_days(20.0, 12_000.0, 0.97)
    fast = copy_time_days(aasm_implied_rate_kg_per_day(), 12_000.0, 0.97)
    assert fast < slow
    assert slow / fast == pytest.approx(273.97 / 20.0, rel=1e-3)
    # NASA's rate would cut the ~582-day clock to ~42 days.
    assert fast == pytest.approx(42.5, rel=1e-2)


def test_more_manipulators_scale_linearly():
    one = machinery_build_rate_kg_per_day(1, 1.0, 0.85, 0.999)
    four = machinery_build_rate_kg_per_day(4, 1.0, 0.85, 0.999)
    assert four == pytest.approx(4 * one)


def test_full_closure_costs_more_build_time_than_partial():
    # Higher closure => more mass must be built locally per copy => longer copy time.
    full = copy_time_days(20.0, 12_000.0, 1.0)
    partial = copy_time_days(20.0, 12_000.0, 0.5)
    assert full > partial
    assert full / partial == pytest.approx(2.0, rel=1e-9)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        machinery_build_rate_kg_per_day(0, 1.0, 0.85, 0.999)  # no manipulators
    with pytest.raises(ValueError):
        machinery_build_rate_kg_per_day(1, -1.0, 0.85, 0.999)  # negative rate
    with pytest.raises(ValueError):
        machinery_build_rate_kg_per_day(1, 1.0, 1.5, 0.999)  # duty > 1
    with pytest.raises(ValueError):
        machinery_build_rate_kg_per_day(1, 1.0, 0.85, 0.0)  # zero yield
    with pytest.raises(ValueError):
        copy_time_days(0.0, 12_000.0, 0.97)  # zero rate
    with pytest.raises(ValueError):
        copy_time_days(20.0, 12_000.0, 1.5)  # closure > 1
