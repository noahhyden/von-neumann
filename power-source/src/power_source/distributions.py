"""Distributional companions to power-source's sourced numbers.

Issue #35 (UQ) applied to power-source. The key spreads:

- **Solar specific power** spans a documented **4x band** by basis (bare
  blanket vs wing vs full flight system). Pinning the "flight system-level"
  100 W/kg point is the honest deterministic answer; the distributional
  companion is `Uniform(100, 400)` covering system -> wing basis. A
  scenario that pins the basis in a claim should also narrow this.
- **Fission specific power** is sourced as a band (2-7 W/kg across Kilopower
  design points). `Uniform(2.0, 7.0)`.
- **RTG specific power** figures for flown units are each a point value, but
  taken together they span a documented range (~2.4-5.2 W/kg between MMRTG
  and GPHS-RTG). `Uniform(2.4, 5.2)`.
- **Pu-238 production** is explicitly a `(low, high)` tuple in the source
  (0.5-1.5 kg/yr): `Uniform(0.5, 1.5)`.
- **RTG-fission crossover threshold** is sourced as "order-of-magnitude ~1
  kWe". `LogUniform(300, 3000)` captures that order-of-magnitude uncertainty
  while remaining honest that the boundary is not sharp.
- **Fission conversion efficiency** ~30% is a Stirling design number with
  ~+/- 5% real range: `Uniform(0.25, 0.35)`.
- **Fission radiator temperature** 500 K is "representative"; different
  designs pick 450-550 K: `Uniform(450, 550)`.
"""

from __future__ import annotations

from vn_core.uq import Distribution, LogUniform, Uniform

from power_source.power_source import (
    FISSION_CONVERSION_EFFICIENCY,
    FISSION_RADIATOR_TEMP_K,
    FISSION_SPECIFIC_POWER_W_PER_KG,
    GPHS_RTG_SPECIFIC_POWER_W_PER_KG,
    PU238_ANNUAL_PRODUCTION_KG,
    PU238_PER_GPHS_RTG_KG,
    RTG_FISSION_CROSSOVER_WE,
    SOLAR_SPECIFIC_POWER_1AU_W_PER_KG,
)

# Solar specific power (W/kg at 1 AU). REFERENCES.md documents a ~4x band
# depending on basis. The point value pins the conservative system-level end.
SOLAR_SPECIFIC_POWER_1AU_DIST: Distribution = Uniform(low=100.0, high=400.0)

# Fission (Kilopower-class) specific power. REFERENCES.md gives a 2-7 W/kg
# band across design points; Uniform is the honest read.
FISSION_SPECIFIC_POWER_DIST: Distribution = Uniform(low=2.0, high=7.0)

# RTG specific power: MMRTG (~2.4) and GPHS-RTG (~5.2) mark the flown range.
RTG_SPECIFIC_POWER_DIST: Distribution = Uniform(low=2.4, high=5.2)

# Pu-238 mass per GPHS-RTG - a manufactured spec, tightly known.
PU238_PER_GPHS_RTG_DIST: Distribution = Uniform(low=8.0, high=8.2)

# US Pu-238 annual production - source literally gives (0.5, 1.5) kg/yr.
PU238_ANNUAL_PRODUCTION_DIST: Distribution = Uniform(
    low=PU238_ANNUAL_PRODUCTION_KG[0],
    high=PU238_ANNUAL_PRODUCTION_KG[1],
)

# RTG-fission crossover threshold: sourced as "~1 kWe order-of-magnitude".
# LogUniform spreads across the honest order-of-magnitude uncertainty.
RTG_FISSION_CROSSOVER_DIST: Distribution = LogUniform(low=300.0, high=3000.0)

# Kilopower Stirling thermal-to-electric conversion (~30%, real range ~5%).
FISSION_CONVERSION_EFFICIENCY_DIST: Distribution = Uniform(low=0.25, high=0.35)

# Fission radiator temperature (~500 K, design range ~50 K).
FISSION_RADIATOR_TEMP_DIST: Distribution = Uniform(low=450.0, high=550.0)


__all__ = [
    "SOLAR_SPECIFIC_POWER_1AU_DIST",
    "FISSION_SPECIFIC_POWER_DIST",
    "RTG_SPECIFIC_POWER_DIST",
    "PU238_PER_GPHS_RTG_DIST",
    "PU238_ANNUAL_PRODUCTION_DIST",
    "RTG_FISSION_CROSSOVER_DIST",
    "FISSION_CONVERSION_EFFICIENCY_DIST",
    "FISSION_RADIATOR_TEMP_DIST",
]
