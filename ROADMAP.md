# Roadmap

The project has an architectural spine, not just a topic list. Each module is a
**pure fold** (a deterministic reduce over state - the model math) wrapped in a
**reactive skin** ([pimas](frontend/) memos that subscribe to the fold's outputs),
with **speculate** (exact, free-rollback what-if) on top.

The load-bearing word is **pure**: `speculate` is exact and rollback is free *only
because the fold is deterministic*. That criterion is the lens for every step below
- when a model stops being pure, the speculate leg needs care (see Design notes).

## Modules

### 0. `closure-sim` - the factory (done)

Bill-of-materials closure ratio + discrete-time replication + the electronics wall.
The pure fold (`model.ts` / `closure_sim`) and the pattern (`reactive-model.ts`:
store + signals + memos + `speculate` + agent bridge) that everything else reuses.

### 1. `frontend` - the interactive surface (live)

The monorepo's single pimas-only surface; a shell hosting one surface per model.
First surface: the electronics wall, live.

### 2. Single probe - in progress (`probe-sim/`)

**Started:** `probe-sim/` has the solar environment (inverse-square delivered power
vs heliocentric distance) and the operational-range computation (delivered power →
`closure-sim` replication → the distance where the probe stops reaching target
output), exercised on a synthetic fixture. A live **"Single probe" frontend surface**
already shows delivered power falling as 1/d² and the compute it affords. **Remaining
(blocked on external data):** instantiate the real per-module probe factory - this
needs real per-module probe masses, which are an unsourceable `[GAP]`; finishing it
with a guessed mass would violate §1, so it waits on a source, not on effort.

**Source:** Borgue & Hein (2020), *Near-Term Self-replicating Probes - A Concept
Design*, [arXiv:2005.12303](https://arxiv.org/abs/2005.12303) (*Acta Astronautica*
2021).

A < 100 kg CubeSat-module-scale probe with **6 modules** (power, resource
harvesting/ISRU, replication via laser powder-bed AM, propulsion, control,
telemetry) that replicates **~70% of its mass**; the non-replicated **~30% is
microchips and complex electronics** brought along. Solar flux gates operational
**range** (1374 W/m² at Earth → ~50 W/m² at Jupiter → useless beyond the solar
system).

**Why it fits:** this is closure-sim's shape with an environmental gate - the fold
stays pure (`step(state, {distance, flux})` is deterministic), so `speculate` and
the agent bridge transfer nearly verbatim. The non-replicable 30% **is the
electronics wall again**, re-instantiated in a spacecraft. Likely closer to *a new
scenario + a few fields (modules, a `flux(distance)` term)* than a whole new module.

**Notes:** "vitamins" is our term, not the paper's (the concept - imported
electronics - is identical). Flux→*range* is stated; flux→*replication-rate* would
be our extrapolation.

### 3. Small deterministic multi-probe - v1 model done (`multi-probe/`)

A handful of probes (tens, not 10⁵), deterministic. Validates the "probe-as-agent"
abstraction and keeps `speculate` exact *before* taking on the paradigm jump to a
stochastic spatial ABM and a performance engine at once. De-risks step 4.

