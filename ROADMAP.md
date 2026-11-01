# Roadmap

The project has an architectural spine, not just a topic list. Each module is a
**pure fold** (a deterministic reduce over state - the model math) wrapped in a
**reactive skin** ([pimas](frontend/) memos that subscribe to the fold's outputs),
with **speculate** (exact, free-rollback what-if) on top.

The load-bearing word is **pure**: `speculate` is exact and rollback is free *only
because the fold is deterministic*. That criterion is the lens for every step below
- when a model stops being pure, the speculate leg needs care (see Design notes).


## Modules

Every top-level module directory is built and owns its status in its own `README.md` and
`REFERENCES.md`; the CI module matrix in `.github/workflows/ci.yml` is the live list. This
file does not track per-module status, because that rots. `frontend/` is the single
pimas-only surface; `modules/core/` (vn_core) holds the shared linalg, ode, rng and uq code.

## Design notes

- **Purity / seeded determinism.** `speculate`'s exact-what-if + free-rollback needs
  a pure fold. The swarm is stochastic, so thread an explicit **seed** (as
  `frontend/scripts/gen-diff.mjs` already does): fix the seed → the fold is
  reproducible → `speculate` a *policy* change deterministically. `speculate` helps
  per-seed; ensemble statistics over seeds remain inherently many-runs. Since the
  base swarm assumes perfect global info, coordination is deterministic given a seed
  - light-speed lag is the *optional* layer added on top.

- **Determinism has depth - "fix the seed" is necessary, not sufficient.** Three
  things break bit-exact reproducibility (and therefore `speculate` and replay), all
  learned the hard way by deterministic sims like Factorio and Egregoria:
  1. **RNG must be threaded state, not ambient.** Shape the tick as
     `step(state, dt, rng) → {state, rng}` with a small seeded, splittable generator
     (PCG / splitmix / xoshiro) carried *in the state*. Never `Math.random()`, never a
     wall clock. This makes `speculate` fork the future exactly and gives free
     Monte-Carlo (N seeds → a distribution). *The sneakiest bug in the whole project:
     `Math.random()` in a fold works until an agent asks "what-if" and gets a
     non-reproducible answer.*
  2. **Iteration order must be deterministic.** Ordered containers, not hash
     sets/maps, anywhere order affects results; sort before any parallel reduction.
  3. **Float non-determinism is real** across platforms/builds (FMA, fast-math
     reordering: `(v·dt)+(v·dt) ≠ v·2dt`). If cross-machine reproducibility ever
     matters, use a fixed timestep and either fixed-point or our own deterministic
     transcendental functions - don't discover this at swarm scale.

- **speculate at scale forks the *fold*, not `pimas/store`.** For small models a
  what-if is a signal/store write that `speculate` shadows in a `Map` - perfect. At
  swarm scale, don't try to copy-on-write thousands of entity cells through the store
  (that turns a reactive engine into a database). Instead the fold owns its own
  structural sharing (a persistent/immutable state structure if memory demands it),
  and `speculate` shadows the *one* signal holding the swarm-state handle - the fold
  produces a new state from the old, which it already does (`step(s)→s'`). pimas stays
  the thin what-if *orchestrator*, exactly as in `frontend`. The one legitimate future
  *core* change is letting `speculate` **nest/fork** (it currently forbids nesting), so
  an agent can plan a *tree* of what-ifs - deferred until an agent actually needs it.

- **Rendering is the biggest new build at swarm scale - and it lives in `frontend`,
  not pimas.** Fine-grained DOM (a node per entity) dies in the low thousands. The
  ladder is ~10× per rung: Canvas 2D (~10⁴) → WebGL instanced (~10⁵) → WebGPU compute
  (10⁶+). The clean boundary: the sim core owns state in flat typed arrays and knows
  nothing about rendering; the render layer **reads those buffers each frame** and
  uploads them, and is driven by a **single `createEffect`** over camera/selection/
  tick signals. Do **not** implement it as a canvas `RenderBackend` (that seam is a
  retained-node/DOM contract; canvas is immediate-mode - you'd rebuild a scene graph
  just to satisfy it) and do **not** build a reactive scene graph (it reintroduces
  per-node cost in the paint layer). One `<canvas>` hosted by pimas + a plain
  `SwarmView.draw(state, camera)` is the whole design.

- **Keep it out of pimas' core.** pimas *describes and observes*; it does not
  simulate, store-at-scale, or render-at-scale. The tick loop, sim-clock, SoA state,
  RNG, spatial index, persistence, and per-entity drawing all live here in `frontend`
  (userland), never in the kernel. The test for anything proposed for pimas itself:
  *would noahhyden.com's static build pay for it?* If a byte lands in the indivisible
  kernel, it's wrong - use a subpath (`pimas/agent` etc.) or keep it here. A ~10–30 Hz
  **sampler** (snapshot sim → coarse reactive store at UI rate, not tick rate) and
  delta-**coalescing** in the agent bridge are the two things that keep the reactive
  skin cheap when the fold ticks fast.
- **pimas' role narrows with scale.** speculate / agent-bridge / explain are most
  valuable in the small deterministic models (closure, probe) and least at raw swarm
  scale, where the value is the numerical SoA core (pimas contributes nothing to
  that hot loop). At swarm scale pimas is honestly the dashboard + policy-sweep
  control - real, but thin. Design accordingly.

## Depth tracks (cross-cutting)

These cut across all modules and are ordered by whether they make the papers more
correct, not by what is fun to learn; §3 (depth is a liability) applies to them too.

- **UQ: error bars + sensitivity (done, issue #35 closed).** `vn_core.uq` plus a
  `distributions.py` per module. UQ is a filter: findings whose error bars straddle
  their threshold become honest nulls.
- **Explicit optimization.** Reframe the implicit constrained problems (power split,
  minimum import set) as programs so shadow prices show which constraint binds. Check
  convexity before claiming LP duality; a solver must not hide physics behind an optimum.
- **Swarm GPU.** Scope GPU to the rendering skin (Canvas 2D to WebGL instanced to WebGPU).
  Keep the seeded fold on the CPU: cross-GPU float determinism would break replay and
  `speculate`.
- **Learning-only, off the paper critical path.** Physical units as types (substitute:
  runtime dimensional analysis) and RK4/symplectic integrators (only if a finding depends
  on integrator accuracy).
