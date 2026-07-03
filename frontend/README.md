# frontend - von-neumann's interactive surface

This is the monorepo's **central frontend**: the place where von-neumann's models
run live in the browser, built entirely on [**pimas**](../../pimas) (the repo rule
is pimas-only - no other reactive framework; see [`../CLAUDE.md`](../CLAUDE.md)).
The reactive core runs the model *and* renders the page.

It is organized as a **shell that hosts one surface per model**, so each module
keeps its own slice - the frontend just presents them. As `power-budget`,
`launch-economics`, and the rest arrive, each gets its own surface here; they don't
fuse into one giant simulation.

## Surfaces

### Overview - the front page

The landing surface: a plain-language explanation of what the project is, its
methodology (every number sourced, gaps marked not guessed), and a live per-module
roadmap status (which of the seven modules are done, which are in progress, and the
known open gaps). Click any module row to open its surface.

### Sources - the bibliography

The project-wide bibliography, consolidated from every module's `REFERENCES.md` into
one page: every source, a link where one exists, the specific quantity it grounds, and
a strength tag (peer-reviewed vs vendor vs wiki cross-check). The data lives in the
pure, tested [`src/sources.ts`](src/sources.ts); an inline `Cite` marker on figures
across the other surfaces reveals the exact paper on hover or keyboard focus.

### Full mission (`mission`) - live

The flagship end-to-end surface (first in the nav). It runs the **whole operation as
one pure fold** over all four models: launch a seed, fly it to a heliocentric
distance, split its solar power between building and thinking, replicate, and price
the launch-mass payoff. Drag the five knobs - or jump to a destination (Earth orbit,
Mars, the belt, Jupiter, deep space) - and the entire six-stage chain recomputes,
including a plain-language verdict on whether the operation *succeeds* at that distance
and split. Move the probe far enough out and it visibly starves: the manufacturing
share of the inverse-square power drops below what replication needs, and the factory
never reaches target. Composes the parity-tested `mission.ts` port (itself a
composition of the other four ports); reactive via signals + one memo (no
store/speculate - the fold is cheap to re-run on every drag).

### The swarm (`swarm`) - live

A settlement front filling a galaxy, live **on a canvas**: press **play** and watch the
reachable star field light up from one homeworld as probes settle and re-launch; drag
the knobs (star count, offspring, probe speed) and reseed the galaxy. The canvas reads
the fold's per-star settlement buffers each frame and redraws - one `<canvas>` + a
single effect, **never a DOM node per star** (the rendering discipline that scales,
§7). Deterministic: same seed, same spread, every run (mulberry32 byte-identical to the
Python). Toggle between the three travel policies (powered and two gravitational
slingshots), switch **perfect info vs light-speed lag** (probes decide from stale,
light-delayed views and race for the same star, with a live "slowdown vs perfect info"
readout), and hover any star to read its coordination lag from home. Parity-tested TS
port of `swarm`; the one remaining slice is the 200k-star WebGL render engine.

### The fleet (`multi-probe`) - live

A small, **deterministic, seeded** fleet running live: one probe copies itself, the
copies disperse outward and copy again. Drag the knobs (start distance, vitamin pool,
dispersal, fleet cap, transit time + jitter) and **scrub through the 40-year mission**
to watch two charts move - fleet size (cyan) and the dispersal frontier in AU (amber) -
plus a scatter of where every probe ends up along the Sun→distance axis. The two
ceilings from the earlier modules reappear: a finite vitamin pool (the electronics wall
at fleet scale) and 1/d² power vs dispersal (the spatial power wall). The RNG is
mulberry32 threaded through the fold - byte-identical to the Python - so it replays
bit-for-bit: same seed, same fleet. Parity-tested TS port of `multi-probe`.

### The electronics wall (`closure-sim`) - live

`closure-sim`'s "electronics wall" essay began life as a static page - but its
headline chart was a *hand-faked* curve (`Math.pow(t, 2.4)`) and its results were
hard-coded strings (`~29 years`, `~17 years`, `never`). This surface **is** that
essay now - the **real model, running live**: drag the assumptions and the
simulation recomputes; preview "make its own chips" as a *speculation* - the exact
after-state, computed against a shadow of the reactive graph, with **nothing
committed** - then commit only if you like it; and watch the model explain *which
ceiling* is binding. The whole page is ~11 KB gzipped.

