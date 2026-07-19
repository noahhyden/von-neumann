# core - shared primitives across the von-neumann monorepo

Distributed as the `vn-core` package (Python name `vn_core`). Currently holds:

- **`vn_core.uq`** - uncertainty quantification. Distributions (`Fixed`, `Uniform`,
  `Normal`, `LogNormal`), seeded Monte Carlo, Sobol first- and total-order
  sensitivity (each with a confidence interval, so an index that is within noise
  reads as a CI straddling zero rather than a false-confident number), a
  paper-ready one-line reporter. `uq_and_gsa` runs both propagation and sensitivity
  off one Saltelli design (the UQ is free from the Sobol evaluations). `pce_fit`
  is a polynomial-chaos surrogate for **smooth, low-dimensional** findings: it
  returns the moments, closed-form Sobol indices, and a cheap `predict()` surrogate
  in far fewer model evaluations than Monte Carlo, and carries a `fit_residual`
  that flags non-smooth findings so it never silently lies (fall back to
  `monte_carlo`/`uq_and_gsa` there). Every von-neumann module reaches for this so
  no one re-implements the RNG discipline or the propagation loop.
- **`vn_core.ode`** - ordinary differential equation solvers (issue
  [#38](https://github.com/noahhyden/von-neumann/issues/38)). One entry point,
  `solve(f, y0, t_span, ...)`, with two methods: `"rk45"` (Dormand-Prince,
  explicit adaptive - the default, non-stiff workhorse) and `"bdf1"` (backward
  Euler, implicit L-stable - for stiff systems). It replaces the hand-rolled
  forward-Euler loops that had picked a timestep "small enough for the regimes we
  report" - an unjustified number by CLAUDE.md §1 - with a tolerance-driven,
  validated integrator. Method constants are cited in
  [`REFERENCES.md`](REFERENCES.md); the 5-point validation gate is
  `tests/test_ode_validation.py`.

## Why a core/ package

Issue [#35](https://github.com/noahhyden/von-neumann/issues/35) (Depth track
Tier 1, UQ) is explicitly a cross-cutting rollout: "then generalize the
interface across the other modules." That generalization lives here instead of
being duplicated per module.

The directory is called `core/` (not `uq-core/`) because more shared primitives
will land here as they appear - the seeded-RNG helpers, fold utilities, and
whatever else at least two modules end up wanting - each behind its own
`vn_core.<name>` subpackage. The naming leaves room for a future rust +
[pyo3](https://pyo3.rs) speed drop-in: `core/rust/` with pyo3 bindings that
`vn_core.uq` re-exports, so callers do not move imports when the fast path
lands. (Rust is not present yet - the marker is the layout, not a promise.)

## Discipline (still binding)

Everything here is a **pure fold with a seeded RNG threaded through** (CLAUDE.md
§7): deterministic across processes, no wall clock, no `Math.random()`. Pure
Python today; when the rust drop-in appears it inherits the same rule.

## Develop

```sh
uv run --extra dev pytest -q     # smoke tests
```

The comprehensive UQ tests live where the findings do (see
`probe-sim/tests/test_uq_*.py`); this package's own tests only prove the
package is importable and round-trips end-to-end.
