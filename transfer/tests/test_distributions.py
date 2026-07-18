"""transfer.distributions: every constant here is a measured or definitional
quantity, so `Fixed` is correct (not a `[GAP]`)."""

import pytest

from transfer.distributions import (
    AU_M_DIST,
    BODY_SEMI_MAJOR_AXIS_AU_DIST,
    BODY_SIDEREAL_PERIOD_DAYS_DIST,
    GM_SUN_DIST,
    SECONDS_PER_DAY_DIST,
)
from transfer.orbits import (
    AU_M,
    BODY_SEMI_MAJOR_AXIS_AU,
    BODY_SIDEREAL_PERIOD_DAYS,
    GM_SUN_M3_S2,
)
from vn_core.uq import Fixed


def test_definitional_constants_are_fixed():
    for name, dist in [
        ("GM_sun", GM_SUN_DIST),
        ("AU_m", AU_M_DIST),
        ("seconds/day", SECONDS_PER_DAY_DIST),
    ]:
        assert isinstance(dist, Fixed), f"{name} is not Fixed"


def test_body_dicts_carry_matching_entries():
    assert set(BODY_SEMI_MAJOR_AXIS_AU_DIST.keys()) == set(BODY_SEMI_MAJOR_AXIS_AU.keys())
    assert set(BODY_SIDEREAL_PERIOD_DAYS_DIST.keys()) == set(BODY_SIDEREAL_PERIOD_DAYS.keys())
    for name, dist in BODY_SEMI_MAJOR_AXIS_AU_DIST.items():
        assert isinstance(dist, Fixed)
        assert dist.value == pytest.approx(BODY_SEMI_MAJOR_AXIS_AU[name])


def test_gm_sun_value_matches_module():
    assert GM_SUN_DIST.value == GM_SUN_M3_S2


def test_au_m_value_matches_module():
    assert AU_M_DIST.value == AU_M
