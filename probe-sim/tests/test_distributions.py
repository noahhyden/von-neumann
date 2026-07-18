"""probe_sim.distributions: the honest distribution for every sourced number.

These are three separable assertions, one per row of REFERENCES.md that has a
distributional companion here: the sourced-spread inputs must carry non-zero
spread, the [GAP] inputs must NOT (they are the honest-null slot, not an
invented Gaussian), and the deterministic inputs must be exactly `Fixed`.
"""

import pytest

from probe_sim.distributions import (
    AU_DISTANCE_DIST,
    REPLICATED_MASS_FRACTION_DIST,
    SOLAR_CELL_EFFICIENCY_DIST,
    SOLAR_CONSTANT_1AU_DIST,
)
from probe_sim.environment import AU_DISTANCE
from vn_core.uq import Fixed


def test_sourced_spread_distributions_carry_real_variance():
    # Two draws far apart in the [0, 1) uniform must land at different values.
    assert SOLAR_CONSTANT_1AU_DIST.quantile(0.05) != SOLAR_CONSTANT_1AU_DIST.quantile(0.95)
    assert SOLAR_CELL_EFFICIENCY_DIST.quantile(0.05) != SOLAR_CELL_EFFICIENCY_DIST.quantile(0.95)


def test_gap_distributions_are_fixed():
    # The [GAP] entries must be Fixed - inventing a spread here would violate §1.
    # When someone lands a source for a spread, they also flip this test's
    # expectation in the same commit. A test failure here says "look at me on
    # purpose".
    assert isinstance(REPLICATED_MASS_FRACTION_DIST, Fixed)
    assert REPLICATED_MASS_FRACTION_DIST.value == 0.70


def test_deterministic_distributions_match_the_point_values():
    for name, dist in AU_DISTANCE_DIST.items():
        assert isinstance(dist, Fixed)
        assert dist.value == pytest.approx(AU_DISTANCE[name])


def test_solar_constant_dist_median_equals_the_point_value():
    from probe_sim.environment import SOLAR_CONSTANT_1AU_W_M2
    assert SOLAR_CONSTANT_1AU_DIST.quantile(0.5) == pytest.approx(SOLAR_CONSTANT_1AU_W_M2)


def test_solar_cell_efficiency_dist_median_is_within_the_landis_bailey_range():
    med = SOLAR_CELL_EFFICIENCY_DIST.quantile(0.5)
    assert 0.28 <= med <= 0.32
