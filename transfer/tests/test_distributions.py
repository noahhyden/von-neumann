"""transfer.distributions: every constant here is a measured or definitional quantity, so `Fixed` is correct (not a `[GAP]`)."""

import pytest

from transfer.distributions import (
    BODY_SEMI_MAJOR_AXIS_AU_DIST,
    BODY_SIDEREAL_PERIOD_DAYS_DIST,
)
from transfer.orbits import (
    BODY_SEMI_MAJOR_AXIS_AU,
    BODY_SIDEREAL_PERIOD_DAYS,
)
from vn_core.uq import Fixed


def test_body_dicts_carry_matching_entries():
    assert set(BODY_SEMI_MAJOR_AXIS_AU_DIST.keys()) == set(BODY_SEMI_MAJOR_AXIS_AU.keys())
    assert set(BODY_SIDEREAL_PERIOD_DAYS_DIST.keys()) == set(BODY_SIDEREAL_PERIOD_DAYS.keys())
    for name, dist in BODY_SEMI_MAJOR_AXIS_AU_DIST.items():
        assert isinstance(dist, Fixed)
        assert dist.value == pytest.approx(BODY_SEMI_MAJOR_AXIS_AU[name])
