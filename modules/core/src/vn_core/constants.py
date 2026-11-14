"""Defined physical constants. constants.toml is the single source; regenerate with `make constants`, do not edit by hand."""

from __future__ import annotations


# SI second is exact (caesium-133 hyperfine); a fixed 86400 s day with no leap seconds, which is what every duration in this repo means [s] https://www.bipm.org/en/publications/si-brochure
SECONDS_PER_DAY: float = 86400.0

# IAU Julian year, exact by definition; the year the light-year and the IAU parsec are defined against [d] https://www.iau.org/publications/proceedings_rules/units/
DAYS_PER_JULIAN_YEAR: float = 365.25

# exact by the SI definition of the metre [km/s] https://www.bipm.org/en/publications/si-brochure
SPEED_OF_LIGHT_KM_S: float = 299792.458

# IAU 2015 Resolution B2 exact parsec, 648000/pi au with the au defined as 1.495978707e11 m [km] https://www.iau.org/static/resolutions/IAU2015_English.pdf
KM_PER_PARSEC: float = 3.0856775814913673e13

# exact by the 2019 SI redefinition of the kelvin; CODATA agrees by construction [J/K] https://www.bipm.org/en/publications/si-brochure
BOLTZMANN_J_PER_K: float = 1.380649e-23

SECONDS_PER_JULIAN_YEAR: float = DAYS_PER_JULIAN_YEAR * SECONDS_PER_DAY

__all__ = ['BOLTZMANN_J_PER_K', 'DAYS_PER_JULIAN_YEAR', 'KM_PER_PARSEC', 'SECONDS_PER_DAY', 'SECONDS_PER_JULIAN_YEAR', 'SPEED_OF_LIGHT_KM_S']
