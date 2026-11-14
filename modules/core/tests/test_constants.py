"""The shared defined constants: sources present, literals exact, and spine/SCRUTINY.md C4."""

import struct
import tomllib
from pathlib import Path

import pytest

from vn_core.constants import (
    BOLTZMANN_J_PER_K,
    DAYS_PER_JULIAN_YEAR,
    KM_PER_PARSEC,
    SECONDS_PER_DAY,
    SECONDS_PER_JULIAN_YEAR,
    SPEED_OF_LIGHT_KM_S,
)

TOML = Path(__file__).resolve().parents[1] / "src/vn_core/constants.toml"
TABLE = tomllib.loads(TOML.read_text())


def _bits(x: float) -> bytes:
    return struct.pack(">d", x)


@pytest.mark.parametrize("name", sorted(TABLE), ids=str)
def test_every_constant_carries_a_source_and_a_basis(name: str) -> None:
    # CLAUDE.md section 1 as an executable check rather than a prose promise.
    entry = TABLE[name]
    for field in ("value", "unit", "source", "basis", "verdict"):
        assert entry.get(field), f"{name} has no {field}"
    assert entry["source"].startswith("http"), f"{name} source is not a URL"


@pytest.mark.parametrize("name", sorted(TABLE), ids=str)
def test_every_literal_round_trips_through_float(name: str) -> None:
    literal = TABLE[name]["value"]
    assert isinstance(literal, str), "literals are quoted so the digits match the cited source"
    assert _bits(float(repr(float(literal)))) == _bits(float(literal))


def test_julian_year_is_exactly_365_25_days():
    assert DAYS_PER_JULIAN_YEAR == 365.25


def test_day_is_exactly_86400_si_seconds():
    assert SECONDS_PER_DAY == 86_400.0


def test_c4_both_clocks_trace_to_one_definition():
    # spine/SCRUTINY.md C4: DAYS_PER_JULIAN_YEAR * 86400 must equal the 3.15576e7 s/yr swarm's C_PC_PER_YEAR is built from.
    assert DAYS_PER_JULIAN_YEAR * SECONDS_PER_DAY == 3.15576e7
    assert SECONDS_PER_JULIAN_YEAR == 3.15576e7


@pytest.mark.parametrize(
    ("got", "literal"),
    [
        (SECONDS_PER_JULIAN_YEAR, 3.15576e7),
        (SPEED_OF_LIGHT_KM_S, 299792.458),
        (KM_PER_PARSEC, 3.0856775814913673e13),
        (BOLTZMANN_J_PER_K, 1.380649e-23),
    ],
)
def test_generated_values_are_bit_identical_to_the_literals_they_replaced(got: float, literal: float) -> None:
    # Published results depend on these floats exactly; a value that merely rounds the same is not enough.
    assert _bits(got) == _bits(literal)


def test_swarm_light_speed_is_unchanged_by_sourcing_the_constants():
    # C_PC_PER_YEAR = c * s_per_yr / km_per_pc, in that order; sourcing the inputs must not move a bit.
    literal = 299792.458 * 3.15576e7 / 3.0856775814913673e13
    sourced = SPEED_OF_LIGHT_KM_S * SECONDS_PER_JULIAN_YEAR / KM_PER_PARSEC
    assert _bits(literal) == _bits(sourced)
