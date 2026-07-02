"""launch-economics — the economics of not launching mass.

Launch cost, the rocket-equation Δv penalty on delivering mass across the solar
system, and the launch-mass leverage of shipping a self-replicating seed instead of
the finished installation.

Every number traces to a source; see REFERENCES.md.
"""

from launch_economics.economics import ReplicationLaunchComparison
from launch_economics.launch import (
    G0_M_S2,
    exhaust_velocity_m_s,
    launch_cost_usd,
    propellant_fraction,
    rocket_equation_mass_ratio,
)

__all__ = [
    "ReplicationLaunchComparison",
    "G0_M_S2",
    "exhaust_velocity_m_s",
    "launch_cost_usd",
    "propellant_fraction",
    "rocket_equation_mass_ratio",
]
