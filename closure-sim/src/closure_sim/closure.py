"""Mass-closure calculation and vitamin breakdown.

Closure is the fraction of a factory's own mass it can manufacture locally. The
headline caveat, surfaced deliberately: mass closure *flatters electronics*. A
factory can be 99% closed by mass yet non-viable because the missing 1% is the
chips. So we also expose, in the replication layer, the resupply ceiling R/(1-C)
that the vitamin fraction imposes.
"""

from __future__ import annotations

from pydantic import BaseModel

from .models import Factory


class VitaminEntry(BaseModel):
    name: str
    category: str
    mass_kg: float
    mass_share: float  # fraction of total factory mass
    processes: list[str]


class ClosureReport(BaseModel):
    factory_name: str
    total_mass_kg: float
    local_mass_kg: float
    vitamin_mass_kg: float
    closure_ratio: float  # local_mass / total_mass, in [0, 1]
    total_build_energy_kwh: float  # energy to build one complete copy
    local_build_energy_kwh: float  # energy for the locally-produced fraction only
    vitamins: list[VitaminEntry]


def compute_closure(factory: Factory) -> ClosureReport:
    """Compute the mass closure ratio, vitamin breakdown, and build energy."""
    total = factory.total_mass_kg
    local = factory.local_mass_kg

    vitamins = [
        VitaminEntry(
            name=s.name,
            category=s.category,
            mass_kg=s.mass_kg,
            mass_share=s.mass_kg / total if total > 0 else 0.0,
            processes=list(s.processes),
        )
        for s in factory.vitamins
    ]
    # Heaviest vitamins first - that's the order an engineer wants to read.
    vitamins.sort(key=lambda v: v.mass_kg, reverse=True)

    total_energy = sum(s.build_energy_kwh for s in factory.subsystems)
    local_energy = sum(
        s.build_energy_kwh for s in factory.subsystems if s.producible_locally
    )

    return ClosureReport(
        factory_name=factory.name,
        total_mass_kg=total,
        local_mass_kg=local,
        vitamin_mass_kg=factory.vitamin_mass_kg,
        closure_ratio=local / total if total > 0 else 0.0,
        total_build_energy_kwh=total_energy,
        local_build_energy_kwh=local_energy,
        vitamins=vitamins,
    )
