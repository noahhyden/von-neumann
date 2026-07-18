"""reliability - degradation, mortality, and the Aurora steady-state.

The real-world messiness CLAUDE.md 3 asks for: nothing else in the project ages or fails.
Three parts: deterministic array/dose decay (`degradation`), a stochastic per-day hazard
built as a strict seeded fold (`mortality`, the only RNG in the repo), and the Aurora
equilibrium settled fraction `X_eq = 1 - T_l/T_s` that turns unbounded fleet growth into a
steady state (`aurora`). It consumes the shared radiation environment from
`shielding.radenv`.

The seeded fold reproduces bit-for-bit from a seed, and with hazard = 0 it reproduces the
existing failure-free models exactly (the mandatory regression guard). No pimas. Every
number traces to a source; see REFERENCES.md.
"""

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
