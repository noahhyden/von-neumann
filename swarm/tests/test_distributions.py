"""swarm.distributions: sourced spreads for every REFERENCES.md number."""

import math

import pytest

from swarm.distributions import (
    C_PC_PER_YEAR_DIST,
    OFFSPRING_PER_SETTLEMENT_DIST,
    POWERED_CRUISE_SPEED_C_DIST,
    SETTLE_DWELL_YEARS_DIST,
    STELLAR_DENSITY_PER_PC3_DIST,
)
from swarm.models import C_PC_PER_YEAR
from vn_core.uq import Fixed, LogUniform, Uniform, monte_carlo


def test_defined_constants_are_fixed():
    assert isinstance(C_PC_PER_YEAR_DIST, Fixed)
    assert C_PC_PER_YEAR_DIST.value == C_PC_PER_YEAR


def test_cruise_speed_loguniform_covers_the_paper_point_value():
    assert isinstance(POWERED_CRUISE_SPEED_C_DIST, LogUniform)
    assert POWERED_CRUISE_SPEED_C_DIST.low <= 3e-5 <= POWERED_CRUISE_SPEED_C_DIST.high


def test_stellar_density_range_covers_recons_and_paper_choices():
    # RECONS 10-pc: 0.14; N&F: 1.0. Uniform must contain both.
    assert STELLAR_DENSITY_PER_PC3_DIST.low <= 0.14
    assert STELLAR_DENSITY_PER_PC3_DIST.high >= 1.0


def test_scenario_convention_choices_are_fixed():
    assert isinstance(OFFSPRING_PER_SETTLEMENT_DIST, Fixed)
    assert OFFSPRING_PER_SETTLEMENT_DIST.value == 2.0
    assert isinstance(SETTLE_DWELL_YEARS_DIST, Fixed)


def test_settlement_timescale_uq_spans_orders_of_magnitude():
    # Time to reach a 1 pc star at powered cruise: (1 pc) / (speed * c_pc/yr).
    # Under LogUniform on speed, the timescale should also span orders.
    def hop_years(sample):
        return 1.0 / (sample["v_c"] * C_PC_PER_YEAR)

    r = monte_carlo(
        {"v_c": POWERED_CRUISE_SPEED_C_DIST},
        hop_years,
        n=3000,
        seed=181,
    )
    lo, hi = r.error_bar_95
    # Order-of-magnitude spread on speed -> order-of-magnitude spread on time.
    assert hi / lo > 5.0
