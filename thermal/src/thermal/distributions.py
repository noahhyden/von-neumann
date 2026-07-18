"""Distributional companions to thermal's sourced numbers.

Issue #35 (UQ) applied to thermal. The physics constant is exact; the material
and hardware inputs have real bands; the ISS anchor is a flight measurement.

- Stefan-Boltzmann is exact by SI redefinition -> `Fixed`.
- Emissivity of a high-emissivity radiator coating is a documented ~0.8-0.9
  band (white paints / OSRs). `Uniform(0.8, 0.9)` is the honest read.
- Radiator specific mass explicitly has a 3-12 kg/m^2 band (target vs SOA
  vs conservative). `Uniform(3.0, 12.0)`.
- Fission surface power SOA range 5.24-10.95 kg/m^2 (sub-band inside the
  larger 3-12 band). Exposed separately for scenarios that pin the reactor
  case.
- ISS EATCS anchors (heat rejection kW, radiator temp, geometry) are tight
  flight measurements, treated as `Fixed`.
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, Uniform

from thermal.thermal import (
    ISS_HEAT_REJECTION_PER_LOOP_KW,
    ISS_HEAT_REJECTION_TOTAL_KW,
    ISS_PANEL_LENGTH_M,
    ISS_PANEL_WIDTH_M,
    ISS_PANELS_PER_ASSEMBLY,
    ISS_RADIATOR_ASSEMBLY_AREA_M2,
    ISS_RADIATOR_TEMP_K,
    RADIATOR_SPECIFIC_MASS_BAND_KG_M2,
    STEFAN_BOLTZMANN_W_M2_K4,
)

# Physical constant, exact by SI redefinition.
STEFAN_BOLTZMANN_DIST: Distribution = Fixed(STEFAN_BOLTZMANN_W_M2_K4)

# Radiator emissivity: representative high-emissivity coating ~0.8-0.9 band.
EMISSIVITY_DIST: Distribution = Uniform(low=0.8, high=0.9)

# Radiator areal density (kg/m^2): documented 3-12 band across
# target -> conservative-deployable.
RADIATOR_SPECIFIC_MASS_DIST: Distribution = Uniform(
    low=RADIATOR_SPECIFIC_MASS_BAND_KG_M2[0],
    high=RADIATOR_SPECIFIC_MASS_BAND_KG_M2[1],
)

# Fission surface power SOA sub-band, tighter than the target-inclusive range.
RADIATOR_SPECIFIC_MASS_FSP_SOA_DIST: Distribution = Uniform(low=5.24, high=10.95)

# ISS EATCS flight anchors - tight measurements, Fixed.
ISS_HEAT_REJECTION_TOTAL_DIST: Distribution = Fixed(ISS_HEAT_REJECTION_TOTAL_KW)
ISS_HEAT_REJECTION_PER_LOOP_DIST: Distribution = Fixed(ISS_HEAT_REJECTION_PER_LOOP_KW)
# Coolant temperature runs 2-6 C = 275-279 K. Small band, but sourced.
ISS_RADIATOR_TEMP_DIST: Distribution = Uniform(low=275.0, high=279.0)
ISS_RADIATOR_ASSEMBLY_AREA_DIST: Distribution = Fixed(ISS_RADIATOR_ASSEMBLY_AREA_M2)
ISS_PANELS_PER_ASSEMBLY_DIST: Distribution = Fixed(float(ISS_PANELS_PER_ASSEMBLY))
ISS_PANEL_LENGTH_DIST: Distribution = Fixed(ISS_PANEL_LENGTH_M)
ISS_PANEL_WIDTH_DIST: Distribution = Fixed(ISS_PANEL_WIDTH_M)


__all__ = [
    "STEFAN_BOLTZMANN_DIST",
    "EMISSIVITY_DIST",
    "RADIATOR_SPECIFIC_MASS_DIST",
    "RADIATOR_SPECIFIC_MASS_FSP_SOA_DIST",
    "ISS_HEAT_REJECTION_TOTAL_DIST",
    "ISS_HEAT_REJECTION_PER_LOOP_DIST",
    "ISS_RADIATOR_TEMP_DIST",
    "ISS_RADIATOR_ASSEMBLY_AREA_DIST",
    "ISS_PANELS_PER_ASSEMBLY_DIST",
    "ISS_PANEL_LENGTH_DIST",
    "ISS_PANEL_WIDTH_DIST",
]
