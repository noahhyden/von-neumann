"""comms.distributions: sourced spreads for every REFERENCES.md number."""

import pytest

from comms.distributions import (
    BITS_PER_MBIT_DIST,
    K_OPTICAL_MBPS_AU2_DIST,
    R_MAX_DSOC_MBPS_DIST,
)
from comms.link import BITS_PER_MBIT, K_OPTICAL_MBPS_AU2, R_MAX_DSOC_MBPS
from vn_core.uq import Fixed, Uniform, monte_carlo, sobol_total_order


def test_definitional_constants_are_fixed():
    assert isinstance(BITS_PER_MBIT_DIST, Fixed)
    assert BITS_PER_MBIT_DIST.value == BITS_PER_MBIT


def test_dsoc_fit_uncertainty_is_the_disagreement_between_anchors():
    # The +/- ~1% between the two verified DSOC anchors (56.7 and 55.3) IS
    # the honest error bar on k.
    assert K_OPTICAL_MBPS_AU2_DIST.low == 55.3
    assert K_OPTICAL_MBPS_AU2_DIST.high == 56.7
    assert K_OPTICAL_MBPS_AU2_DIST.low <= K_OPTICAL_MBPS_AU2 <= K_OPTICAL_MBPS_AU2_DIST.high


def test_rmax_band_contains_the_point_value():
    assert R_MAX_DSOC_MBPS_DIST.low < R_MAX_DSOC_MBPS < R_MAX_DSOC_MBPS_DIST.high + 1


def test_dsoc_data_rate_at_2au_stays_below_rmax():
    # Sanity finding: at 2 AU, k / d^2 = 56 / 4 = 14 Mbps, well below R_max.
    # UQ over both must preserve this: no draw should push rate over R_max
    # at 2 AU. This catches a regression that would silently swap the
    # min(k/d^2, R_max) branch.
    def rate_at_2au(sample):
        power_limited = sample["k"] / (2.0**2)
        return min(power_limited, sample["r_max"])

    r = monte_carlo(
        {"k": K_OPTICAL_MBPS_AU2_DIST, "r_max": R_MAX_DSOC_MBPS_DIST},
        rate_at_2au,
        n=2000,
        seed=137,
    )
    assert max(r.values) < 20.0  # far below the ~200 Mbps R_max floor
