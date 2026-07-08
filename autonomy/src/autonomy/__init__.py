"""autonomy - onboard compute demand and the autonomy wall.

Supplies the compute *demand* that pairs with `probe-sim`'s 1/d^2 compute *supply*,
closing the loop `mission`/`multi-probe` left open with a free 0.70 manufacturing / 0.30
compute split. The demand is a sourced band - honeybee brain (~1e13) to mouse brain
(~1e15), with a self-driving car (~1.4e14 ops/s) landing between them - and where supply
falls below it is the autonomy wall, `d = sqrt(supply_1AU / required)`.

Pure accounting, no neural-net simulation (CLAUDE.md 3), no pimas, no RNG (7). Reuses
`power-budget` (watts<->FLOPS) and `probe-sim` (supply). Every number traces to a source;
see REFERENCES.md.
"""

from autonomy.autonomy import (
    HONEYBEE_BRAIN_FLOPS,
    MOUSE_BRAIN_FLOPS,
    SELF_DRIVING_OPS_PER_S,
    ComputeDemandBand,
    affordable_compute_at,
    autonomy_wall_au,
    compute_fraction_needed,
    required_compute_band,
    required_compute_power_w,
)

__all__ = [
    "HONEYBEE_BRAIN_FLOPS",
    "MOUSE_BRAIN_FLOPS",
    "SELF_DRIVING_OPS_PER_S",
    "ComputeDemandBand",
    "affordable_compute_at",
    "autonomy_wall_au",
    "compute_fraction_needed",
    "required_compute_band",
    "required_compute_power_w",
]
