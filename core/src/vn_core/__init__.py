"""Shared core primitives for the von-neumann monorepo.

Every module reaches for a seeded RNG, UQ propagation, and validated ODE
integration. They live here so no module re-implements them and the invariants
(deterministic, seeded, no wall clock) hold across the repo.

Subpackages:

- :mod:`vn_core.rng` - mulberry32, threaded through the fold (issue #29). One
  Python source of truth for the mulberry32 (byte-identical to the JS mirror in
  the frontend). Reliability's ``splitmix64`` is a distinct generator kept in
  its own module because it needs no JS parity; both share the
  ``(value, new_state)`` threading contract (issue #65).
- :mod:`vn_core.uq`  - propagation, Sobol sensitivity, PCE (issue #35).
- :mod:`vn_core.ode` - RK45 + backward Euler with a validation gate (issue #38).
- :mod:`vn_core.linalg` - tiny dense solvers shared by the two: a square Gaussian
  elimination (implicit ODE) and a Householder-QR least-squares (PCE regression).
"""
