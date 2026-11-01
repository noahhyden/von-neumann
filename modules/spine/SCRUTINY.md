# Scrutiny plan - FINDINGS #9 (the cross-scale spine)

This is a plan, not code. It lists the claims that must survive scientific scrutiny
for FINDINGS #9 to hold, how each will be tested, and the pass/fail bar for each. It
is written before the paper is scaffolded so that the paper reports a *verified*
finding rather than a plausible one. Nothing here introduces a new number
(CLAUDE.md 1); it audits numbers the sibling modules already fix.

## The finding, reduced to one inequality

FINDINGS #9 is not a measurement. It is a ratio of two derived quantities threaded
through three modules (`closure-sim` -> `multi-probe` -> `swarm`). The whole claim
reduces to:

```
dwell  (~582 d  ==  ~1.6 yr)      <<      galactic fill time (~2e6 yr, powered)
     [numerator]                                  [denominator]
```

with two corollaries:

- at fleet scale, the same ~582 d *is* the doubling clock (transit is days); and
- measured A/B, the dwell costs ~0.4% of exploration time for fast slingshots,
  ~1e-6 for powered.

Every item below is either (a) the numerator, (b) the denominator, (c) that the two
are on one clock, or (d) that the ratio generalizes past the single default point.
Ordered by how much it threatens the finding.

---

## C1 - The numerator is a proxy, not a probe measurement (highest risk)

**Claim under scrutiny.** The ~582 d copy time is
`closure_ratio * seed_mass_kg / build_rate`, computed from the **lunar-regolith seed**
(`src/spine/scenario.py:30`, `default_factory`), because `probe-sim`'s own probe bill
of materials is an admitted `[GAP]`. So the numerator is a lunar factory's cadence
standing in for an interstellar probe's.

**Why it matters.** If a reviewer rejects the proxy, the numerator is unsourced and
the finding collapses - unless the conclusion is shown to be insensitive to it.

**How to scrutinize (the decisive test).** Do *not* defend the exact 582 d. Instead
establish the robustness margin: the fill/dwell ratio is 6-7 orders of magnitude, so
the inequality survives even a large error in the numerator.

- Sweep the derived copy time across a defensible range (e.g. x0.1 to x100 of the
  nominal value) and record whether the inequality `dwell << fill` and the
  "dwell is negligible at galactic scale" verdict still hold.
- State the *break-even* copy time: the value at which the dwell fraction of the
  powered fill reaches, say, 1%. Compare it to the nominal to quantify the margin.

**Pass bar.** The finding holds iff the qualitative verdict is unchanged across at
least +-2 orders of magnitude on the copy time, and the break-even copy time is many
orders above nominal. If a 100x numerator error can flip the verdict, the finding
does not hold and must be re-scoped.

**Honest-framing requirement.** The paper must foreground the proxy and lead with the
margin argument, not bury the `[GAP]`.

---

## C2 - The build-rate regime and its inputs

**Claim under scrutiny.** `time_to_build_one_copy_days`
(`multi-probe/src/multi_probe/fleet.py:84`) uses `min(machinery, energy_cap)`. The
numerator therefore inherits `closure_ratio`, `seed_mass_kg`, `e_local`, and the
1-AU power assumption built from the `4 MW / 30% efficiency / 9798 m^2` array
(`fleet.py:58`), where the 30% array efficiency is flagged `[ESTIMATE]`.

**How to scrutinize.**

- State explicitly which regime binds at 1 AU for the default factory
  (energy-limited vs machinery-limited); the paper must name it, not leave it
  implicit.
- Record how the copy time moves when the `[ESTIMATE]` array inputs move across
  their documented range. Fold that variation into the C1 sweep rather than
  treating it separately.

**Pass bar.** The regime is named and sourced; the `[ESTIMATE]` sensitivity is inside
the margin established in C1.

---

## C3 - The denominator is reproducible from Nicholson and Forgan (2013)

**Claim under scrutiny.** The ~2e6 yr powered fill comes from `swarm` / N&F and is
sensitive to `n_stars` (default 1200), field density, cruise speed, and policy.

**How to scrutinize.**

- Reuse and cite the N&F reproduction already validated for the coordination-tax
  paper; do not re-derive it here.
- Show the fill time is stable across the field-size and seed choices used by
  `run_spine` (`src/spine/scenario.py`: `n_stars`, `seed`), so the denominator is not
  an artifact of one field realization.

**Pass bar.** The fill time reproduces the source within its stated order of
magnitude and does not swing with field size or seed in a way that changes the ratio's
order.

---

## C4 - Unit-clock consistency (silent-failure risk)

**Claim under scrutiny.** The ratio is only meaningful if `DAYS_PER_JULIAN_YEAR`
(`src/spine/run.py:49`, used to convert build-days to years) is the *same* year basis
as the swarm's `C_PC_PER_YEAR` (`swarm/models.py`). A mismatch does not crash - it
shifts the ratio by orders of magnitude undetectably.

