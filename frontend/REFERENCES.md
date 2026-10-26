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

## Numbers that appear in `src/` comments, and where each is sourced

These figures are cited in source comments and carry no new value; each traces to a module reference.

| Figure (file) | Basis | Source of truth |
| --- | --- | --- |
| Array area 9,798 m^2 = 4e6 W / (1360.8 W/m^2 * 0.30) (`mission.ts`) | derived: area sized to deliver the closure scenario's ~4 MW at 1 AU; 0.30 efficiency is `[ESTIMATE]` | [`../mission/REFERENCES.md`](../mission/REFERENCES.md), [`../probe-sim/REFERENCES.md`](../probe-sim/REFERENCES.md) |
| Δv ~9400 m/s, Isp 311 s (LOX/RP-1), $3,000/kg (Falcon 9 reusable) (`mission.ts`) | sourced launch inputs, SI units; target installed mass is a design choice | [`../launch-economics/REFERENCES.md`](../launch-economics/REFERENCES.md), [`../mission/REFERENCES.md`](../mission/REFERENCES.md) |
| Compute efficiency 1e11 FLOPS/W (`mission.ts`) | `[ESTIMATE]` scenario input | [`../power-budget/REFERENCES.md`](../power-budget/REFERENCES.md) |
| ~1e18 FLOPS brain scale, ~20 W brain, Landauer floor (`probe-sim.ts`, `power-budget.ts`) | `[ESTIMATE]` midpoint, Sandberg & Bostrom (2008) | [`../power-budget/REFERENCES.md`](../power-budget/REFERENCES.md) |
| Power split 70 / 20 / 10 and the 10% housekeeping floor with a 0-90% compute slider (`mission-model.ts`) | design choice (fractions of delivered power), not physics | [`../mission/REFERENCES.md`](../mission/REFERENCES.md) |
| ~13.6 AU spatial power wall (`multi-probe.ts`) | derived crossover where the 1/d^2 energy cap overtakes the machinery rate | [`../multi-probe/REFERENCES.md`](../multi-probe/REFERENCES.md) |
| Mean heliocentric distances for the quick-jump buttons (`main.tsx`) | NASA planetary fact sheet | [`../probe-sim/REFERENCES.md`](../probe-sim/REFERENCES.md) |
| Coordination rungs, 1 s / 1 min / 1 hr / 1 yr bucket edges (`coordination.ts`) | rung transitions sourced; the round-number edges are an `[ESTIMATE]` presentation choice | [`../swarm/REFERENCES.md`](../swarm/REFERENCES.md) ("Coordination-horizon visualization") |
| 1 Julian year = 365.25 d = 3.15576e7 s (`spine.ts`) | 3.15576e7 s / 86400 s-per-day = 365.25 d; same year basis as swarm's `C_PC_PER_YEAR` | [`../spine/REFERENCES.md`](../spine/REFERENCES.md) |
| ~1.6 yr dwell vs ~1e5 yr powered hops (`spine-model.ts`) | derived by spine from the shared factory | [`../spine/REFERENCES.md`](../spine/REFERENCES.md) |
| ~8 px star hit radius (`main.tsx`) | UI pick tolerance, not a physical quantity | none needed |
