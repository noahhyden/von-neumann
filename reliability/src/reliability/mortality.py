"""Stochastic mortality as a pure, seeded, deterministic fold.

Real fleets lose units: a factory or probe fails at some per-day hazard. This is the one
place the project uses randomness, so it is built to the strictest reading of CLAUDE.md 7
- `step(state, hazard, ...) -> state` is a pure fold over an explicit RNG state (from
`rng.py`), with deterministic iteration order and no wall clock. Same seed and inputs
reproduce the trajectory bit-for-bit; that is what makes replay and `speculate` exact.

The per-day hazard itself is a proxy `[ESTIMATE]`: discrete self-replicating factories
have no operational failure history, so we borrow a satellite-class on-orbit failure rate
(~1.1e-5 per day) as a defensible analog, tagged at the use site. The self-replication
*mutation* rate (copies that build flawed copies) is a genuine `[GAP]` - not modelled
here, only flagged.

**The mandatory guard (CLAUDE.md 2):** with `hazard = 0`, no unit can ever die, so the
population trajectory is identical to the project's current failure-free models. The test
suite asserts this bit-exact regression - the safety net that lets mortality be added
without disturbing any existing result.
"""

from __future__ import annotations

from dataclasses import dataclass

from reliability.rng import next_uniform, seed_state

# Proxy per-day hazard for a discrete unit, from satellite on-orbit failure statistics.
# [ESTIMATE] - a defensible analog, not a measured factory rate. See REFERENCES.md.
SATELLITE_HAZARD_PER_DAY: float = 1.1e-5


@dataclass(frozen=True)
class FleetState:
    """The fold's state: explicit RNG, living-unit count, and elapsed day. Plain data."""

    rng: int
    alive: int
    day: int

    @staticmethod
    def initial(population: int, seed: int) -> "FleetState":
        if population < 0:
            raise ValueError("population must be non-negative")
        return FleetState(rng=seed_state(seed), alive=population, day=0)


def step(state: FleetState, hazard_per_day: float) -> FleetState:
    """Advance the fleet one day: each living unit fails with probability hazard_per_day.

    Pure fold: draws are taken in a fixed order (one per living unit), the RNG state is
    threaded through and returned in the new state, and nothing external is read. With
    hazard_per_day = 0 no draw can trigger a death (a uniform in [0, 1) is never < 0), so
    the population is invariant - the bit-exact regression against the failure-free model.
    """
    if not 0.0 <= hazard_per_day <= 1.0:
        raise ValueError("hazard_per_day must be in [0, 1]")
    rng = state.rng
    deaths = 0
    for _ in range(state.alive):
        rng, u = next_uniform(rng)
        if u < hazard_per_day:
            deaths += 1
    return FleetState(rng=rng, alive=state.alive - deaths, day=state.day + 1)


def simulate(
    population: int, days: int, hazard_per_day: float, *, seed: int
) -> FleetState:
    """Fold `step` over `days` days from a seeded initial state. Deterministic in seed."""
    if days < 0:
        raise ValueError("days must be non-negative")
    state = FleetState.initial(population, seed)
    for _ in range(days):
        state = step(state, hazard_per_day)
    return state


def expected_survival_fraction(days: int, hazard_per_day: float) -> float:
    """Analytic expected fraction surviving: (1 - hazard)^days.

    The deterministic expectation the stochastic fold fluctuates around - used to check
    the simulation is unbiased, not to replace it.
    """
    if days < 0:
        raise ValueError("days must be non-negative")
    if not 0.0 <= hazard_per_day <= 1.0:
        raise ValueError("hazard_per_day must be in [0, 1]")
    return (1.0 - hazard_per_day) ** days
