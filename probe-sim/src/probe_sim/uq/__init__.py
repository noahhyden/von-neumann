"""Compatibility shim - the UQ primitives now live in [`vn_core.uq`](../../../../../core/src/vn_core/uq).

Every von-neumann module reuses the same distributions, seeded MC, and Sobol
estimator; keeping a copy per module was the wrong shape once issue #35's
generalization scope kicked in (issue #35 explicitly asks for "then generalize
the interface across the other modules"). All new code should import from
`vn_core.uq` directly; this shim is kept only so probe-sim's own tests and
scripts do not have to move in the same PR.
"""

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
