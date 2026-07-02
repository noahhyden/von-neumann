"""power-budget — how an autonomous factory splits a watt between making and thinking.

A pure, one-shot power accounting: divide a (solar-limited) power budget among
manufacturing, computation, and housekeeping, and convert compute-watts into
throughput — floored by the Landauer limit and anchored to the ~20 W human brain.

Every number traces to a source; see REFERENCES.md.
"""

from power_budget.budget import PowerBudget, compute_capacity_flops
from power_budget.physics import (
    BOLTZMANN_J_PER_K,
    BRAIN_COMPUTE_FLOPS_ESTIMATE,
    HUMAN_BRAIN_POWER_W,
    brain_equivalents,
    landauer_limit_j_per_bit,
    max_bit_operations_per_joule,
)

__all__ = [
    "PowerBudget",
    "compute_capacity_flops",
    "BOLTZMANN_J_PER_K",
    "HUMAN_BRAIN_POWER_W",
    "BRAIN_COMPUTE_FLOPS_ESTIMATE",
    "brain_equivalents",
    "landauer_limit_j_per_bit",
    "max_bit_operations_per_joule",
]
