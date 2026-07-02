# von-neumann

A long-term, modular exploration of **self-replicating space manufacturing** — the
idea that you could land a single factory on the Moon (or an asteroid, or Mars) and
let it build copies of itself from local material, growing an entire industry from
one rocket's worth of cargo. The name is the standard term for the concept:
"von Neumann"-style self-replicating machines.

This is a **monorepo**. Each project lives in its own top-level directory, is
independently runnable and tested, and models one slice of the problem. They share
concepts (and, over time, data) but not a single giant simulation — the whole point
is to keep each piece small, honest, and verifiable.

## Modules

| Module | Status | What it does |
|---|---|---|
| [`closure-sim`](closure-sim/) | ✅ v1 | **Closure & replication.** Define a factory as a bill of materials; compute how much of itself it can build locally ("closure"), simulate how a seed multiplies over time, and analyze the "electronics wall" — why chips are the part that can't be made in space. |
| [`frontend`](frontend/) | ✅ live | **The monorepo's central interactive surface.** von-neumann's models run live in the browser, built entirely on [pimas](../pimas). A shell that hosts one surface per model; the first is the interactive electronics wall (drag the assumptions, speculate "make its own chips" before committing, watch the model explain which ceiling binds). |
| `power-budget` | 🔜 planned | Compute power-budget modeling (e.g. intelligence-per-watt at ~20 W). |
| `launch-economics` | 🔜 planned | Launch costs and the economics of iterating on a seed design. |
| _more to come_ | | The plan is upwards of ten interacting projects over the coming year. |

## Working in here

Each module is self-contained — `cd` into it and follow its own README. They don't
share a top-level build; a module brings its own dependencies and tests.

```bash
cd closure-sim
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
.venv/bin/pytest
```

## Conventions

- **One module = one directory** with its own README, dependencies, and tests.
- **`frontend` is the one shared surface.** It's the single interactive/presentation
  layer, built on [pimas](frontend/) and pimas only. It hosts *one surface per model*
  rather than fusing them — each model still owns its slice; the frontend just
  presents it.
- **Real tests, real numbers.** Assertions check that the math behaves correctly,
  not just that code runs.
- **Grounded inputs.** Assumptions trace to real research; modules document their
  sources (see, e.g., [`closure-sim/REFERENCES.md`](closure-sim/REFERENCES.md)).
- **Plain language.** This work gets shared with non-specialists; explanations are
  written to be read by people who aren't engineers.
