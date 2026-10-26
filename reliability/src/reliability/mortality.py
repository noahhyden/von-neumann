"""Stochastic mortality as a pure, seeded, deterministic fold."""

from __future__ import annotations

from dataclasses import dataclass

from reliability.rng import next_uniform, seed_state

# Proxy per-day hazard for a discrete unit from satellite on-orbit failure statistics: [ESTIMATE], a defensible analog and not a measured factory rate (REFERENCES.md).
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


def _verify_step_invariants(before: FleetState, after: FleetState) -> None:
    """Assert the documented step invariants on (before -> after). See REFERENCES.md."""
    assert after.alive <= before.alive, "[inv:rl-alive-monotone] alive_new > alive_old"
    assert after.alive >= 0, "[inv:rl-alive-nonneg] alive_new < 0"
    assert after.day == before.day + 1, "[inv:rl-day-monotone] day_new != day_old + 1"
    # When any draws happened, the RNG state must have advanced; guards against step() forgetting to thread the RNG and returning the same state.
    if before.alive > 0:
        assert after.rng != before.rng, "[inv:rl-rng-advances] RNG state did not change despite alive>0"


def step(state: FleetState, hazard_per_day: float) -> FleetState:
    """Advance the fleet one day: each living unit fails with probability hazard_per_day."""
    if not 0.0 <= hazard_per_day <= 1.0:
        raise ValueError("hazard_per_day must be in [0, 1]")
    rng = state.rng
    deaths = 0
    for _ in range(state.alive):
        u, rng = next_uniform(rng)
        if u < hazard_per_day:
            deaths += 1
    new_state = FleetState(rng=rng, alive=state.alive - deaths, day=state.day + 1)
    if __debug__:
        _verify_step_invariants(state, new_state)
    return new_state


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
    """Analytic expected fraction surviving: (1 - hazard)^days."""
    if days < 0:
        raise ValueError("days must be non-negative")
    if not 0.0 <= hazard_per_day <= 1.0:
        raise ValueError("hazard_per_day must be in [0, 1]")
    return (1.0 - hazard_per_day) ** days
