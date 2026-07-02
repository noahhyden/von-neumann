# Roadmap

The project has an architectural spine, not just a topic list. Each module is a
**pure fold** (a deterministic reduce over state — the model math) wrapped in a
**reactive skin** ([pimas](frontend/) memos that subscribe to the fold's outputs),
with **speculate** (exact, free-rollback what-if) on top.

The load-bearing word is **pure**: `speculate` is exact and rollback is free *only
because the fold is deterministic*. That criterion is the lens for every step below
— when a model stops being pure, the speculate leg needs care (see Design notes).

## Modules

### 0. `closure-sim` — the factory (done ✅)

Bill-of-materials closure ratio + discrete-time replication + the electronics wall.
The pure fold (`model.ts` / `closure_sim`) and the pattern (`reactive-model.ts`:
store + signals + memos + `speculate` + agent bridge) that everything else reuses.

### 1. `frontend` — the interactive surface (live ✅)

The monorepo's single pimas-only surface; a shell hosting one surface per model.
First surface: the electronics wall, live.

### 2. Single probe — next 🔜

**Source:** Borgue & Hein (2020), *Near-Term Self-replicating Probes — A Concept
Design*, [arXiv:2005.12303](https://arxiv.org/abs/2005.12303) (*Acta Astronautica*
2021).

A < 100 kg CubeSat-module-scale probe with **6 modules** (power, resource
harvesting/ISRU, replication via laser powder-bed AM, propulsion, control,
telemetry) that replicates **~70% of its mass**; the non-replicated **~30% is
microchips and complex electronics** brought along. Solar flux gates operational
**range** (1374 W/m² at Earth → ~50 W/m² at Jupiter → useless beyond the solar
system).

**Why it fits:** this is closure-sim's shape with an environmental gate — the fold
stays pure (`step(state, {distance, flux})` is deterministic), so `speculate` and
the agent bridge transfer nearly verbatim. The non-replicable 30% **is the
electronics wall again**, re-instantiated in a spacecraft. Likely closer to *a new
scenario + a few fields (modules, a `flux(distance)` term)* than a whole new module.

**Notes:** "vitamins" is our term, not the paper's (the concept — imported
electronics — is identical). Flux→*range* is stated; flux→*replication-rate* would
be our extrapolation.

### 3. Small deterministic multi-probe — intermediate 🔜

A handful of probes (tens, not 10⁵), deterministic. Validates the "probe-as-agent"
abstraction and keeps `speculate` exact *before* taking on the paradigm jump to a
stochastic spatial ABM and a performance engine at once. De-risks step 4.

### 4. The swarm — later 🔭

**Source:** Nicholson & Forgan (2013), *Slingshot Dynamics for Self-Replicating
Probes and the Effect on Exploration Timescales*,
[arXiv:1307.1648](https://arxiv.org/abs/1307.1648) (*Int. J. Astrobiology* 2013).

Agent-based Monte-Carlo over up to **200,000 stars**: per-probe next-star policies
(nearest powered / nearest slingshot / max-boost), gravitational slingshots,
replicate-in-transit from the ISM.

**Architecture:** a struct-of-arrays (SoA) typed-array **fixed-step + spatial-hash
core** for the hot loop; pimas is **only** a control/metrics skin. Do **not** put
fine-grained reactivity in the per-agent loop.

**The novel extension:** the source paper grants every probe **perfect,
instantaneous global information** — finite-light-speed coordination is explicitly
its *future work*, not implemented. So implementing **light-speed-limited
coordination** (probes deciding from stale, propagation-delayed local views, then
reconciling) is *new work*, not a port — and a natural fit for `speculate`
(evaluate a next-star choice against a probe's *believed* world) and `explain`
(provenance of a decision made on lagged info).

## Design notes

- **Purity / seeded determinism.** `speculate`'s exact-what-if + free-rollback needs
  a pure fold. The swarm is stochastic, so thread an explicit **seed** (as
  `frontend/scripts/gen-diff.mjs` already does): fix the seed → the fold is
  reproducible → `speculate` a *policy* change deterministically. `speculate` helps
  per-seed; ensemble statistics over seeds remain inherently many-runs. Since the
  base swarm assumes perfect global info, coordination is deterministic given a seed
  — light-speed lag is the *optional* layer added on top.
- **pimas' role narrows with scale.** speculate / agent-bridge / explain are most
  valuable in the small deterministic models (closure, probe) and least at raw swarm
  scale, where the value is the numerical SoA core (pimas contributes nothing to
  that hot loop). At swarm scale pimas is honestly the dashboard + policy-sweep
  control — real, but thin. Design accordingly.
- **Sequencing.** closure → probe is a small step (maybe scenario + fields). probe →
  swarm is a paradigm jump (deterministic BoM model → stochastic spatial ABM + a
  performance engine). The deterministic multi-probe step (3) exists to avoid taking
  both on at once.
