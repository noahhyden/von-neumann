"""Distributional companions to closure-sim's sourced numbers.

Issue #35 (UQ) applied to closure-sim: every per-part energy figure and every
material-strength figure in REFERENCES.md turns into a citable **band**, not a
point. Callers reach here (via `vn_core.uq`) when they want error bars on
closure or on the electronics-wall crossover time.

Two categories of sourced spread live here:

- **Per-part manufacturing energy** (`PART_ENERGY_KWH_PER_KG_DIST`): every
  entry in the REFERENCES.md table has a low-high range from the LCA
  literature, held here as `Uniform(low, high)`. Uniform is the honest read
  when a source gives an interval without a shape (Kopp & Lean's +/- 0.5
  is a std; the LCA tables here are min-max intervals).
- **Sintered regolith strength** (`SINTERED_REGOLITH_STRENGTH_DIST`): the
  (2.49, 355.0) MPa band explicitly labelled in REFERENCES.md as "carry as
  a band, never a point" (>100x span across techniques). LogUniform is the
  right shape for a multi-order-of-magnitude range - each decade is equally
  likely, matching how the source presents the technique choice rather than
  the linear numeric distance.

Anything scenario-specific (a particular chip node, a particular sintering
technique) still narrows the distribution at the point of use.
"""

from __future__ import annotations

from vn_core.uq import Distribution, LogUniform, Uniform

from closure_sim.structures import SINTERED_REGOLITH_STRENGTH_BAND_MPA


# Per-part manufacturing energy ranges (kWh/kg), from the REFERENCES.md table.
# Keys mirror the categories used in scenario YAMLs; each Uniform's endpoints
# cite the LCA sources listed in REFERENCES.md.
PART_ENERGY_KWH_PER_KG_DIST: dict[str, Distribution] = {
    # metals / structure: recycled -> primary steel
    "structure": Uniform(1.7, 9.7),
    "thermal": Uniform(1.7, 5.6),
    "refining_plant": Uniform(6.0, 24.0),
    # motors / actuators / manipulators
    "actuators": Uniform(14.0, 20.0),
    "manipulators": Uniform(14.0, 20.0),
    # precision alloys / superalloys
    "bearings": Uniform(20.0, 46.0),
    # precision metal housings (tens)
    "sensor_housings": Uniform(20.0, 100.0),
    # silicon PV
    "solar_arrays": Uniform(40.0, 120.0),
    # power electronics / ICs
    "power_electronics": Uniform(1000.0, 3000.0),
    # electronic sensors
    "electronic_sensors": Uniform(2000.0, 8000.0),
    # finished packaged compute / logic chips (the widest, most consequential range)
    "compute_chips": Uniform(3000.0, 15000.0),
}

# Sintered lunar-regolith compressive strength (MPa). REFERENCES.md explicitly
# names this a >100x band by technique; LogUniform over the (2.49, 355.0)
# endpoints preserves that spread on its natural (log) scale.
SINTERED_REGOLITH_STRENGTH_DIST: Distribution = LogUniform(
    low=SINTERED_REGOLITH_STRENGTH_BAND_MPA[0],
    high=SINTERED_REGOLITH_STRENGTH_BAND_MPA[1],
)


__all__ = [
    "PART_ENERGY_KWH_PER_KG_DIST",
    "SINTERED_REGOLITH_STRENGTH_DIST",
]
