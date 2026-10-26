"""Distributional companions to isru's sourced numbers."""

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

# Metal MOE sequence 2.6 (theoretical) < 3.7 (practical) < 4.0 (global) < 5.0 (closure-sim hand-set): Uniform spans the band this module retires.
METAL_MOE_DIST: Distribution = Uniform(
    low=METAL_MOE_THEORETICAL_MIN_KWH_PER_KG,
    high=CLOSURE_SIM_IRON_KWH_PER_KG,
)

# Usable-abundance threshold is a modelling policy dial, not a measurement.
USABLE_THRESHOLD_WT_PCT_DIST: Distribution = Fixed(DEFAULT_USABLE_THRESHOLD_WT_PCT)

# Lunar regolith abundance: Apollo mare-soil averages vary +/- 25% by site, so each major element is Uniform and trace (<0.5 wt%) elements are Fixed.
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
