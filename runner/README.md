# runner - one committed spec per simulation run

A simulation run used to be a command you had to remember:

```
cd swarm/experiments && SWARM_WORKERS=2 uv run python -O measure.py branching_scale
```

Four things in that line decide the result, and none of them were written down
anywhere: the worker cap, the `-O` flag, which accelerated backends were active,
and the experiment name. Get the worker cap wrong and the sweep runs out of RAM.
Forget `-O` and it takes two to three times longer. Leave a stale
`export SWARM_WORKERS=2` in a shell and a later run silently inherits it.

Now the run is a file:

```
make run SPEC=swarm/runs/branching-scale.yaml
```

Everything the run needs is in that file, and nothing is read from the
environment.

## The format

```yaml
name: branching-scale
module: swarm
entry: experiments.measure:m_branching_scale
description: >
  Branching-factor sweep at the top of the N ladder. RAM-bound rather than
  CPU-bound at 200k stars, which is why workers is capped below core count.

runtime:
  workers: 2        # was SWARM_WORKERS; blank means every core
  optimize: true    # was `python -O`; strips the fold's debug invariants
  backends:
    rust: true      # was SWARM_NO_RUST / _FILL / _FLAT
    njit: true      # was SWARM_NO_NJIT

params:             # passed to the entry callable as keyword arguments
  n_stars: 262144
```

`runtime` is how the run executes. `params` is what it computes. They are kept
apart on purpose: changing `workers` must never change a number, and the split
makes that reviewable rather than something you have to take on trust.

An unknown key is an **error**, not an ignored line. A spec with `worker: 2`
fails loudly instead of quietly running on every core, because the failure it
replaces was silent.

## No environment variables

The old names - `SWARM_WORKERS`, `SWARM_NO_RUST`, `SWARM_NO_RUST_FILL`,
`SWARM_NO_RUST_FLAT`, `SWARM_NO_NJIT`, `SWARM_P2_N_OVERRIDE`, `PYTHONOPTIMIZE` -
are refused. If one is set in your shell, the run stops and tells you to move the
value into the spec.

This matters more than tidiness. The folds are deterministic by design
(CLAUDE.md section 7), which is what makes a published result reproducible. A
value that reaches the simulation from your shell rather than from a committed
file breaks that guarantee without leaving a trace in the repository.

The variables still exist *inside* the runner, which sets them before importing
the fold. The point is that a person never does.

## Runs stay local

There is no dispatcher, no queue, no container, no server. `vn-run` executes the
run in the current process on this machine. What it adds is visibility: a long
sweep writes its progress to a status file, so

```
make ps
```

shows what is running, how far along it is, and how long it has been going. A run
whose process has died is reported as failed rather than sitting at `running`
forever - a progress view that confidently shows a dead run as live would be
worse than no view at all.

## The event log

Beside the snapshot, each run appends to `.vn-runs/<name>.events.jsonl` - one JSON
object per line, never rewritten:

```json
{"ts":"2026-10-26T23:14:42.863Z","severity":"info","payload":{"type":"run_start","spec":"dwell-tax","module":"spine","optimize":true,"invariants_active":false,"workers":null,"backends":{"rust":true,"njit":true}}}
{"ts":"2026-10-26T23:15:15.438Z","severity":"info","payload":{"type":"run_end","spec":"dwell-tax","state":"done","duration_s":32.575}}
```

The snapshot says where a run IS and is overwritten in place; the log says what
HAPPENED and is append-only. A consumer classifies on `severity` plus
`payload.type`, so `type` is a stable slug naming the kind of thing and the
varying detail goes in sibling keys - `{"type": "invariant_violation", "check":
"mass_closure", "value": 1.03}`, never the value baked into the type.

`invariants_active` is worth reading before trusting an absence. It is `not
optimize`: with `optimize: true` the fold'''s `__debug__` invariant checks are
compiled out, so that run **could not** have reported one. A run with no
invariant events and `invariants_active: false` is silent, not clean. Set
`optimize: false` to make those checks live, at 2-3x the wall clock.

An experiment opts in to emitting its own events by declaring an `events`
parameter, the same way it opts in to `progress`. Nothing in the fold writes to
the log: the fold stays pure (CLAUDE.md section 7), so a violation travels out as
returned or raised data and the harness emits it.

## Commands

| command | what |
|---|---|
| `make run SPEC=<path>` | run one spec |
| `make runs` | list every committed spec |
| `make ps` | live runs and their progress |

Underneath, each is `vn-run` - `vn-run <spec.yaml>`, `vn-run ls`, `vn-run ps`,
and `vn-run validate`, which checks every spec in the tree and is what CI runs.

## Why this is a tooling package

`runner` holds no physical quantities and no fold, so it has no `REFERENCES.md`
and does not import `vn_core`. Like `scripts`, it is excluded from the module
graph in `scripts/depgraph.py`; `depgraph --selftest` asserts every *module*
imports core, and runner is deliberately not one.
