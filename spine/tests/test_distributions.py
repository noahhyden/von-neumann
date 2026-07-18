from spine.distributions import DAYS_PER_JULIAN_YEAR_DIST
from spine.run import DAYS_PER_JULIAN_YEAR
from vn_core.uq import Fixed


def test_julian_year_is_definitional():
    assert isinstance(DAYS_PER_JULIAN_YEAR_DIST, Fixed)
    assert DAYS_PER_JULIAN_YEAR_DIST.value == DAYS_PER_JULIAN_YEAR
