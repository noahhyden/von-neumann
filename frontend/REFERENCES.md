# Where the numbers come from

`frontend` introduces **no numbers of its own.** It is a faithful port of
`closure-sim`'s model plus a pimas reactive skin - every quantity it displays is
computed by the ported math from the same inputs the Python package uses. So the
grounding for all of it lives in one place:

- **[`../closure-sim/REFERENCES.md`](../closure-sim/REFERENCES.md)** - the sources
  for closure, replication, and the electronics wall (NASA CP-2255 (1980), Freitas &
  Merkle (2004), arXiv:2110.15198). The two example scenarios in `src/scenarios.ts`
  are transcribed verbatim from `closure-sim/scenarios/*.yaml`.

## Why porting doesn't introduce unsourced numbers

The port is guarded so it cannot silently diverge from the reference:

- **`src/model.test.ts`** - parity test: the TS port must reproduce the Python CLI
  **exactly** on both example scenarios (run by `npm test` and in CI).
- **`scripts/gen-diff.mjs` + `scripts/diff_check.py`** (`npm run test:diff`) - a
  differential test across randomly generated factories: the TS port and the real
  Python `closure-sim` must agree across the input space, not just the two examples.

If a displayed number is wrong, one of these fails. A new number that isn't a
consequence of the ported math (e.g. a UI-only constant) must be sourced here per
[`../CLAUDE.md`](../CLAUDE.md) §1 - there are currently none.

## The consolidated bibliography (`src/sources.ts`)

The frontend also hosts the **project-wide bibliography**: [`src/sources.ts`](src/sources.ts)
consolidates every source from all modules' `REFERENCES.md` files into one typed,
pure-data list (Layer A, zero pimas imports), rendered on the **Sources** surface and
surfaced as inline `Cite` tooltips across the other surfaces. It introduces **no new
sources** - it is a re-presentation of what each module already documents, so the
per-module `REFERENCES.md` remains the source of truth. `src/sources.test.ts` guards
its integrity (unique ids, complete records, real-or-null URLs, stable citation
numbering, the repo-wide no-em-dash / no-emoji rule, and the load-bearing sources).
