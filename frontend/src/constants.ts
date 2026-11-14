// Defined physical constants. constants.toml is the single source; regenerate with `make constants`, do not edit by hand.

// SI second is exact (caesium-133 hyperfine); a fixed 86400 s day with no leap seconds, which is what every duration in this repo means [s] https://www.bipm.org/en/publications/si-brochure
export const SECONDS_PER_DAY = 86400.0;

// IAU Julian year, exact by definition; the year the light-year and the IAU parsec are defined against [d] https://www.iau.org/publications/proceedings_rules/units/
export const DAYS_PER_JULIAN_YEAR = 365.25;

// exact by the SI definition of the metre [km/s] https://www.bipm.org/en/publications/si-brochure
export const SPEED_OF_LIGHT_KM_S = 299792.458;

// IAU 2015 Resolution B2 exact parsec, 648000/pi au with the au defined as 1.495978707e11 m [km] https://www.iau.org/static/resolutions/IAU2015_English.pdf
export const KM_PER_PARSEC = 3.0856775814913673e13;

// exact by the 2019 SI redefinition of the kelvin; CODATA agrees by construction [J/K] https://www.bipm.org/en/publications/si-brochure
export const BOLTZMANN_J_PER_K = 1.380649e-23;

export const SECONDS_PER_JULIAN_YEAR = DAYS_PER_JULIAN_YEAR * SECONDS_PER_DAY;
