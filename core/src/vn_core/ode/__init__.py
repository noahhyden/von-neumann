"""Ordinary differential equation solvers, shared across every von-neumann module.

Phase 1 of issue #38: replace the hand-rolled forward-Euler loops (each of which
picked a timestep "small enough for the regimes we report" - an unjustified
number by CLAUDE.md §1) with one validated, adaptive integrator that takes a
tolerance instead of a guessed dt.

Two methods, one entry point (`solve`):
- ``"rk45"`` - Dormand-Prince, explicit adaptive. Default; the non-stiff workhorse.
- ``"bdf1"`` - backward Euler, implicit L-stable. For stiff systems where an
  explicit method would need vanishingly small steps.

Pure Python, zero runtime dependencies (like the rest of `vn-core`), and a pure
deterministic fold (§7): no RNG, no wall clock, fixed operation order, so the
same (f, y0, t_span, tol) returns byte-identical output on any machine. The
[`core/`](../..) layout leaves room for a rust + pyo3 speed drop-in behind this
same interface (issue #38 Phase 3) without callers moving an import.
"""

from vn_core.ode.common import ODEResult
from vn_core.ode.solve import solve

__all__ = ["ODEResult", "solve"]
