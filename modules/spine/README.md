# spine - the cross-scale integrator

`von-neumann` models self-replication at three scales, each its own pure fold:

1. a **single factory** (`closure-sim`) - mass closure and a replication sim: how long one
   seed takes to reach a target output;
2. a **local fleet** (`multi-probe`) - tens of probes copying and dispersing across AU; and
3. a **galaxy** (`swarm`) - a settlement front spreading across parsecs (Nicholson &
   Forgan 2013).

Until now those three told **three disconnected stories**. Each scale that needed a "how
long to build a copy" number chose its own - and in one place that number was simply
missing: the swarm's per-star **manufacturing dwell** (`settle_time_years`, the time a
freshly settled probe spends building offspring before they leave) was an ungrounded
`[ESTIMATE]` defaulted to **0.0**. The front was assumed to replicate *instantaneously*.

`spine` closes that seam. It threads **one** `closure-sim` factory through all three folds
and **derives** the swarm's dwell from the very same build physics the fleet already uses
(`multi_probe.time_to_build_one_copy_days` at 1 AU). It adds **no new physics** - it routes
a quantity the factory already fixes to the scale that was guessing it (CLAUDE.md §1, §4).

## What it shows

The payoff is a quantitative answer to *which constraint binds at which scale*:

- The derived copy time (~582 days for the lunar-regolith seed) **is the fleet's doubling
  clock** - at fleet scale, transit is days, so build time governs.
- The **same** dwell is a vanishing fraction of the galactic fill: ~8e-7 of a ~2-million-year
  powered fill. Interstellar transit dominates by orders of magnitude.
- The dwell tax is ordered by speed and small at every speed. Measured A/B over a 24-seed
  ensemble (`experiments/measure.py`), the nearest-slingshot tax is a resolved median of ~0.32%
  of exploration time; the max-boost tax is positive but within seed noise at the field size we
  can afford; the powered tax (~8.5e-7) is knowable only analytically. Faster transit shrinks the
  hop time the dwell competes with, so the faster policy pays the larger (still negligible) tax.
- The result survives *not knowing* the copy time. Because the copy cadence is a lunar-factory
  proxy for a probe with no sourced bill of materials, the finding is stated as a robustness
  margin: the powered dwell stays under 1% of the fill until the copy time is ~15,000x nominal, so
  an error of four orders of magnitude in the build cadence does not change the verdict.

So the manufacturing cadence that is *the* constraint on a local fleet is a rounding error on
galactic exploration. That is the cross-scale story the individual modules could not tell on
their own.

## Scrutiny and the paper

[`SCRUTINY.md`](SCRUTINY.md) is the pre-registered scrutiny plan: the claims that must survive
for this finding to hold, each with a test and a pass bar, written *before* the paper so the
paper reports a verified result rather than a plausible one. The decisive checks (the robustness
margin, the one-clock audit, the ensemble tax) are implemented under `experiments/` and in
`tests/`, and the paper `papers/spine/` restates only their committed output.

## API

```python
from spine import SpineScenario, run_spine, measure_dwell_tax, derive_settle_time_years

sc = SpineScenario.default()                 # the shared, sourced lunar-regolith factory
result = run_spine(sc)                        # all three scales, one factory
print(result.verdict)                         # plain-language cross-scale summary

tax = measure_dwell_tax(                       # direct A/B of the dwell's galactic cost
    SpineScenario.default(policy="slingshot_nearest")
)
```

`measure_dwell_tax` runs a fine-timestep A/B (derived dwell vs. zero dwell) on a small field.
It is meant for **fast policies** (slingshots): resolving a ~1.6 yr dwell against ~10⁵-yr
powered hops by brute force is impractical - which is itself the finding. For `powered`, read
the analytic separation (`dwell_fraction_of_t100`) from `run_spine` instead.

## Layout

```
src/spine/
  scenario.py   SpineScenario - one shared factory + the per-scale knobs (no new numbers)
  run.py        run_spine (the integrator), measure_dwell_tax, derive_settle_time_years
experiments/
  measure.py    the reproducibility harness: writes committed JSON to results/ (the copy-time
                robustness margin, the ensemble dwell tax, the per-policy crossover)
  paper_figures.py  renders the paper's figures from results/*.json (no simulation)
  results/      committed, bit-reproducible JSON; the paper restates only these numbers
tests/
  test_spine.py       end-to-end behavior: one factory drives every scale; the dwell is derived
                      not guessed; the copy cadence is the fleet's clock; the dwell is a negligible,
                      speed-ordered tax at galactic scale; boundaries (no offspring); determinism.
  test_clock_audit.py the one-clock guard (SCRUTINY C4): spine's day-year and swarm's light-year
                      trace to one Julian-year definition, so the central ratio cannot silently slip.
  test_measure_results.py  drift guard (SCRUTINY C8): re-runs a slice of each measurement and
                      asserts it matches the committed JSON, so the paper's numbers cannot desync.
```

Regenerate the committed results and figures with:

```sh
uv run --extra dev python -m experiments.measure --force   # -> experiments/results/*.json
uv run --extra dev python -m experiments.paper_figures     # -> papers/spine/*.pdf
```

## Develop

```sh
uv run --extra dev pytest -q
```

Every number spine reports traces to a sibling module's `REFERENCES.md`; spine introduces
none of its own. See [`REFERENCES.md`](REFERENCES.md).
