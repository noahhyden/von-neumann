# core - shared primitives across the von-neumann monorepo

Distributed as the `vn-core` package (Python name `vn_core`). Currently holds:

- **`vn_core.uq`** - uncertainty quantification. Distributions (`Fixed`, `Uniform`,
  `Normal`, `LogNormal`), seeded Monte Carlo, Sobol total-order sensitivity, a
  paper-ready one-line reporter. Every von-neumann module reaches for this so
  no one re-implements the RNG discipline or the propagation loop.

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