**How to scrutinize.**

- Audit both constants back to a single definition of the Julian year
  (365.25 d = 3.15576e7 s) and state the audit in the paper's methods.
- Add a guard test asserting the two constants agree (planned in C8; listed here
  because a unit slip is the most likely silent corruption of the headline number).

**Pass bar.** Both clocks trace to one Julian-year definition; the guard test exists
and passes.

---

## C5 - The dwell is evaluated at 1 AU around a Sun-like star (uniformity assumption)

**Claim under scrutiny.** `derive_settle_time_years` (`src/spine/run.py:107`) evaluates
the cadence at 1 AU, i.e. it assumes every target star delivers 1-AU-equivalent power
and lunar-equivalent feedstock. This is inherited from N&F's uniform field, but real
stellar luminosities and material availability vary.

**How to scrutinize.**

- State it as a scoped assumption tied explicitly to N&F's uniform field.
- Note that stellar variation moves the numerator only, so its effect is already
  bounded by the C1 margin; do not build a stellar-population sub-model (CLAUDE.md 3 -
  this belongs as a parameter and a stated limitation, not a nested simulation).

**Pass bar.** The assumption is stated, attributed to the source's field model, and
shown to fall inside the C1 margin.

---

## C6 - The A/B dwell-tax methodology (`measure_dwell_tax`)

**Claim under scrutiny.** The ~0.4% (slingshot) / ~1e-6 (powered) tax comes from
`measure_dwell_tax` (`src/spine/run.py:178`), an A/B of derived-dwell vs zero-dwell on
a **small** field (`tax_n_stars = 400`) at a **fine** timestep (`tax_dt_years = 1.0`),
for **fast** policies only.

**Three hazards, each with a test.**

1. **Single seed.** The run uses one seed (`0x9E3779B9`, `src/spine/scenario.py:58`),
   whereas the coordination-tax result used a 32-seed ensemble. A single-seed tax is
   not reproducible science.
   - *Scrutiny:* report the tax over a seed ensemble; state median and spread.
   - *Pass bar:* the reported tax is an ensemble statistic, not a point sample.

2. **Timestep resolution.** `tax_dt_years = 1.0` against a ~1.6 yr dwell is barely
   resolved.
   - *Scrutiny:* halve dt and confirm the tax fraction is stable (convergence check).
   - *Pass bar:* tax fraction changes by less than its ensemble spread when dt is
     halved.

3. **Finite-size extrapolation.** The tax is measured on 400 stars because powered is
   impractical to brute-force (see `README.md` note).
   - *Scrutiny:* vary field size and confirm the tax fraction does not drift, or bound
     the finite-size effect explicitly.
   - *Pass bar:* the small-field tax is shown representative, or the drift is bounded
     and reported.

**No-silent-caps requirement.** Any bound the method imposes (small field, single
policy class for brute force) is reported in the paper, not left implicit
(CLAUDE.md 7 spirit: log what was dropped).

---

## C7 - The generalization claim

**Claim under scrutiny.** "The constraint that rules one scale is a rounding error at
the next" is stated generally but computed at one default point. The result is
monotone in the transit/dwell ratio, so it should be robust - but that must be
*demonstrated*, not asserted.

**How to scrutinize.**

- Sweep across policies and cruise speeds and report the dwell fraction at each.
- Report the crossover: the transit speed / policy at which the dwell would stop being
  negligible. This tells the reader where the finding breaks - the honest framing.

**Pass bar.** The negligible-dwell verdict holds across the policy space actually
claimed, and the crossover point is stated so the claim's boundary is explicit.

---

## C8 - Determinism and reproducibility of the artifact itself

**Claim under scrutiny.** The whole finding must be a pure, seeded, deterministic fold
(CLAUDE.md 7): same scenario in, same numbers out, on any machine.

**How to scrutinize.**

- Confirm `run_spine` and `measure_dwell_tax` are deterministic given a fixed
  scenario and seed (no wall clock, no unseeded RNG anywhere in the chain).
- Pin the exact scenario (factory YAML SHA or path, all `SpineScenario` fields, seed
  or seed set) that produced every number quoted in the paper, so a reader can
  reproduce each figure from the pinned inputs.
- Include the C4 unit guard here as a standing test.

**Pass bar.** Two runs from the pinned scenario produce identical numbers; the paper
lists the pinned inputs for every quoted value.

---

## The one-line acceptance test

> If a reviewer says "your copy time is a lunar-factory proxy for a probe you have no
> BOM for - why believe the conclusion?", the answer must be a *demonstrated
> robustness margin* (C1), reproduced over an ensemble (C6), on one audited clock
> (C4), across the claimed policy space (C7) - not a defense of the exact 582 days.

If any of C1, C4, C6, or C7 fails, FINDINGS #9 does not hold as stated and must be
re-scoped before the paper is written. C2, C3, C5, and C8 are supporting audits that
must be clean but are unlikely to flip the finding on their own.

---

## Execution scope: the minimum a VERY simple paper needs

