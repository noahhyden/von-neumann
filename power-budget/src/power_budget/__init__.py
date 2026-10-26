"""power-budget - how an autonomous factory splits a watt between making and thinking."""

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
