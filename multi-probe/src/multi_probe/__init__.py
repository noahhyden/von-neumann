"""multi-probe - a small, deterministic fleet of self-replicating probes.

The intermediate step between the single probe and the swarm (ROADMAP §3): a handful
of probes (tens, not 10⁵), each an agent that builds copies of itself at a rate its
local sunlight allows and disperses children outward. Deterministic and seeded, so
`speculate` stays exact before the paradigm jump to a stochastic spatial ABM.

Re-instantiates two ceilings from the earlier modules at fleet scale: the electronics
wall (a finite vitamin pool) and a spatial power wall (1/d² sunlight vs dispersal).
"""

from multi_probe.fleet import (
    build_rate_kg_per_day,
    initial_state,
    params_from_factory,
    simulate_fleet,
    step,
    time_to_build_one_copy_days,
)
from multi_probe.models import (
    FleetParams,
    FleetResult,
    FleetState,
    FleetStep,
    Probe,
    ProbeStatus,
    RegimeCount,
)

__all__ = [
    "simulate_fleet",
    "step",
    "initial_state",
    "params_from_factory",
    "build_rate_kg_per_day",
    "time_to_build_one_copy_days",
    "FleetParams",
    "FleetResult",
    "FleetState",
    "FleetStep",
    "Probe",
    "ProbeStatus",
    "RegimeCount",
]
