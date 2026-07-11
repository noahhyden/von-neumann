# von-neumann - operating rules

A modular, physics-heavy exploration of self-replicating space manufacturing. This
file is binding for all work in this repo. Read it before changing anything.

The work fails quietly: it is processes inside processes, many interacting parts,
and real-world noise. A single unsourced number or unvalidated step compounds into
confident nonsense. The rules below exist to stop that. They cost a little speed and
buy correctness - that trade is always worth it here.

---

## 1. The cardinal rule: no number may be assumed

**If a number has no source, the number is wrong** - not "rough," not "a reasonable
placeholder." Wrong. This applies to every quantity: masses, energies, rates,
efficiencies, durations, costs, fractions, thresholds.

- **Every number traces to a citable source, or is derived by explicit math from
  numbers that do.** Deriving is encouraged - show the formula and cite each input.
  (e.g. `energy_cap = power / e_local`, where `power` cites [X] and `e_local` is
  computed from per-part figures that each cite a source.)
- **Never invent, guess, round-to-a-vibe, or "assume for now."** If you catch
  yourself writing a number you can't point at, stop and find the source first.
- **Document the number where it lives.** Each module has a `REFERENCES.md` mapping
  value → source (URL) → a verdict on whether it's reasonable. A number that appears
  in code or a scenario file with no matching reference entry is a bug, full stop.
- **Units are always explicit, and conversions are shown.** (1 kWh = 3.6 MJ, etc.)
  A bare number with no unit is incomplete.
- **State the measurement basis when it's ambiguous.** The same thing can differ by
  orders of magnitude depending on basis (e.g. chip energy per bare die vs. per
  packaged part). Pin and document which basis you used.

### When a number genuinely doesn't exist (a real gap)

Sometimes the literature simply has no value. That is a finding, not a license to
make one up.

- **Surface it explicitly.** Mark it `[GAP]` in `REFERENCES.md` and as an inline
  comment at the use site. Never let an estimate pass as a measured fact.
- **Then find the best defensible estimate:** derive a bound, use a documented proxy
  or analogous system, or interpolate from neighbours - and cite whatever partial
  evidence informs it. Tag the result `[ESTIMATE]` and write one line on the
  reasoning and its uncertainty.
- A `[GAP]`/`[ESTIMATE]` is honest; an unmarked guess is not.

---

## 2. Scope every step. Validate before moving on.

- **Define scope before writing.** For each step, state what it covers, what it
  explicitly does *not*, and how you'll know it's correct. If you can't state that,
  the step isn't ready.
- **No new feature without a validation test.** Validation can be simple - a short
  Python script that runs the flow **end to end** and asserts the result *behaves
  correctly*, not merely that it ran without error.
- **Assert on behavior and edges, not execution.** Check real numbers and the
  regimes that matter, including boundary cases (e.g. closure = 1.0, resupply = 0,
  energy-limited). "It didn't crash" is not validation.
- **If you can't validate it simply, the scope is too big.** Shrink it until you can.
- Keep a fast `pytest` suite green at all times; an end-to-end script may live
  alongside it for whole-flow checks.

---

## 3. Ground everything in physics - but don't over-nest

This is physics-heavy. Grounding is not optional.

- **Respect conservation and realism.** Mass and energy balance; efficiencies,
  material properties, and process parameters must be physically plausible. A model
  that violates physics is wrong even when it runs and the tests pass.
- **Include real-world messiness where it matters** - external factors and
  variability enter as *noise or parameters*. They must be present (the system is
  not frictionless) but must not become new subsystems.
- **Do not nest processes within processes more deeply than the question needs.**
  This is the counterweight to grounding. Each module models one slice. Prefer a
  documented parameter over an elaborate sub-simulation until the sub-simulation is
  actually justified *and* separately validated.
- **When tempted to add another layer of nested simulation, stop and ask:** does
  this belong as a parameter, or as a *sibling module* with a clean interface,
  rather than fused into this one? Depth is a liability; seams are an asset.

---

## 4. Module hygiene (monorepo)

- **One module = one directory** with its own README, dependencies, tests, and
  `REFERENCES.md`. Independently runnable.
- Modules share concepts and data through **clean interfaces**, never by reaching
  into each other's internals. Leave seams for the modules still to come.
- **`frontend` is the one shared surface, and it is pimas-only.** The repo's single
  interactive/presentation layer lives in `frontend/` - a shell that hosts *one
  surface per model* rather than fusing them (each model still owns its slice; the
  frontend just presents it). It, and any interactive code in this repo, must use
  [pimas](https://github.com/noahhyden/pimas) as its reactive framework - signals, memos, store, JSX (via
  `jsxImportSource: "pimas"`), flow control, and the agent bridge. Do **not**
  introduce React, SolidJS, Vue, Svelte, or any other reactive/UI framework. Plain
  DOM and build-only tooling (esbuild) are fine; a competing reactive runtime is not.
