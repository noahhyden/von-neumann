"""autonomy - onboard compute demand and the autonomy wall."""

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
