"""Distributional companions to shielding's sourced numbers.

Issue #35 (UQ). Sourced spreads:

- GCR deep-space dose ~1.8 mSv/day (MSL RAD). The literature spread across
  cruise conditions is 1.5-2.1 mSv/day. Uniform.
- Material densities (Ti, Al, regolith) are tightly known but regolith
  varies 1.5-1.8 g/cm^3 with compaction. Ti / Al Fixed; regolith Uniform.
- Juno vault attenuation factor ~800x is the design target; real measured
  attenuation runs 500-1000x depending on interior geometry. Uniform.
- Vault masses are flight measurements -> Fixed.
- GCR dose minimum areal density is an HZETRN design point, treated as
  Uniform over the documented 15-25 g/cm^2 band.
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, Uniform

from shielding.radenv import (
    ALUMINIUM_DENSITY_G_CM3,
    EUROPA_CLIPPER_VAULT_MASS_KG,
    GCR_DEEP_SPACE_DOSE_MSV_PER_DAY,
    GCR_DOSE_MIN_AREAL_DENSITY_G_CM2,
    JUNO_ANTICIPATED_TID_RAD,
    JUNO_VAULT_ATTENUATION_FACTOR,
    JUNO_VAULT_MASS_KG,
    LUNAR_REGOLITH_DENSITY_G_CM3,
    TITANIUM_DENSITY_G_CM3,
)

GCR_DEEP_SPACE_DOSE_DIST: Distribution = Uniform(low=1.5, high=2.1)
GCR_DOSE_MIN_AREAL_DENSITY_DIST: Distribution = Uniform(low=15.0, high=25.0)
JUNO_ANTICIPATED_TID_DIST: Distribution = Fixed(JUNO_ANTICIPATED_TID_RAD)
JUNO_VAULT_ATTENUATION_DIST: Distribution = Uniform(low=500.0, high=1000.0)
TITANIUM_DENSITY_DIST: Distribution = Fixed(TITANIUM_DENSITY_G_CM3)
ALUMINIUM_DENSITY_DIST: Distribution = Fixed(ALUMINIUM_DENSITY_G_CM3)
LUNAR_REGOLITH_DENSITY_DIST: Distribution = Uniform(low=1.5, high=1.8)
JUNO_VAULT_MASS_DIST: Distribution = Fixed(JUNO_VAULT_MASS_KG)
EUROPA_CLIPPER_VAULT_MASS_DIST: Distribution = Fixed(EUROPA_CLIPPER_VAULT_MASS_KG)


__all__ = [
    "GCR_DEEP_SPACE_DOSE_DIST",
    "GCR_DOSE_MIN_AREAL_DENSITY_DIST",
    "JUNO_ANTICIPATED_TID_DIST",
    "JUNO_VAULT_ATTENUATION_DIST",
    "TITANIUM_DENSITY_DIST",
    "ALUMINIUM_DENSITY_DIST",
    "LUNAR_REGOLITH_DENSITY_DIST",
    "JUNO_VAULT_MASS_DIST",
    "EUROPA_CLIPPER_VAULT_MASS_DIST",
]