This section turns the plan above into concrete, ordered work. It exists because the
sibling coordination-tax paper was scrutinized *after* it was written and needed a major
revision; three of its lessons set the bar here and are non-negotiable:

- **Scrutiny before prose.** No number goes in the paper until the check that backs it
  has run and committed its output. (coordination-tax M2: statistics that lived only in
  the `.tex` and regenerated from nothing.)
- **Every statistic regenerates from committed JSON.** We mirror the swarm reproducibility
  backbone exactly: `experiments/measure.py` writes committed JSON to
  `experiments/results/`; `experiments/paper_figures.py` renders figures from that JSON;
  `tests/test_measure_results.py` re-runs a tiny slice and asserts it matches, so nothing
  can silently drift. The spine fold is cheap (a copy time is instant; the tax A/B on a
  few hundred stars is seconds), so unlike swarm this whole harness can run in seconds.
- **Ensembles, not point samples; claims sized to the evidence.** Report a median and
  spread over seeds, not one seed (coordination-tax M6/M3: single-seed and over-read
  headlines). State the inequality and its margin; do not dress a rounding-error tax up as
  a precise measurement.

Because the spine finding is a *corollary* of the swarm fill physics (coordination-tax)
and the closure/fleet build physics (electronics-wall), the paper leans on those two
siblings for everything they already establish and validated, and runs new code only for
the seam spine itself closes. Each claim is tagged:

- **[RUN]** new code + committed JSON in `spine/experiments/`, guarded by a drift test.
- **[TEST]** a `pytest` guard (no JSON artifact needed).
- **[CITE]** established and validated in a sibling module/paper; restate and cite, do not
  re-derive.
- **[LIMIT]** a stated assumption/limitation in the paper; no sub-model (CLAUDE.md 3).

| Claim | Disposition | Concrete work | Blocks the finding? |
| --- | --- | --- | --- |
| **C1** margin | **[RUN]** | `m_copy_time_robustness`: sweep the derived copy time x0.1..x1e5, recompute the dwell fraction of the fill at each (do **not** assume linearity - large dwell changes the fill), and solve for the break-even copy time where the powered dwell fraction hits 1%. Emit per-multiplier fractions + the break-even. | **Yes - decisive** |
| **C4** clock | **[TEST]** | Assert `DAYS_PER_JULIAN_YEAR * 86400 == 3.15576e7`, the exact seconds-per-Julian-year that swarm's `C_PC_PER_YEAR` is built from - so both clocks trace to one definition. | **Yes - silent-failure** |
| **C6** tax A/B | **[RUN]** | `m_dwell_tax`: the derived-vs-zero-dwell A/B over a **seed ensemble** (report median + IQR, not one seed), plus a **dt-halving** convergence check and a **field-size** point or two to bound finite-size drift. Slingshot policies only (powered read analytically from C1). | Supports the corollary |
| **C7** general | **[RUN]** | `m_policy_sweep`: dwell fraction across all three policies (and, if cheap, a cruise-speed axis); report the **crossover** copy/transit ratio at which the dwell stops being negligible. | Supports the generalization |
| **C3** denominator | **[CITE]** | The ~2e6 yr fill and the N&F reproduction are validated in coordination-tax; restate and cite. Show only that the fill is stable across the field size/seed spine uses (falls out of C1/C6 runs). | No |
| **C2** build regime | **[RUN]**/prose | Report which regime binds at 1 AU (energy vs machinery) for the default factory and fold the `[ESTIMATE]` array-input variation into the C1 sweep rather than as a separate claim. | No |
| **C5** 1-AU uniformity | **[LIMIT]** | State as an assumption tied to N&F's uniform Sun-like field; note stellar variation moves the numerator only, so it is inside the C1 margin. No stellar-population sub-model. | No |
| **C8** determinism | **[TEST]** | Already covered by `test_spine.py` determinism tests; extend the drift guard (C6) and pin the exact scenario (factory YAML + all `SpineScenario` fields + seed set) in the paper's data-availability note. | No |

### The four experiments and two guards, in build order

1. **[TEST] C4 clock guard** - one assert; do it first, it is the cheapest thing that can
   silently corrupt every downstream number.
2. **[RUN] `m_copy_time_robustness` (C1, C2)** - the decisive margin. If the verdict flips
   inside +-2 orders of magnitude, stop: the finding does not hold and the paper is not
   written.
3. **[RUN] `m_dwell_tax` (C6)** - the ensemble tax for the slingshot corollary, with the
   dt-convergence and finite-size sub-checks.
4. **[RUN] `m_policy_sweep` (C7)** - the generalization and the crossover.
5. **[TEST] drift guard** - `test_measure_results.py` welds each committed JSON to the
   fold so a later refactor cannot desync the paper's numbers.

Everything else (C3, C5, C8) is prose that cites a sibling or states a limitation. That is
the whole scope: two guards, three measurement drivers, and a figure script - enough to
make the one inequality bulletproof and no more.
