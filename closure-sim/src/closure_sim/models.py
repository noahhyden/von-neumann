"""Core domain model: subsystems, replication parameters, and the factory itself.

A factory is a bill of materials (a list of :class:`Subsystem`) plus, optionally,
a :class:`ReplicationParams` block describing how a landed seed grows. Closure and
replication math live in sibling modules; this file only holds data + a few cheap
mass/energy aggregates so the model stays the single source of truth.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Categories treated as "electronics" for the electronics-wall analysis. Kept here
# (not buried in analysis.py) because scenario authors reason in these terms.
ELECTRONICS_CATEGORIES: frozenset[str] = frozenset(
    {"compute", "electronics", "semiconductor"}
)


class Subsystem(BaseModel):
    """One line item in a factory's bill of materials.

    A subsystem is a *vitamin* when it cannot be produced locally
    (``producible_locally is False``) - it must be shipped from Earth.
    """

    name: str
    mass_kg: float = Field(gt=0)
    category: str
    producible_locally: bool = True
    processes: list[str] = Field(default_factory=list)
    energy_to_produce_kwh_per_kg: float = Field(ge=0, default=0.0)

    @property
    def is_vitamin(self) -> bool:
        return not self.producible_locally

    @property
    def build_energy_kwh(self) -> float:
        """Energy to manufacture this subsystem once (mass x specific energy)."""
        return self.mass_kg * self.energy_to_produce_kwh_per_kg


class ReplicationParams(BaseModel):
    """Inputs to the discrete-time replication simulator.

    ``seed_mass_kg`` is the factory mass landed from Earth and ``local_build_rate_kg_per_day``
    is that seed's initial local-material output. Their ratio defines productivity
    (output per day per kg of installed factory), which is what makes capacity grow
    with the factory - i.e. makes replication exponential rather than linear.
    """

    seed_mass_kg: float = Field(gt=0)
    local_build_rate_kg_per_day: float = Field(gt=0)
    vitamin_resupply_mass_kg: float = Field(ge=0, default=0.0)
    resupply_cadence_days: float = Field(gt=0, default=30.0)
    available_power_kw: float = Field(gt=0)
    target_output_kg_per_day: float = Field(gt=0, default=1000.0)
    duration_days: int = Field(gt=0, default=3650)
    dt_days: float = Field(gt=0, default=1.0)

    @property
    def resupply_rate_kg_per_day(self) -> float:
        return self.vitamin_resupply_mass_kg / self.resupply_cadence_days

    @property
    def available_power_kwh_per_day(self) -> float:
        return self.available_power_kw * 24.0


class Factory(BaseModel):
    """A named bill of materials, optionally with replication parameters."""

    name: str
    subsystems: list[Subsystem]
    replication: ReplicationParams | None = None

    @property
    def total_mass_kg(self) -> float:
        return sum(s.mass_kg for s in self.subsystems)

    @property
    def local_mass_kg(self) -> float:
        return sum(s.mass_kg for s in self.subsystems if s.producible_locally)

    @property
    def vitamin_mass_kg(self) -> float:
        return sum(s.mass_kg for s in self.subsystems if s.is_vitamin)

    @property
    def vitamins(self) -> list[Subsystem]:
        return [s for s in self.subsystems if s.is_vitamin]
