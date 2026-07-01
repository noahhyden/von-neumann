# wall-live — the electronics wall, made interactive

`closure-sim`'s "electronics wall" essay ([`../closure-sim/explainer.html`](../closure-sim/explainer.html))
is a beautiful static page — but its headline chart is a *hand-faked* curve
(`Math.pow(t, 2.4)`) and its results are hard-coded strings (`~29 years`,
`~17 years`, `never`). This module replaces it with the **real model, running
live**: drag the assumptions and the simulation recomputes; preview "make its own
chips" as a *speculation* — the exact after-state, computed against a shadow of
the reactive graph, with **nothing committed** — then commit only if you like it;
and watch the model explain *which ceiling* is binding.

It is also the dogfood target for [**pimas**](../../pimas): the reactive core runs
the model *and* renders the page, and the whole thing is ~11 KB gzipped.

## What it demonstrates

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

## Layout

```
src/
  model.ts          faithful TS port of closure-sim's math (models + closure + replication + wall)
  model.test.ts     parity test — the port must reproduce the Python CLI exactly (node --test)
  scenarios.ts      the two example factories, transcribed from closure-sim/scenarios/*.yaml
  reactive-model.ts the model as a pimas graph: store + signals + memos + speculate + agent bridge
  chart.tsx         the growth chart, driven by the real sim output
  main.tsx          the page
  smoke.ts          headless integration check (reactive graph + speculate rollback + bridge)
```

## Develop

```sh
npm install          # links pimas via file:../../pimas (build pimas first: cd ../../pimas && npm run build)
npm test             # node --test — parity against the Python model
npm run build        # -> dist/ (app.js + index.html), reports gzipped size
npx serve dist       # or any static server; open the page
```

The model is faithful to `closure-sim` (verified against the Python CLI on both
example scenarios). Figures trace back to NASA CP-2255 (1980) and Freitas &
Merkle (2004) — see [`../closure-sim/REFERENCES.md`](../closure-sim/REFERENCES.md).
