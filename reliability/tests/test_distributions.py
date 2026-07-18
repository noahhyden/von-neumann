"""reliability.distributions: sourced spreads for every REFERENCES.md band."""

import math

import pytest

from reliability.degradation import (
    ARRAY_DEGRADATION_BAND_PER_YR,
    ARRAY_DEGRADATION_PER_YR,
    array_power_fraction,
)
from reliability.distributions import (
    ARRAY_DEGRADATION_DIST,
    SATELLITE_HAZARD_PER_DAY_DIST,
)
from reliability.mortality import SATELLITE_HAZARD_PER_DAY
from vn_core.uq import LogUniform, Uniform, monte_carlo


def test_array_degradation_band_matches_source():
    assert ARRAY_DEGRADATION_DIST.low == ARRAY_DEGRADATION_BAND_PER_YR[0]
    assert ARRAY_DEGRADATION_DIST.high == ARRAY_DEGRADATION_BAND_PER_YR[1]


def test_satellite_hazard_is_loguniform_due_to_orders_of_magnitude_spread():
    assert isinstance(SATELLITE_HAZARD_PER_DAY_DIST, LogUniform)
    # Point value must sit inside the LogUniform range.
    assert SATELLITE_HAZARD_PER_DAY_DIST.low < SATELLITE_HAZARD_PER_DAY < SATELLITE_HAZARD_PER_DAY_DIST.high


def test_array_power_fraction_uq_shows_ten_year_spread():
    # Under UQ over the 0.002-0.010 band, what is the array power left after
    # 10 years? Point value at 0.003 gives ~97% left; the wider band pulls
    # this down to ~90% at the high end.
    def frac_at_10yr(sample):
        return array_power_fraction(years=10.0, degradation_per_yr=sample["deg"])

    r = monte_carlo({"deg": ARRAY_DEGRADATION_DIST}, frac_at_10yr, n=3000, seed=167)
    lo, hi = r.error_bar_95
    # The 90% CI should span at least 5 percentage points.
    assert (hi - lo) > 0.05
    # And every draw must sit inside [0, 1].
    assert 0.0 < r.q05 and r.q95 < 1.0
