"""C4 (SCRUTINY.md): the two scales must be on one clock, or the headline ratio is wrong.

The spine finding is a ratio: a manufacturing dwell (built in DAYS, converted to years with
`DAYS_PER_JULIAN_YEAR`) over a galactic fill time (years, whose light-travel uses swarm's
`C_PC_PER_YEAR`). If those two "years" were different definitions, the ratio would be off by
their quotient with NO crash and NO failing assertion elsewhere - the single most likely way
the headline number could be silently corrupted. This guard makes that mismatch loud.
"""

from __future__ import annotations

import pytest

from swarm.models import C_PC_PER_YEAR

from spine import DAYS_PER_JULIAN_YEAR

# The definitions both modules cite (swarm/models.py header; spine/REFERENCES.md).
SECONDS_PER_DAY = 86_400
SECONDS_PER_JULIAN_YEAR = 3.15576e7  # 1 Julian year
C_KM_S = 299_792.458  # speed of light
PC_KM = 3.0856775814913673e13  # 1 parsec


def test_spine_day_clock_is_the_julian_year() -> None:
    # spine's build-days -> years conversion must be exactly the Julian year (365.25 d),
    # 1 yr = 3.15576e7 s = 86400 s/d x 365.25 d.
    assert DAYS_PER_JULIAN_YEAR == 365.25
    assert DAYS_PER_JULIAN_YEAR * SECONDS_PER_DAY == SECONDS_PER_JULIAN_YEAR


def test_spine_and_swarm_share_one_year_basis() -> None:
    # Reconstruct swarm's speed of light (pc/yr) from spine's day-based year. If spine and
    # swarm used different year definitions, this reconstruction would diverge from the value
    # swarm actually uses - so agreement to machine precision proves both clocks trace to the
    # SAME Julian year, and the dwell/fill ratio is meaningful (SCRUTINY.md C4).
    seconds_per_year = DAYS_PER_JULIAN_YEAR * SECONDS_PER_DAY
    c_reconstructed = C_KM_S * seconds_per_year / PC_KM
    assert c_reconstructed == pytest.approx(C_PC_PER_YEAR, rel=1e-12)