**Built:** `multi-probe/` - a pure, seeded fold (`step`/`simulate_fleet`) where each
probe builds copies at `min(machinery rate, energy cap)` (closure-sim's regime logic,
reusing probe-sim's 1/d² power) and disperses children outward. Two emergent ceilings:
a finite **vitamin pool** (the electronics wall at fleet scale) and a **spatial power
wall** (~13.6 AU crossover). RNG is mulberry32 threaded through state (byte-identical
to `gen-diff.mjs`); jitter = 0 is deterministic and seed-independent. 11 behavior tests.
**Frontend:** a live "Fleet" surface - knobs + a 40-year day-scrubber over two charts
(fleet size, dispersal frontier) + a final-fleet distance scatter; parity-tested TS
port with the mulberry32 RNG matching the Python bit-for-bit. **Remaining:** swapping in
a probe-specific BOM once the mass `[GAP]` is closed.

### 3b. `mission` - the whole operation, end to end (done)

Not a planned module - an **integration** that emerged once 0–3 existed. One pure fold
(`run_mission`) composes launch-economics → closure-sim → probe-sim → replication →
payoff: launch a seed, arrive at a heliocentric distance, split solar power between
building and thinking, replicate, price the launch-mass leverage. Reconciles the seams
between modules (seed mass from the factory; power split decided once). A live **"Full
mission" surface** follows the chain stage by stage. Uses the lunar-regolith factory as
a stand-in (the probe-BOM `[GAP]` above persists here too).

### 3c. `spine` - one factory across all three scales (done)

Where `mission` composes the *single-probe* modules, `spine` composes across **scale**:
it threads one `closure-sim` factory through the single-factory fold, the local fleet
(`multi-probe`), and the galaxy (`swarm`), so their replication cadences are **derived
from one source** rather than assumed independently at each scale. Its headline
contribution closes a real seam: the swarm's per-star **manufacturing dwell**
(`settle_time_years` - time to build offspring before they depart) was an ungrounded
`[ESTIMATE]` defaulted to **0.0** (instantaneous replication). `spine` *derives* it from
the same build physics the fleet uses (`multi_probe.time_to_build_one_copy_days` at 1 AU)
- no new number, just a quantity the factory already fixes, routed to the scale that was
guessing it. **Finding:** the derived copy time (~582 d for the lunar seed) *is* the
fleet's doubling clock, yet is ~8e-7 of a ~2e6-yr powered galactic fill - interstellar
transit dominates, so the manufacturing cadence that governs a local fleet is a negligible
tax on exploration (measured A/B: ~0.4% for fast slingshots, ordered by probe speed). This
is the cross-scale answer to *which constraint binds at which scale*, which no single
module could give. Pure fold, zero pimas imports; adds no new physics (`spine/REFERENCES.md`).

### 4. The swarm - core + slingshots + light-speed coordination done (`swarm/`)

**Source:** Nicholson & Forgan (2013), *Slingshot Dynamics for Self-Replicating
Probes and the Effect on Exploration Timescales*,
[arXiv:1307.1648](https://arxiv.org/abs/1307.1648) (*Int. J. Astrobiology* 2013).

**Built (slice 1 - the fold + surface):** `swarm/` - the pure, seeded, fixed-step
algorithm core. Probes spread star-to-star through a seeded field (uniform 1 star/pc³,
the paper's density), settling the nearest unsettled star at the paper's powered speed
(3e-5c ≈ 9 km/s) and launching offspring; reports the exploration timescale (50/90/100%)
and the settlement-front radius. The front advances at ~40% of probe speed (nearest-hop
zig-zag + settling). SoA-style state, mulberry32 RNG (byte-identical to the other
modules). A live **"Swarm" frontend surface** renders the front on a `<canvas>`
(play/scrub the fill, reseed) - one canvas + a single effect reading the fold's buffers,
no node-per-star (§7); parity-tested TS port.

**Built (slice 2 - slingshots):** the paper's three next-star policies - **powered**,
**slingshot-nearest**, **slingshot-max-boost** - with the gravitational boost from
N&F Eq. 4 (u_esc ≈ 617.5 km/s solar, derived) and per-star galactic velocities
([ESTIMATE], the paper defers these). Reproduces the paper's findings: slingshots ≫
powered, and **nearest-star beats max-boost on time**. Live 3-way policy toggle +
peak-speed readout on the surface; parity-tested.

**Built (slice - the spatial hash):** a uniform-grid nearest-unsettled search, proven
**bit-identical to brute force** and scaling the fill to 8k+ stars. (This is half of the
original "scale" slice - the algorithm side. The 200k render side is the WebGL fork below.)

**Built (bonus - the coordination-horizon viz):** a teaching overlay (not in the
original plan) that turns each link's light-lag into a coordination "rung" (ρ = round-trip
latency ÷ decision timescale). Hover a star → its distance, light-time, ρ, and mode
(real-time → move-and-wait → supervisory → delay-tolerant → independent colonies).
Sourced (Olfati-Saber & Murray 2004; Ferrell 1965; RFC 4838). This is the *visualization*
of the coordination problem; the *simulation* of it is the next slice.

**Built (slice - light-speed-limited coordination) ([FRONTIER issue #1](https://github.com/noahhyden/von-neumann/issues/1)):**
the paper's explicit *future work*, now implemented. A `coordination: "instant" | "lightspeed"`
param and a light-cone belief predicate - a decider at a star knows a distant star is settled
only once the news-light has arrived (`settled_year + dist/c ≤ now`). Target selection reads
*belief*, physical arrival reads *truth*, so probes race for the same star from stale views and
waste trips. `"instant"` collapses to perfect info, bit-identical to the slices above (the c→∞
keystone). Python + parity-tested TS port + a live "Perfect info | Light-speed lag" toggle with a
"Slowdown vs perfect info" readout. **Finding** (32-seed paired ensemble,
`swarm/experiments/lightspeed_coordination.py`): lag costs a median **~30% (nearest-slingshot),
~50% (max-boost), ~0% (powered)** of the exploration timescale - `Λ ≈ v/c` sets the scale, hop
non-locality decides whether it bites. A connected field still fills to 100% (no Aurora plateau
from lag alone). See swarm/REFERENCES.md.

**Remaining - one parked fork + deferred siblings (need an explicit go, not ordinary backlog):**

1. **200k-star scale - the render engine.** The spatial-hash algorithm already scales;
   what's missing is drawing 10⁵ stars at 60 fps. Canvas 2D tops out ~10⁴, so this is a
   canvas→**WebGL instanced-draw** fork (typed-array SoA → vertex buffer). A design
   decision, deferred until wanted. (The 860M iGPU is confirmed capable; at 200k the *sim*
   becomes the bottleneck before rendering.)
2. **Coordination siblings** (deferred, built on the light-speed slice above): probe-to-probe
   **gossip relay** + mid-flight learning (v1 uses decision-site knowledge only, a conservative
   bound); a settlement **death term** → the Aurora steady-state `X_eq = 1 − T_l/T_s < 1`; and a
   **min-heap** arrival index for the 200k scale.

The rest of this section is the original design notes for the coordination simulation (now built)
and the WebGL fork.

Agent-based Monte-Carlo over up to **200,000 stars**: per-probe next-star policies
(nearest powered / nearest slingshot / max-boost), gravitational slingshots,
replicate-in-transit from the ISM.

**Architecture:** a struct-of-arrays (SoA) typed-array **fixed-step + spatial-hash
core** for the hot loop; pimas is **only** a control/metrics skin. Do **not** put
fine-grained reactivity in the per-agent loop.

**The novel extension:** the source paper grants every probe **perfect,
instantaneous global information** - finite-light-speed coordination is explicitly
its *future work*, not implemented. So implementing **light-speed-limited
coordination** (probes deciding from stale, propagation-delayed local views, then
reconciling) is *new work*, not a port - and a natural fit for `speculate`
(evaluate a next-star choice against a probe's *believed* world) and `explain`
(provenance of a decision made on lagged info).

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
- **Sequencing.** closure → probe is a small step (maybe scenario + fields). probe →
  swarm is a paradigm jump (deterministic BoM model → stochastic spatial ABM + a
  performance engine). The deterministic multi-probe step (3) exists to avoid taking
  both on at once.

## Depth tracks (cross-cutting)

The modules above answer the physics question. These tracks cut *across* all of them
and each one buys the project a specific correctness or performance gain while also
being a deep, transferable fundamental. They are ranked and sequenced deliberately -
not written as six peers - because §3 is binding here too: **depth is a liability**,
and a flat wish-list of six parallel efforts is exactly the trap it warns against.
Each track is scored on two axes that do *not* coincide: **(a)** does it make the
papers more correct or more publishable, and **(b)** does it teach a fundamental. We
let (a) drive the ordering and refuse to let (b) smuggle in work (a) would not
justify.

### Tier 1 - these *complete* the rigor, so they are research, not extras

**UQ: error bars + sensitivity.** Every number in the repo is sourced but
point-valued. Propagating that uncertainty (Monte Carlo, or analytic where the model
is linear) and running a global sensitivity analysis (Sobol indices) is the honest
completion of the cardinal rule: it turns "X" into "X, ±Y, and Y is 80% driven by
this one input." Highest leverage for the papers, and it upgrades every module at
once. Three things to hold in view:
- The real cost is **not** the Monte Carlo, it is that every entry in every
  `REFERENCES.md` now needs a **distribution, not just a source** - a spread is a
  citable claim in its own right, and this is a sourcing project across all modules
  before it is a compute project.
- Sobol needs many model evaluations; cheap for most modules, a design constraint for
  any that are not.
- **UQ is a filter, not polish.** Some current findings' error bars will straddle
  their threshold and collapse into honest nulls. That is a feature, not a failure -
  it is the same "proven null over unproven claim" discipline the papers already
  hold. Frame UQ as "find out which findings survive," not "add error bars."

**Explicit optimization: make the implicit LP visible.** Several modules currently
solve constrained-optimization problems by hand-tuning (splitting a solar-power budget
across manufacturing / compute / housekeeping to maximise replication; the minimum
import set for closure). Reframed as proper programs, the **dual / shadow prices**
tell you *which constraint binds and by how much* - the "electronics wall" framing is
informal shadow-price reasoning, made rigorous and publishable. The power-budget side
is linear/convex duality; the closure side ("minimum imports for self-replication"
over the bill-of-materials dependency graph) is a min-hitting-set / ILP problem, the
exact gap the O(N!)-query incident exposed - so the algorithms/complexity work is not
a bonus, it is half of this track. Caveats:
- **Check the structure before promising duality.** Replication rate vs. watts is
  probably nonlinear (thresholds, diminishing returns). If it is convex the shadow
  prices are still clean; if nonconvex they are only local, and the "it *is* LP
  duality" claim has to soften to match.
- Watch the §3 tension: a solver can *hide* physics behind an optimum. The win here is
  the interpretation (which constraint binds), not the optimum itself.

### Tier 2 - mostly done; rescope, do not restart

**Swarm performance + GPU.** The premise that the swarm is "a CPU spatial-hash at
~4,800 stars" is **stale**: the module already runs at **200k stars** on a dynamic
k-d tree over the unsettled set with a near-linear event loop (issues #27, #30), and
has already produced a finding (the coordination tax at 200k). The CPU-depth
curriculum largely happened. What is genuinely open:
- WebGPU **rendering / fill** and the parked frontend engine - squarely the §Design
  notes ladder (Canvas 2D → WebGL instanced → WebGPU compute), rendering reading the
  fold's flat buffers, never a reactive scene graph.
- **Red flag on moving the *fold itself* to the GPU.** §7 makes determinism binding
  and `docs/HARDWARE.md` leans on it ("folds are deterministic, so hardware never
  changes a result"). Cross-GPU floating-point determinism is hard; a GPU fold could
  silently break replay and `speculate`. Scope GPU to the **skin** (rendering) and
  keep the deterministic seeded fold on the CPU - or treat "deterministic GPU fold" as
  its own large, explicitly-flagged project, not a free byproduct of the render work.

### Tier 3 - learning-only, NOT on the paper critical path

These are worth doing for their own sake, but neither is justified by (a) today, so
they are parked here honestly rather than dressed up as research. Each has a cheap
near-term substitute that captures most of the value.

- **Physical units as types.** The dream ("every number sourced" becomes "every
  number dimensioned by the compiler") is beautiful and exactly the repo's ethos, but
  a compile-time units DSL is a **mini-compiler** - a large standalone build with zero
  research output and a new single-maintainer surface (the same burden as pimas).
  **Near-term substitute:** adopt runtime dimensional analysis (e.g. `astropy.units`,
  already plausible in this domain) now - it catches "cannot add mass to energy" and
  forgotten conversions immediately, at a fraction of the cost. The DSL stays a pure
  learning project for later.
- **Numerical methods (RK4 / symplectic integrators).** Classic and worth knowing, but
  gate it on §3: **does any finding actually depend on integrator accuracy?**
  Symplectic integrators earn their keep only over long horizons where energy drift
  would corrupt a result. If orbital mechanics is incidental to a module's question,
  higher-fidelity integration is precisely the "process nested in a process" §3 warns
  against. Trigger this track from an observed drift in a real result, not from
  curiosity.
