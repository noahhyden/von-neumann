"""probe-sim - a single self-replicating probe."""

from probe_sim.environment import (
    SOLAR_CONSTANT_1AU_W_M2,
    AU_DISTANCE,
    SolarArray,
    solar_irradiance_w_m2,
)
from probe_sim.models import (
    REPLICATED_MASS_FRACTION,
    ProbeModule,
)
from probe_sim.range import (
    RangeResult,
    available_power_kw,
    is_viable_at,
    operational_range,
)
from probe_sim.autonomy import (
    ComputeHeadroom,
    compute_headroom_at,
    max_distance_for_compute,
)

__all__ = [
    "SOLAR_CONSTANT_1AU_W_M2",
    "AU_DISTANCE",
    "SolarArray",
    "solar_irradiance_w_m2",
    "REPLICATED_MASS_FRACTION",
    "ProbeModule",
    "RangeResult",
    "available_power_kw",
    "is_viable_at",
    "operational_range",
    "ComputeHeadroom",
    "compute_headroom_at",
    "max_distance_for_compute",
]
