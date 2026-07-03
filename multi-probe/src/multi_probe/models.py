"""Plain-data types for the deterministic multi-probe fold.

A probe is an *agent*: it sits at a heliocentric distance, builds toward its next copy
at a rate its local sunlight allows, and - when it has built one copy's worth of local
structure and the fleet still has imported "vitamins" (non-replicable electronics) -
spawns a child that travels outward to a new distance. The whole fleet state is plain,
serializable data with a seeded RNG carried inside it (CLAUDE.md §7), so the
simulation is a pure function of (params, seed).

Nothing here imports pimas, the DOM, or a clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class ProbeStatus:
    TRAVELING = "traveling"  # en route to its assigned distance, not yet building
    ACTIVE = "active"  # arrived; building toward its next child


@dataclass
class Probe:
    """One probe agent. Immutable-by-convention: the fold never mutates an input probe."""

    id: int
    distance_au: float
    status: str
    arrival_day: float  # day it becomes ACTIVE (== birth day for the seed probes)
    built_kg: float = 0.0  # local structure accumulated toward the next child
    children: int = 0  # copies successfully spawned


class FleetParams(BaseModel):
    """Everything the fold needs; the factory-derived fields come from a real BOM.

    The three factory-derived numbers (seed mass, closure, local build energy) are read
    from a closure-sim ``Factory`` via ``params_from_factory`` - they are sourced. The
    rest are flagged scenario choices/estimates (see REFERENCES.md).
    """

    # --- factory-derived (sourced via closure-sim) ---
    seed_mass_kg: float = Field(gt=0, description="mass of one probe copy (the seed)")
    closure_ratio: float = Field(ge=0, le=1, description="fraction of a copy built locally")
    e_local_kwh_per_kg: float = Field(gt=0, description="energy to build 1 kg of local structure")
    local_build_rate_kg_per_day: float = Field(
        gt=0, description="the probe's machinery throughput (alpha*F for a fixed-size probe)"
    )

    # --- the probe's solar array (probe-sim) ---
    array_area_m2: float = Field(gt=0)
    array_efficiency: float = Field(gt=0, le=1)
    manufacturing_fraction: float = Field(gt=0, le=1, description="share of power to building")

    # --- fleet dynamics (scenario choices / estimates) ---
    start_distance_au: float = Field(gt=0, default=1.0)
    n_seed_probes: int = Field(ge=1, default=1, description="probes landed by the launch")
    dispersal_factor: float = Field(
        ge=1.0, default=1.3, description="a child settles this many × its parent's distance"
    )
    max_distance_au: float = Field(gt=0, default=40.0, description="clamp on child distance")
    transit_days: float = Field(ge=0, default=365.0, description="base travel time to a new site")
    transit_jitter_frac: float = Field(
        ge=0, le=1, default=0.0, description="seeded ± noise on transit time (0 = deterministic)"
    )
    vitamin_pool_kg: float = Field(
        ge=0, default=1_000_000.0, description="total imported non-replicable mass available"
    )
    max_probes: int = Field(ge=1, default=64, description="fleet cap (this is the *small* model)")


@dataclass
class FleetState:
    """The full state the fold carries forward. Pure data + the seeded RNG state."""

    rng: int  # mulberry32 state, threaded (never ambient randomness)
    day: float
    probes: list[Probe]
    vitamin_pool_kg: float
    next_id: int

    def active(self) -> list[Probe]:
        return [p for p in self.probes if p.status == ProbeStatus.ACTIVE]


class RegimeCount(BaseModel):
    """Why the fleet stopped growing, at the final step."""

    vitamin_limited: bool  # the electronics wall: pool exhausted
    power_limited: bool  # some probes build too slowly to ever copy in the time left
    cap_limited: bool  # hit max_probes (a scope bound, not physics)


@dataclass
class FleetStep:
    day: float
    population: int  # arrived + traveling
    active: int
    total_built_kg: float
    vitamin_pool_kg: float
    mean_distance_au: float
    max_distance_au: float


@dataclass
class FleetResult:
    """The whole run: the time series plus final headline numbers."""

    final_population: int
    final_active: int
    total_children: int
    vitamins_consumed_kg: float
    vitamins_remaining_kg: float
    doubling_time_days: float | None  # first fleet-size doubling
    binding: RegimeCount
    mean_distance_au: float
    max_distance_au: float
    steps: list[FleetStep] = field(default_factory=list)