| closure-sim concept | how it shows up here | pimas power |
| --- | --- | --- |
| the closure ratio, doubling time, time-to-target | live readouts | `createMemo` over the same pure functions |
| the discrete-time replication sim | the growth chart (real `sim().steps`) | fine-grained subscribe - only changed outputs re-render |
| the electronics-wall analysis (`analysis.py`) | "speculate: make its own chips" | **`speculate`** - exact what-if, free rollback, no commit |
| the emergent binding regime | the regime timeline + a causal sentence | **explain** (model-derived) |
| - | the "agent surface" panel | `pimas/agent` - subscribe / speculate / explain, zero extra wiring |

The point: `analysis.py` is a *hand-rolled* speculate (deep-copy the factory,
toggle a field, re-run the whole sim, diff, discard). Here that is a first-class
primitive - `speculate(apply, read)` against the live graph.

### Launch economics (`launch-economics`) - live

The second surface (switch via the nav at the top of the page). Drag the **mass
closure** and watch **launch-mass leverage** - installed kg per launched kg - and the
mission cost move: at high closure you launch only a seed; at low closure you end up
launching everything. It runs the parity-tested TS port of `launch-economics` coupled
to closure, live in pimas (signals + a memo - no store/speculate needed for this
simpler model).

### Power budget (`power-budget`) - live

The third surface. Split a power budget between making and thinking (total power,
compute share, hardware efficiency, radiator temperature) and watch compute
throughput, brain-equivalents (~20 W / ~1e18 FLOPS anchor), and how many orders of
magnitude the compute runs above the hard **Landauer** thermodynamic floor (k·T·ln2).
Parity-tested TS port of `power-budget`, live in pimas.

### The single probe (`probe-sim`) - live

The fourth surface. Drag a solar probe out past Mars and Jupiter and watch its
delivered power - and the compute headroom that power buys - collapse as the inverse
square of distance. Composes the environment (inverse-square) with the compute model,
parity-tested TS port of `probe-sim`, live in pimas. (The probe's full replication
range awaits a sourced per-module mass breakdown - an open `[GAP]` in the module.)

## Layout

```
src/
  model.ts               faithful TS port of closure-sim's math (models + closure + replication + wall)
  model.test.ts          parity test - the port must reproduce the Python CLI exactly (node --test)
  pimas-contract.test.ts framework canary - exercises ONLY pimas primitives (see "pimas canary" below)
  scenarios.ts           the two example factories, transcribed from closure-sim/scenarios/*.yaml
  sources.ts             the project-wide bibliography (pure data); sources.test.ts guards its integrity
  coordination.ts        the light-speed coordination-rung logic (pure); coordination.test.ts covers it
  reactive-model.ts      the model as a pimas graph: store + signals + memos + speculate + agent bridge
  chart.tsx              the growth chart, driven by the real sim output
  main.tsx               the page
  smoke.ts               headless integration check (reactive graph + speculate rollback + bridge)
.pimas-good-sha          last pimas commit this frontend is known-good against (canary baseline)
```

## Develop

```sh
npm install          # links pimas via file:../../pimas (build pimas first: cd ../../pimas && npm run build)
npm test             # Layer A - node --test - parity against the Python model (no pimas)
npm run test:contract# Layer B - node --test - the pimas framework canary (pimas primitives only)
npm run smoke        # Layer C - headless integration through the pimas graph
npm run build        # -> dist/ (app.js + index.html), reports gzipped size
npx serve dist       # or any static server; open the page
```

## pimas canary

pimas is first-party and single-maintainer, linked as a live `file:` symlink to
its working tree - so this frontend always builds against whatever pimas is checked
out. To tell **framework** breakage apart from **our** breakage, the tests are
layered by blame surface:

- **Layer A** (`npm test`) imports only the pure TS model - a failure is *our*
  model logic, never pimas.
- **Layer B** (`npm run test:contract`) imports *only* pimas primitives
  (`createSignal`/`createMemo`/`speculate`/`untrack`, `createStore`/`onStoreWrite`,
  `createAgentBridge`) - with A green and our tree unchanged, a failure is **pimas**.
- `.pimas-good-sha` records the last pimas commit this frontend passed against; CI
  diffs current pimas HEAD against it and, on the A-green/B-red gate, files an issue
  in the pimas repo (see [`../.github/workflows/pimas-canary.yml`](../.github/workflows/pimas-canary.yml)).

When Layer B fails against a new pimas, that's verified framework breakage - flag
it in pimas, don't work around it here.

Each surface is faithful to its module (parity-tested against the Python). Every
figure on the page traces to a published source: the consolidated bibliography lives
on the **Sources** surface and in [`src/sources.ts`](src/sources.ts), with per-module
detail in each module's `REFERENCES.md`.
