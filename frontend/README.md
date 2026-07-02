# frontend — von-neumann's interactive surface

This is the monorepo's **central frontend**: the place where von-neumann's models
run live in the browser, built entirely on [**pimas**](../../pimas) (the repo rule
is pimas-only — no other reactive framework; see [`../CLAUDE.md`](../CLAUDE.md)).
The reactive core runs the model *and* renders the page.

It is organized as a **shell that hosts one surface per model**, so each module
keeps its own slice — the frontend just presents them. As `power-budget`,
`launch-economics`, and the rest arrive, each gets its own surface here; they don't
fuse into one giant simulation.

## Surfaces

### The electronics wall (`closure-sim`) — live

`closure-sim`'s "electronics wall" essay began life as a static page — but its
headline chart was a *hand-faked* curve (`Math.pow(t, 2.4)`) and its results were
hard-coded strings (`~29 years`, `~17 years`, `never`). This surface **is** that
essay now — the **real model, running live**: drag the assumptions and the
simulation recomputes; preview "make its own chips" as a *speculation* — the exact
after-state, computed against a shadow of the reactive graph, with **nothing
committed** — then commit only if you like it; and watch the model explain *which
ceiling* is binding. The whole page is ~11 KB gzipped.

| closure-sim concept | how it shows up here | pimas power |
| --- | --- | --- |
| the closure ratio, doubling time, time-to-target | live readouts | `createMemo` over the same pure functions |
| the discrete-time replication sim | the growth chart (real `sim().steps`) | fine-grained subscribe — only changed outputs re-render |
| the electronics-wall analysis (`analysis.py`) | "speculate: make its own chips" | **`speculate`** — exact what-if, free rollback, no commit |
| the emergent binding regime | the regime timeline + a causal sentence | **explain** (model-derived) |
| — | the "agent surface" panel | `pimas/agent` — subscribe / speculate / explain, zero extra wiring |

The point: `analysis.py` is a *hand-rolled* speculate (deep-copy the factory,
toggle a field, re-run the whole sim, diff, discard). Here that is a first-class
primitive — `speculate(apply, read)` against the live graph.

### Launch economics (`launch-economics`) — live

The second surface (switch via the nav at the top of the page). Drag the **mass
closure** and watch **launch-mass leverage** — installed kg per launched kg — and the
mission cost move: at high closure you launch only a seed; at low closure you end up
launching everything. It runs the parity-tested TS port of `launch-economics` coupled
to closure, live in pimas (signals + a memo — no store/speculate needed for this
simpler model).

## Layout

```
src/
  model.ts               faithful TS port of closure-sim's math (models + closure + replication + wall)
  model.test.ts          parity test — the port must reproduce the Python CLI exactly (node --test)
  pimas-contract.test.ts framework canary — exercises ONLY pimas primitives (see "pimas canary" below)
  scenarios.ts           the two example factories, transcribed from closure-sim/scenarios/*.yaml
  reactive-model.ts      the model as a pimas graph: store + signals + memos + speculate + agent bridge
  chart.tsx              the growth chart, driven by the real sim output
  main.tsx               the page
  smoke.ts               headless integration check (reactive graph + speculate rollback + bridge)
.pimas-good-sha          last pimas commit this frontend is known-good against (canary baseline)
```

## Develop

```sh
npm install          # links pimas via file:../../pimas (build pimas first: cd ../../pimas && npm run build)
npm test             # Layer A — node --test — parity against the Python model (no pimas)
npm run test:contract# Layer B — node --test — the pimas framework canary (pimas primitives only)
npm run smoke        # Layer C — headless integration through the pimas graph
npm run build        # -> dist/ (app.js + index.html), reports gzipped size
npx serve dist       # or any static server; open the page
```

## pimas canary

pimas is first-party and single-maintainer, linked as a live `file:` symlink to
its working tree — so this frontend always builds against whatever pimas is checked
out. To tell **framework** breakage apart from **our** breakage, the tests are
layered by blame surface:

- **Layer A** (`npm test`) imports only the pure TS model — a failure is *our*
  model logic, never pimas.
- **Layer B** (`npm run test:contract`) imports *only* pimas primitives
  (`createSignal`/`createMemo`/`speculate`/`untrack`, `createStore`/`onStoreWrite`,
  `createAgentBridge`) — with A green and our tree unchanged, a failure is **pimas**.
- `.pimas-good-sha` records the last pimas commit this frontend passed against; CI
  diffs current pimas HEAD against it and, on the A-green/B-red gate, files an issue
  in the pimas repo (see [`../.github/workflows/pimas-canary.yml`](../.github/workflows/pimas-canary.yml)).

When Layer B fails against a new pimas, that's verified framework breakage — flag
it in pimas, don't work around it here.

The model is faithful to `closure-sim` (verified against the Python CLI on both
example scenarios). Figures trace back to NASA CP-2255 (1980) and Freitas &
Merkle (2004) — see [`../closure-sim/REFERENCES.md`](../closure-sim/REFERENCES.md).
