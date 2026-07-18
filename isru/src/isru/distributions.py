"""Distributional companions to isru's sourced numbers.

Issue #35 (UQ). isru has one of the cleanest sourced-spread stories in the
repo: the PNAS 2025 paper reports 24.3 +/- 5.8 kWh/kg for lunar oxygen with
an explicit standard deviation - the strongest single number in the module.

- **OXYGEN_FULL_CHAIN_KWH_PER_KG**: Normal(24.3, 5.8), source-provided std.
- **WATER_ICE_LOX_KWH_PER_KG**: Kornuta's water-ice route (11.3 kWh/kg) has
  the same practical spread as the propellant module's Kornuta figure -
  9-15 kWh/kg for mining/liquefaction variability.
- **METAL_MOE variants**: 2.6 (theoretical) < 3.7 (practical) < 4.0 (global-
  scale) < 5.0 (closure-sim's hand-set); Uniform(2.6, 5.0) spans this
  well-documented sequence.
- **DEFAULT_USABLE_THRESHOLD_WT_PCT**: "documented modelling choice, 0.1 wt%
  as a representative bulk-extraction floor" - a Fixed for now, but noted as
  a policy dial in REFERENCES.md rather than a measurement.
- **LUNAR_REGOLITH_ELEMENT_WT_PCT**: Apollo mare-soil bulk abundances. These
  vary +/- 20-30% across sample sites (highland vs mare); expose each as a
  Uniform over that documented spread.
"""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, Normal, Uniform

from isru.closure import (
    DEFAULT_USABLE_THRESHOLD_WT_PCT,
    LUNAR_REGOLITH_ELEMENT_WT_PCT,
)
from isru.energy import (
    CLOSURE_SIM_IRON_KWH_PER_KG,
    METAL_MOE_GLOBAL_SCALE_KWH_PER_KG,
    METAL_MOE_PRACTICAL_KWH_PER_KG,
    METAL_MOE_THEORETICAL_MIN_KWH_PER_KG,
    OXYGEN_FULL_CHAIN_KWH_PER_KG,
    OXYGEN_FULL_CHAIN_UNCERTAINTY_KWH_PER_KG,
    WATER_ICE_LOX_KWH_PER_KG,
)

# The strongest single number in the repo: source-provided Normal.
OXYGEN_FULL_CHAIN_KWH_PER_KG_DIST: Distribution = Normal(
    mean=OXYGEN_FULL_CHAIN_KWH_PER_KG,
    std=OXYGEN_FULL_CHAIN_UNCERTAINTY_KWH_PER_KG,
)

# Water-ice electrolysis practical band, shared with propellant module.
WATER_ICE_LOX_DIST: Distribution = Uniform(low=9.0, high=15.0)

# Metal MOE sequence (theoretical -> practical -> global -> closure-sim's
# hand-set). Point values 2.6, 3.7, 4.0, 5.0; Uniform over the full
# theoretical-to-hand-set band captures the "what number should closure-sim
# use for iron" question this module retires.
METAL_MOE_DIST: Distribution = Uniform(
    low=METAL_MOE_THEORETICAL_MIN_KWH_PER_KG,
    high=CLOSURE_SIM_IRON_KWH_PER_KG,
)

# Usable-abundance threshold is a modelling policy dial, not a measurement.
USABLE_THRESHOLD_WT_PCT_DIST: Distribution = Fixed(DEFAULT_USABLE_THRESHOLD_WT_PCT)

# Lunar regolith elemental abundance: Apollo mare-soil averages vary +/- 25%
# by site (mare vs highland). Each entry is a Uniform around its point value.
# Trace elements (< 0.5 wt%) are held as Fixed - the +/- 25% band is much
# smaller than the usable-threshold cut anyway.
LUNAR_REGOLITH_ELEMENT_WT_PCT_DIST: dict[str, Distribution] = {
    name: (Uniform(low=v * 0.75, high=v * 1.25) if v >= 0.5 else Fixed(v))
    for name, v in LUNAR_REGOLITH_ELEMENT_WT_PCT.items()
}


__all__ = [
    "OXYGEN_FULL_CHAIN_KWH_PER_KG_DIST",
    "WATER_ICE_LOX_DIST",
    "METAL_MOE_DIST",
    "USABLE_THRESHOLD_WT_PCT_DIST",
    "LUNAR_REGOLITH_ELEMENT_WT_PCT_DIST",
]
