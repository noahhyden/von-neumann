"""Shared core primitives for the von-neumann monorepo.

Every module reaches for the same seeded RNG, UQ propagation, and validated
ODE integration. They live here so no module re-implements them and the
invariants (deterministic, seeded, no wall clock) hold across the repo.

Subpackages:

- :mod:`vn_core.rng` - mulberry32, threaded through the fold (issue #29).
- :mod:`vn_core.uq`  - propagation, Sobol sensitivity, PCE (issue #35).
- :mod:`vn_core.ode` - RK45 + backward Euler with a validation gate (issue #38).
"""
