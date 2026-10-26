"""Distributional companions to power-source's sourced numbers."""

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

# Solar specific power (W/kg at 1 AU): a documented ~4x band by basis, so Uniform(100, 400) spans flight system-level to wing-level; narrow it if a claim pins the basis.
SOLAR_SPECIFIC_POWER_1AU_DIST: Distribution = Uniform(low=100.0, high=400.0)

# Fission (Kilopower-class) specific power: REFERENCES.md gives a 2-7 W/kg band across design points, read as Uniform.
FISSION_SPECIFIC_POWER_DIST: Distribution = Uniform(low=2.0, high=7.0)

# RTG specific power: MMRTG (~2.4) and GPHS-RTG (~5.2) mark the flown range.
RTG_SPECIFIC_POWER_DIST: Distribution = Uniform(low=2.4, high=5.2)

# Pu-238 mass per GPHS-RTG: a manufactured spec, tightly known (8.1 kg, +/- 0.1 kg band, REFERENCES.md).
PU238_PER_GPHS_RTG_DIST: Distribution = Uniform(low=8.0, high=8.2)

# US Pu-238 annual production - source literally gives (0.5, 1.5) kg/yr.
PU238_ANNUAL_PRODUCTION_DIST: Distribution = Uniform(
    low=PU238_ANNUAL_PRODUCTION_KG[0],
    high=PU238_ANNUAL_PRODUCTION_KG[1],
)

# RTG-fission crossover threshold: sourced as ~1 kWe order-of-magnitude, so LogUniform(300, 3000) spreads across that uncertainty (the boundary is not sharp).
RTG_FISSION_CROSSOVER_DIST: Distribution = LogUniform(low=300.0, high=3000.0)

# Kilopower Stirling thermal-to-electric conversion ~30%, with a +/- 5% design range (REFERENCES.md).
FISSION_CONVERSION_EFFICIENCY_DIST: Distribution = Uniform(low=0.25, high=0.35)

# Fission radiator temperature ~500 K representative, with a +/- 50 K design range (REFERENCES.md).
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
