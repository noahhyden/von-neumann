"""multi-probe - a small, deterministic fleet of self-replicating probes."""

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
