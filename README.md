# The Arithmetic of Self-Replication

> **One factory lands on the Moon or an asteroid and builds copies of itself from local material.** How far that idea actually holds, and where the physics stops it - modelled in small, live pieces, with every number traced to a source.

[![code license: PolyForm Strict 1.0.0](https://img.shields.io/badge/code-PolyForm%20Strict%201.0.0-blue)](LICENSE)
[![docs license: CC BY-NC-ND 4.0](https://img.shields.io/badge/docs-CC%20BY--NC--ND%204.0-lightgrey)](LICENSE-DOCS)
[![CI](https://github.com/noahhyden/von-neumann/actions/workflows/ci.yml/badge.svg)](https://github.com/noahhyden/von-neumann/actions/workflows/ci.yml)
[![live site](https://img.shields.io/badge/live-vn.noahhyden.com-brightgreen)](https://vn.noahhyden.com)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21249296.svg)](https://doi.org/10.5281/zenodo.21249296)

A monorepo of small, independently runnable models, each covering one slice of the
problem rather than one giant simulation. Models live in `modules/` (including
`modules/core`, the shared `vn_core` library); `frontend/`, `papers/`, `runner/`,
`scripts/` and `docs/` sit beside it.

**New here?** [FINDINGS.md](docs/FINDINGS.md) collects what the models have concluded
so far, as one read. The same findings are live and interactive on the
[frontend](https://vn.noahhyden.com).

## Modules

| Module | Status | What it does |
|---|---|---|
| [`closure-sim`](modules/closure-sim/) | v1 | Closure and replication from a bill of materials, plus the "electronics wall" - why chips are the part that can't be made in space. |
| [`frontend`](frontend/) | live | The repo's one interactive surface, built entirely on [pimas](https://github.com/noahhyden/pimas). One surface per model. |
| [`probe-sim`](modules/probe-sim/) | in progress | A single probe (after Borgue & Hein 2020): solar-electric power vs heliocentric distance, and the range it gates. |
| [`power-budget`](modules/power-budget/) | live | Splitting a solar-limited budget among manufacturing, compute and housekeeping; compute-watts to throughput. |
| [`launch-economics`](modules/launch-economics/) | live | Launch cost, the Δv penalty, and the mass leverage of shipping a seed instead of the finished installation. |
| [`mission`](modules/mission/) | live | One pure fold composing the four above: launch, arrive, split power, replicate, price the payoff. |
| [`multi-probe`](modules/multi-probe/) | live | A deterministic fleet of tens of probes. Re-instantiates two ceilings: the electronics wall and a 1/d² spatial power wall. |
| [`swarm`](modules/swarm/) | live | A settlement front filling the reachable galaxy (Nicholson & Forgan 2013), with three travel policies and light-speed-limited coordination ([FRONTIER #1](https://github.com/noahhyden/von-neumann/issues/1)). |
| [`spine`](modules/spine/) | done | Threads one factory through all three scales so their replication cadences derive from one source. |
| [`papers`](papers/) | live | LaTeX write-ups. Bibliographies generate from the same [`sources.ts`](frontend/src/sources.ts) the site cites. |

Architecture rationale: [ROADMAP.md](ROADMAP.md). Run machines: [HARDWARE.md](docs/HARDWARE.md).

## Working in here

Each module is self-contained - `cd` in and follow its README. There is no
top-level build.

```bash
cd modules/closure-sim
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
.venv/bin/pytest
```

Everything at once - every module suite plus the frontend's two test layers and
build - from the repo root:

```bash
./scripts/test-all.sh
```

It exits nonzero if any suite fails. The frontend needs only `npm ci` in
`frontend/`; pimas resolves from npm as
[`pimas-ui`](https://www.npmjs.com/package/pimas-ui), no sibling clone needed.

## Conventions

- One module = one directory, with its own README, dependencies and tests.
- `frontend` is the one shared surface, pimas-only, one surface per model.
- Tests assert that the math behaves correctly, not that the code runs.
- Every number traces to a source - see e.g.
  [`modules/closure-sim/REFERENCES.md`](modules/closure-sim/REFERENCES.md).
- Plain language: this gets read by people who aren't engineers.

## License

Split by intent. **Code, tests, scripts and scenario data:** PolyForm Strict 1.0.0
([LICENSE](LICENSE)) - read and run it noncommercially; no redistribution,
modification or commercial use. **Written research** (all Markdown, including this
file): CC BY-NC-ND 4.0 ([LICENSE-DOCS](LICENSE-DOCS)) - cite with attribution, no
commercial or derivative use.

The bundled frontend build embeds pimas (MIT) - see
[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES). Cite via [CITATION.cff](CITATION.cff).

## Contributing and security

Solo research project; the most useful contribution is an issue flagging a sourcing
or factual error. Code PRs are generally not accepted - see
[CONTRIBUTING.md](CONTRIBUTING.md) and the [code of conduct](CODE_OF_CONDUCT.md).
Report security issues privately via [SECURITY.md](SECURITY.md).
