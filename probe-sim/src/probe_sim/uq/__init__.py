"""Uncertainty quantification for probe-sim - issue #35, Depth track Tier 1.

Every REFERENCES.md number is sourced, but point-valued. This subpackage completes
the cardinal rule (CLAUDE.md §1) by giving each number a **spread** (a citable
distribution, [[distributions]]), propagating it through the pure fold via seeded
Monte Carlo ([[sample]]), and attributing the resulting variance to individual
inputs via Sobol total-order indices ([[sobol]]).

Zero pimas imports; the fold in probe_sim.environment / range / autonomy is
untouched. This is the "reactive-skin-free" wrapper described in CLAUDE.md §7.
"""

from probe_sim.uq.distributions import (
    Distribution,
    Fixed,
    LogNormal,
    Normal,
    Uniform,
)
from probe_sim.uq.report import one_line_finding
from probe_sim.uq.sample import MCResult, monte_carlo
from probe_sim.uq.sobol import SobolResult, sobol_total_order

__all__ = [
    "Distribution",
    "Fixed",
    "Uniform",
    "Normal",
    "LogNormal",
    "MCResult",
    "monte_carlo",
    "SobolResult",
    "sobol_total_order",
    "one_line_finding",
]
