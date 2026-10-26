"""swarm.distributions: sourced spreads for every REFERENCES.md number."""

import math

import pytest

from swarm.distributions import (
    POWERED_CRUISE_SPEED_C_DIST,
    STELLAR_DENSITY_PER_PC3_DIST,
)
from swarm.models import C_PC_PER_YEAR
from vn_core.uq import LogUniform, Uniform, monte_carlo


def test_cruise_speed_loguniform_covers_the_paper_point_value():
    assert isinstance(POWERED_CRUISE_SPEED_C_DIST, LogUniform)
    assert POWERED_CRUISE_SPEED_C_DIST.low <= 3e-5 <= POWERED_CRUISE_SPEED_C_DIST.high


def test_stellar_density_range_covers_recons_and_paper_choices():
    # RECONS 10-pc: 0.14; N&F: 1.0. Uniform must contain both.
    assert STELLAR_DENSITY_PER_PC3_DIST.low <= 0.14
    assert STELLAR_DENSITY_PER_PC3_DIST.high >= 1.0


def test_settlement_timescale_uq_spans_orders_of_magnitude():
    # Time to reach a 1 pc star at powered cruise: (1 pc) / (speed * c_pc/yr).
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
