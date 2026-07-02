"""probe-sim — a single self-replicating probe.

Models the Borgue & Hein (2020) near-term self-replicating probe concept: a
solar-electric spacecraft of six modules that replicates ~70% of its own mass and
imports the rest (mostly electronics) as "vitamins". This module starts from the
physics that gates such a probe's reach — how much power sunlight delivers at a
given heliocentric distance — and builds toward the operational range where
replication is viable.

Every number traces to a source; see REFERENCES.md.
"""

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
]
