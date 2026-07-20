# scripts - repo-level tooling

Cross-cutting tooling for the monorepo. Unlike the physics modules, this directory
holds no folds and no numbers - just tools that reason about the repo as a whole. It
is held to the same test bar as the modules (100% line+branch coverage, green CI).

## `depgraph.py` - the dependency graph

Answers two questions that stop being answerable by memory once more than one module
is swarm-sized:

1. **Test impact** - if module X changes, whose tests can that break?
2. **Artifact drift** - if X changes, which committed `results/*.json` are now stale,
   and which papers were built from them?

Both fall out of one relation: **reverse-reachability over the import DAG**. If A
imports B (directly or transitively), a change to B affects A - so A's tests must
re-run and A's results/papers may have drifted.

### Three edge types, all derived from content

The graph is never a hand-maintained list, so it cannot silently fall out of sync
with the code:

| edge | how it is derived |
|------|-------------------|
| `imports` module -> module | AST-parsed absolute `import`/`from` of an intra-repo package (src-layout `dir/src/<pkg>/`) |
| `results` module -> `*.json` | the committed `results/*.json` a module owns |
| `figures` paper -> module | a paper's `\includegraphics{X.pdf}` matched to the module whose `paper_figures.py` emits the literal `"X.pdf"` |
| `frontend` module -> port | a module's TS re-implementation, by the convention `frontend/src/<module>-model.ts` (a forward edge: a fold change makes the parity-tested port stale) |

The figure edges reproduce the hand-maintained CI `paths-filter`
(`coordination-tax -> swarm`, `electronics-wall -> closure-sim`, `spine -> spine`)
with zero hardcoding. That duplication is now guarded (see `--check-ci-filter` below).

### Usage

```sh
python scripts/depgraph.py                    # whole graph + blast-radius summary
python scripts/depgraph.py --changed vn_core  # impact of a module change
python scripts/depgraph.py --changed swarm/src/swarm/sim.py   # ...or a file path
python scripts/depgraph.py --changed core,closure-sim --json  # machine output
python scripts/depgraph.py --dot | dot -Tsvg -o deps.svg      # visualize the DAG
python scripts/depgraph.py --selftest         # assert the correctness contract
python scripts/depgraph.py --check-ci-filter  # assert ci.yml's paths-filter matches
python scripts/depgraph.py --ci-filter        # emit the paper filter groups for ci.yml
```

### Keeping the CI paths-filter honest

`ci.yml`'s `dorny/paths-filter` block hand-lists each paper's source modules
(`coordination_tax -> swarm/**`, ...). `--check-ci-filter` parses that block and
asserts it matches depgraph's paper edges, so a new figure sourced from a module
nobody added to the filter fails CI (in the `scripts` job) instead of silently
skipping that paper's rebuild. `--ci-filter` emits the correct paper groups to paste
back into `ci.yml` when they drift. The `shared: &shared` anchor stays hand-kept.

`--changed` accepts module dir names (`swarm`), package names (`vn_core`), or file
paths (the first path component that is a module wins), comma-separated.

### `make affected M=<module>`

The repo's `Makefile` wraps `depgraph --changed ... --list` into a runner that tests
exactly the reachable set:

```sh
make affected M=swarm        # runs swarm + spine (spine imports swarm)
make affected M=vn_core      # runs every module (core is the universal substrate)
make affected M=shielding    # runs shielding + reliability
```

It prints the full impact report (test impact + stale results + papers) first, then
runs each reachable module's `pytest` suite via `uv run --extra dev`. This is the
repo-scale replacement for "re-run everything" (too slow) and "re-run just what I
touched" (misses downstream drift). Note: `M` must be a graph module (a src-layout
package); `scripts` itself is tooling and is not in the DAG.

### Correctness contract

Asserted by `--selftest` and by `test_depgraph.py`:

- `core` (vn_core) is the shared substrate: imported by every other module.
- `spine` threads the cross-scale set `{closure-sim, multi-probe, swarm, core}`.
- a change to `swarm` reaches `spine` (the derived-dwell coupling).
- a change to `core` reaches every module.
- result owners are exactly the modules with committed ensembles (`swarm`, `spine`).
- paper->module edges equal the CI `paths-filter`.

### Non-goals (known gaps)

- **Frontend edges are convention-based**, not import-based: a module's port is found
  by the `frontend/src/<module>-model.ts` name, and the edge flags the port for
  re-verification against the parity fixtures - depgraph does not parse the TS. A port
  that breaks the naming convention is invisible here.
- Dynamic / `importlib` / conditional imports are not seen (literal AST imports only).
- Third-party and stdlib imports are ignored (only intra-repo packages are edges).

The tool reads the tree and never runs a fold, so it can never change a number
(CLAUDE.md 7).

### Tests

```sh
cd scripts && uv run --extra dev coverage run -m pytest -q && uv run --extra dev coverage report
```

`test-all.sh` runs every module's suite plus the frontend; the CI `scripts` job runs
this suite under the coverage gate.
