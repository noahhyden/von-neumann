"""Physical constants shared across modules; every value is cited in core's REFERENCES.md."""

from __future__ import annotations

# SI second is exact, so a day of 86400 s is exact by definition (no leap seconds in this clock).
SECONDS_PER_DAY: float = 86_400.0

# IAU Julian year, the astronomical year basis: exactly 365.25 days.
DAYS_PER_JULIAN_YEAR: float = 365.25

# Derived, not a second literal: 365.25 * 86400 = 3.15576e7 s, bit-identical to writing it out.
SECONDS_PER_JULIAN_YEAR: float = DAYS_PER_JULIAN_YEAR * SECONDS_PER_DAY

__all__ = ["DAYS_PER_JULIAN_YEAR", "SECONDS_PER_DAY", "SECONDS_PER_JULIAN_YEAR"]
