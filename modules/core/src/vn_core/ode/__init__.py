"""Ordinary differential equation solvers, shared across every von-neumann module."""

from vn_core.ode.common import ODEResult
from vn_core.ode.solve import solve

__all__ = ["ODEResult", "solve"]
