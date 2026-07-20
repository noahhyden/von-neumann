# core - shared primitives across the von-neumann monorepo

Distributed as the `vn-core` package (Python name `vn_core`). Currently holds:

- **`vn_core.rng`** - the shared seeded mulberry32, threaded through the fold
  (CLAUDE.md §7). `next_u32`, `next_float`, `seed_state`. Extracted from
  `swarm/rng.py` and `multi_probe/rng.py` under issue
  [#29](https://github.com/noahhyden/von-neumann/issues/29) once the second
  consumer (multi-probe) confirmed the "extract on second consumer" trigger had
  fired. Both modules now re-export from here, so there is one Python source
  of truth for the mulberry32. Byte-identical to the mulberry32 in
  `frontend/src/swarm.ts`, `frontend/src/multi-probe.ts`, and
  `frontend/scripts/gen-diff.mjs`; that JS parity is pinned by a committed
  fixture (`tests/rng_js_fixture/`), so a drift in either language is a test
  failure and not a downstream simulation puzzle. Reliability uses a distinct
  64-bit generator (`splitmix64`) because it has no JS-parity surface and a
  wider generator is defensible there; the two share the ``(value,
  new_state)`` threading contract but not the algorithm (issue
  [#65](https://github.com/noahhyden/von-neumann/issues/65)). A third
  generator would fire the same "second-consumer" trigger.
- **`vn_core.uq`** - uncertainty quantification. Distributions (`Fixed`, `Uniform`,
  `Normal`, `LogNormal`), seeded Monte Carlo, Sobol first- and total-order
  sensitivity (each with a confidence interval, so an index that is within noise
  reads as a CI straddling zero rather than a false-confident number), a
  paper-ready one-line reporter. `uq_and_gsa` runs both propagation and sensitivity
  off one Saltelli design (the UQ is free from the Sobol evaluations). `pce_fit`
  is a polynomial-chaos surrogate for **smooth** findings: it
  returns the moments, closed-form Sobol indices, and a cheap `predict()` surrogate
  in far fewer model evaluations than Monte Carlo (`method="quadrature"` in low
  dimension, `method="regression"` - least squares, ~2*n_terms runs - when the
  input count would make tensor quadrature explode; Uniform/Normal use the exact
  Askey families, any other distribution uses arbitrary PCE built from its
  moments), and carries a `fit_residual`
  that flags non-smooth findings so it never silently lies (fall back to
  `monte_carlo`/`uq_and_gsa` there). Two variance-reduction mean estimators sit
  alongside for when the mean is the headline number: `qmc_mean` (randomized
  quasi-Monte Carlo - ~1/N convergence for smooth low-dim findings, with an honest
  error bar from replicate spread) and `pce_control_variate` (PCE as a control
  variate - an unbiased mean with far lower variance, and it stays honest even
  where PCE alone is untrustworthy). Both variance-reduction paths and the Saltelli
  sensitivity design draw their base points from `vn_core.uq.sequences` - a shared
  source of deterministic low-discrepancy sequences (`halton_point`, `sobol_points`).
  The Sobol' points are built from the Joe-Kuo direction numbers and pinned
  bit-identical to `scipy.stats.qmc.Sobol` by a committed oracle test, so the
  quasi-random sampler is verified against the reference rather than hand-rolled.
  Every von-neumann module reaches for this so no one re-implements the RNG
  discipline or the propagation loop.
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
uv run --extra dev pytest -q                        # the test suite
uv run --extra dev coverage run -m pytest && \
  uv run --extra dev coverage report                # + the 100% coverage gate
```

The package holds at **100% line+branch coverage**, enforced in CI (the `core` job
in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) via `fail_under = 100`
in `pyproject.toml`. The comprehensive downstream UQ tests still live where the
findings do (see `probe-sim/tests/test_uq_*.py`); the tests here validate each
primitive directly - RNG JS-parity, ODE vs scipy, Sobol' vs scipy, PCE vs analytic -
and pin bit-reproducible golden values.

## Deferred (Tier 3 roadmap options, intentionally not built)

Per CLAUDE.md §3 (don't build the elaborate path before it is justified) and the
repo's "extract/add on the second consumer" rule, these have a clear design but no
firing consumer yet, so they are documented rather than shipped:

- **Owen-scrambled QMC** - a stronger randomization than the Cranley-Patterson shift
  `qmc_mean` uses today. Current randomization already gives an honest error bar; Owen
  is a refinement to add when a finding needs it.
- **More distributions** (Beta, Gamma, Triangular, Truncated Normal) - trivial to add
  behind `Distribution.quantile`, but gated on a real consumer so the surface does not
  grow unused.
- **Lanczos recurrence for arbitrary PCE** - an alternative to the discretized
  Stieltjes procedure for robustness on ill-conditioned moment problems; the current
  route is validated and sufficient for the distributions in use.
