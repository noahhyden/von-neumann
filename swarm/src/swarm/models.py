"""Plain-data types for the deterministic swarm fold (slice 1: the settlement front).

The star field is held struct-of-arrays style (parallel lists of coordinates + a
per-star settlement year), which is the shape the future TypeScript SoA/typed-array
port will use at scale. Probes are ephemeral in-flight hops. A seeded RNG is carried in
the state (CLAUDE.md §7), so a run is a pure function of (params, seed).

Nothing here imports pimas, the DOM, or a clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

# Speed of light in parsecs per year (c = 299792.458 km/s). Exact given the SI second
# and the parsec definition: 1 pc = 3.0856775814913673e13 km, 1 yr = 3.15576e7 s
# (Julian year). c = 299792.458 * 3.15576e7 / 3.0856775814913673e13 pc/yr.
C_PC_PER_YEAR: float = 299792.458 * 3.15576e7 / 3.0856775814913673e13


class SwarmParams(BaseModel):
    """Inputs to one settlement-front run. Physical numbers sourced in REFERENCES.md."""

    n_stars: int = Field(gt=1, default=500)
    density_stars_per_pc3: float = Field(
        gt=0, default=0.14, description="local stellar number density [ESTIMATE]"
    )
    probe_speed_c: float = Field(
        gt=0, le=1, default=0.1, description="cruise speed as a fraction of c (Nicholson & Forgan)"
    )
    offspring_per_settlement: int = Field(
        ge=0, default=2, description="probes launched from each newly settled star"
    )
    settle_time_years: float = Field(
        ge=0, default=0.0, description="dwell to build offspring before they depart [ESTIMATE]"
    )
    dt_years: float = Field(
        gt=0, default=25.0, description="fixed timestep; keep ≲ mean hop time (~63 yr at defaults)"
    )
    max_years: float = Field(gt=0, default=2_000_000.0, description="safety cap; the run ends when the front does")

    @property
    def probe_speed_pc_per_year(self) -> float:
        return self.probe_speed_c * C_PC_PER_YEAR

    @property
    def box_side_pc(self) -> float:
        """Side of the cube holding ``n_stars`` at the given density: (N/ρ)^(1/3)."""
        return (self.n_stars / self.density_stars_per_pc3) ** (1.0 / 3.0)


@dataclass
class Probe:
    """One in-flight hop: heading to ``target`` star, arriving at ``arrive_year``."""

    id: int
    target: int
    arrive_year: float


@dataclass
class SwarmState:
    """Full state carried by the fold. SoA star field + seeded RNG (pure data)."""

    rng: int
    year: float
    xs: list[float]
    ys: list[float]
    zs: list[float]
    settled_year: list[float]  # -1.0 while unsettled, else the year it was settled
    origin: int  # index of the homeworld star (front radius is measured from here)
    probes: list[Probe]
    next_probe_id: int
    total_launched: int

    def n_settled(self) -> int:
        return sum(1 for y in self.settled_year if y >= 0.0)


@dataclass
class SwarmStep:
    year: float
    n_settled: int
    fraction_settled: float
    in_flight: int
    front_radius_pc: float


@dataclass
class SwarmResult:
    n_stars: int
    final_settled: int
    total_probes_launched: int
    t50_years: float | None  # years to settle 50% / 90% / 100% of the field
    t90_years: float | None
    t100_years: float | None
    front_radius_pc: float
    steps: list[SwarmStep] = field(default_factory=list)
