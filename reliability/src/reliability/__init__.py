"""reliability - degradation, mortality, and the Aurora steady-state."""

from reliability.aurora import (
    aurora_equilibrium,
    aurora_integrate,
    aurora_rate,
)
from reliability.degradation import (
    ARRAY_DEGRADATION_BAND_PER_YR,
    ARRAY_DEGRADATION_PER_YR,
    array_power_fraction,
    cumulative_gcr_dose_msv,
)
from reliability.mortality import (
    SATELLITE_HAZARD_PER_DAY,
    FleetState,
    expected_survival_fraction,
    simulate,
    step,
)
from reliability.rng import next_uniform, next_uint64, seed_state

__all__ = [
    # aurora
    "aurora_equilibrium",
    "aurora_integrate",
    "aurora_rate",
    # degradation
    "ARRAY_DEGRADATION_BAND_PER_YR",
    "ARRAY_DEGRADATION_PER_YR",
    "array_power_fraction",
    "cumulative_gcr_dose_msv",
    # mortality (seeded fold)
    "SATELLITE_HAZARD_PER_DAY",
    "FleetState",
    "expected_survival_fraction",
    "simulate",
    "step",
    # rng
    "next_uniform",
    "next_uint64",
    "seed_state",
]
