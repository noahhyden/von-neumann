# assembly - the build rate that sets the whole clock

How fast can a self-replicating factory turn raw feedstock into installed machinery?
That single number - kilograms built per day - is the most load-bearing assumption in
the entire project. `closure-sim` and `multi-probe` take it as a hand-set input
(~20 kg/day), and it alone fixes the fleet's doubling cadence: the time to build one
copy is `closure_ratio * seed_mass / build_rate`, which is FINDINGS #9's ~582-day clock
for the lunar seed. This module derives that rate from published numbers instead of
assuming it.

## What it models

`rate.py`, pure algebra (no discrete-event assembly simulator - that would be
over-nesting, CLAUDE.md §3):

    build_rate = manipulators * deposition_rate * hours_per_day * duty_cycle * yield

- **`machinery_build_rate_kg_per_day(...)`** - the derivation, from real metal additive
  manufacturing (WAAM ~1-10 kg/h, LPBF ~0.2-1.4 kg/h) and Overall Equipment
  Effectiveness (world-class 85%, quality 99.9%; typical ~60%).
- **`aasm_implied_rate_kg_per_day()`** - NASA's 1980 self-replicating lunar factory: a
  100-tonne seed that copies itself in a year implies **274 kg/day**.
- **`build_rate_band()`** - the honest `[ESTIMATE]`: `low` ~2.9 (one LPBF head, typical
  OEE), `anchor` ~20.4 (one slow WAAM head, world-class OEE - reproducing closure-sim's
  20), `high` ~274 (NASA). A **>10x** spread.
- **`copy_time_days(rate, seed_mass, closure)`** - the fleet copy time (the same formula
  multi-probe uses), so the module can show its rate setting the doubling clock.

Every input is a terrestrial-robot proxy for a space factory that does not yet exist, so
the whole result is tagged `[ESTIMATE]` (see [`REFERENCES.md`](REFERENCES.md)). Pure,
deterministic, no pimas, no RNG (CLAUDE.md §7).

## What it found

- **closure-sim's 20 kg/day is a single slow head at world-class OEE.** It is not wrong -
  it is one defensible corner of a wide band. That the assumed number falls out of the
  derivation is the calibration check.
- **The build rate is a >10x uncertainty band, and so is the doubling clock.** NASA's own
  1980 study implies 274 kg/day - 13.7x closure-sim's 20 - which would cut the ~582-day
  lunar copy time to ~42 days. The fleet's entire cadence hinges on which end of this
  band is right.

## What it does NOT model (over-nesting guardrails, CLAUDE.md §3)

No discrete-event floor simulation, no per-part process planning, no thermal/mechanical
AM physics - throughput is a sourced parameter, not a simulated assembly line. Feedstock
availability is assumed (that is `isru`'s job).

## Interfaces

- **-> `closure-sim` / `multi-probe`:** supplies the `local_build_rate_kg_per_day` both
  currently hand-set. Scenarios should carry the band, not a point.
- **shares the copy-time formula with `multi-probe`** (no dependency taken - the formula
  is the clean seam); **assumes `isru`'s feedstock** without simulating it.

## Run the tests

```
uv run --extra dev pytest -q
```

9 tests: the derivation, the anchor reproducing closure-sim's 20 kg/day, NASA's 274
kg/day, the >10x band, the 582-day clock and its collapse to ~42 days at the NASA rate,
and linear scaling in manipulators and closure.
