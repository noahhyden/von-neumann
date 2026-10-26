"""Compatibility shim - the UQ primitives now live in [`vn_core.uq`](../../../../../core/src/vn_core/uq)."""

from vn_core.uq import (
    Distribution,
    Fixed,
    LogNormal,
    LogUniform,
    MCResult,
    Normal,
    SobolResult,
    Uniform,
    monte_carlo,
    one_line_finding,
    sobol_total_order,
)

__all__ = [
    "Distribution",
    "Fixed",
    "Uniform",
    "Normal",
    "LogNormal",
    "LogUniform",
    "MCResult",
    "monte_carlo",
    "SobolResult",
    "sobol_total_order",
    "one_line_finding",
]
