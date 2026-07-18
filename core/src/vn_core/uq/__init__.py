"""Uncertainty quantification, shared across every von-neumann module.

Introduced by issue #35 (Depth track Tier 1): give every REFERENCES.md number
a citable spread, propagate it through the fold, rank the drivers. Lives here
(not in a single module) because that generalization is exactly the scope of
the issue - every module reuses these primitives, no duplication.

Pure Python today. The [`core/`](../..) layout leaves room for a future rust
+ pyo3 speed drop-in without moving imports (CLAUDE.md §7 says the fold stays
deterministic; whatever we swap under it must too).
"""

from vn_core.uq.distributions import (
    Distribution,
    Fixed,
    LogNormal,
    LogUniform,
    Normal,
    Uniform,
)
from vn_core.uq.report import one_line_finding
from vn_core.uq.sample import MCResult, monte_carlo
from vn_core.uq.sobol import SobolResult, sobol_total_order

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