- **Plain language.** This work is shared with non-specialists - explain the "why"
  in words, not only in code and equations.

---

## 5. Practical conventions

- Python 3.12, typed (pydantic v2 / dataclasses), minimal dependencies.
- `uv` for environments; `pytest` with real assertions.
- **Typography: no em-dash (U+2014) and no emoji, anywhere in the repo.** Use a
  plain ASCII hyphen `-` in place of any em-dash. This is binding for code,
  comments, Markdown, `REFERENCES.md`, and every UI string on the public frontend
  alike - it keeps text portable, diff-clean, and free of decorative noise in a
  project whose output is meant to be read as research. Math and astronomy symbols
  (Greek letters, `≈`, `≫`, `²`, `☉`, arrows) are not emoji and are fine where they
  carry meaning.
- **Git:** commit or push only when asked. The repo is **private** at
  `noahhyden/von-neumann`. **Never push to `Klarum-Software`** (or anywhere else).
- New numbers in a change → update that module's `REFERENCES.md` in the same change.
- **Compute hardware is inventoried in [`docs/HARDWARE.md`](docs/HARDWARE.md).** Consult
  it whenever you reason about run time, parallelism, or what a machine can handle, and
  update it when the hardware stack changes (new machine, GPU, cloud ensemble). It is a
  wall-clock aid only: the folds are deterministic (§7), so hardware never changes a
  result - which is exactly why the specs live in one shared place, not baked into code.

---

## 6. pimas is first-party and single-maintainer

pimas (`https://github.com/noahhyden/pimas`, consumed from npm as
[`pimas-ui`](https://www.npmjs.com/package/pimas-ui) - aliased to the bare `pimas`
specifier in `frontend/package.json`) is our own reactive framework, built and - for
the foreseeable future - solely maintained by the repo owner. It is a dependency we
*control*, not a stable third-party package. Practical implications:

- **Things may break or not work out-of-the-box.** If a frontend problem traces to
  **pimas itself** (a framework bug or missing capability), **do not build a
  workaround around it** - stop and flag it so it gets fixed in the pimas repo. Only
  work around issues that are genuinely in this repo's own code. When flagging,
  distinguish clearly: is the failure our code, or verified framework breakage?
- **Layered tests make that distinction decidable at the pinned version.**
  `frontend`'s tests are layered by blame surface: **Layer A** (`npm test`) is the
  pure model with no pimas - a failure is *our* logic; **Layer B** (`npm run
  test:contract`) exercises only pimas primitives against the exact `pimas-ui`
  version the lockfile pins - with A green and our tree unchanged, a Layer B failure
  is **pimas**. Version pinning lives in `frontend/package.json` and the lockfile;
  bumping pimas is a deliberate `npm update pimas` step, and Layer A/B rerun on that
  bump in CI. When Layer B fails after a bump, that's verified framework breakage -
  flag it in pimas, don't work around it here.

---

## 7. Architecture is binding: pure fold, reactive skin, speculate

Every model has the same shape, and it is not optional - it is what makes
`speculate` exact, rollback free, and replay reproducible, and what keeps pimas' core
tiny. See [ROADMAP.md](ROADMAP.md) for the full rationale.

- **The model is a pure fold.** The math is a deterministic `step(state, dt, rng) →
  {state, rng}` (or a one-shot `simulate()`), in plain data, with **zero pimas
  imports** - framework-agnostic, serializable, independently testable (Layer A). It
  does not know pimas, the DOM, or rendering exist.
- **Randomness is seeded state, threaded through the fold.** Never `Math.random()`,
  never a wall clock. Use a small seeded generator carried in the state. Keep
  iteration order deterministic (ordered containers, not hash sets). This is the one
  discipline that silently breaks everything downstream if ignored - a `Math.random()`
  in a fold *works* until someone asks it to reproduce or `speculate`.
- **pimas is the skin, never the loop.** Signals for the knobs, memos for aggregates
  and selection, `speculate` + the agent bridge for what-if and provenance. **Never a
  signal/store-node per entity; never fine-grained reactivity in the per-entity /
  per-tick loop.** The reactive graph scales with what a human or agent *looks at*,
  not with entity count.
- **Rendering reads the fold's buffers; it never owns state.** At scale, one
  `<canvas>` + a plain draw loop driven by a single effect - not a DOM node per
  entity, not a reactive scene graph, not a canvas `RenderBackend`.
- **Nothing simulation-shaped enters pimas itself.** The tick loop, clock, state
  storage, RNG, spatial index, persistence, and drawing live here. If a change seems
  to need a pimas core feature, that's a §6 flag, not a local workaround - and the bar
  is high (would noahhyden.com's static build pay for it?).

## The one-line test before you commit

> Can I point at a source for every number, did a simple end-to-end check confirm
> the flow behaves correctly, is the model grounded in physics without burying the
> logic under needless nesting, and is it a **pure, seeded, deterministic fold with
> pimas only as its skin** (§7)?

If any answer is no, it's not done.
