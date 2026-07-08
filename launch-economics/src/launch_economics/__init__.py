"""launch-economics - the economics of not launching mass.

Launch cost, the rocket-equation Δv penalty on delivering mass across the solar
system, and the launch-mass leverage of shipping a self-replicating seed instead of
the finished installation.

Every number traces to a source; see REFERENCES.md.
"""

from launch_economics.economics import ReplicationLaunchComparison
from launch_economics.from_closure import (
    comparison_from_closure,
    vitamin_mass_for_build,
)
from launch_economics.launch import (
    G0_M_S2,
    exhaust_velocity_m_s,
    launch_cost_usd,
    propellant_fraction,
    rocket_equation_mass_ratio,
)
from launch_economics.value import (
    PLATINUM_ANNUAL_PRODUCTION_T,
    PLATINUM_MARKET_ANNUAL_USD,
    PSYCHE_QUOTED_VALUE_USD,
    market_absorption_years,
    output_value_launch_avoided_usd,
    realizable_value_ceiling_usd,
)

__all__ = [
    "ReplicationLaunchComparison",
    "comparison_from_closure",
    "vitamin_mass_for_build",
    "G0_M_S2",
    "exhaust_velocity_m_s",
    "launch_cost_usd",
    "propellant_fraction",
    "rocket_equation_mass_ratio",
    "PLATINUM_ANNUAL_PRODUCTION_T",
    "PLATINUM_MARKET_ANNUAL_USD",
    "PSYCHE_QUOTED_VALUE_USD",
    "market_absorption_years",
    "output_value_launch_avoided_usd",
    "realizable_value_ceiling_usd",
]
