"""The shared time basis: one definition, and the identity spine/SCRUTINY.md C4 asks for."""

import struct

from vn_core.constants import DAYS_PER_JULIAN_YEAR, SECONDS_PER_DAY, SECONDS_PER_JULIAN_YEAR


def _bits(x: float) -> bytes:
    return struct.pack(">d", x)


def test_julian_year_is_exactly_365_25_days():
    assert DAYS_PER_JULIAN_YEAR == 365.25


def test_day_is_exactly_86400_si_seconds():
    assert SECONDS_PER_DAY == 86_400.0


def test_c4_both_clocks_trace_to_one_definition():
    # spine/SCRUTINY.md C4: DAYS_PER_JULIAN_YEAR * 86400 must equal the 3.15576e7 s/yr swarm's C_PC_PER_YEAR is built from.
    assert DAYS_PER_JULIAN_YEAR * SECONDS_PER_DAY == 3.15576e7
    assert SECONDS_PER_JULIAN_YEAR == 3.15576e7


def test_derived_year_is_bit_identical_to_the_literal():
    # swarm's published results depend on this float exactly; a derived value that merely rounds the same is not enough.
    assert _bits(SECONDS_PER_JULIAN_YEAR) == _bits(3.15576e7)


def test_swarm_light_speed_is_unchanged_by_deriving_the_year():
    # C_PC_PER_YEAR = c_km_s * s_per_yr / km_per_pc; deriving s_per_yr must not move a single bit.
    literal = 299792.458 * 3.15576e7 / 3.0856775814913673e13
    derived = 299792.458 * SECONDS_PER_JULIAN_YEAR / 3.0856775814913673e13
    assert _bits(literal) == _bits(derived)
