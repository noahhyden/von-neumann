# Scrutiny report - the spine paper

Post-hoc adversarial scrutiny of `main.pdf` ("The Manufacturing Clock of a Self-Replicating
Fleet Is a Rounding Error on Galactic Settlement"), run as if the paper were under review at an
astrobiology / space-systems journal (International Journal of Astrobiology, JBIS, Acta
Astronautica - the venue of its direct parent, Nicholson & Forgan 2013). It complements the
pre-writing plan in [`../../spine/SCRUTINY.md`](../../spine/SCRUTINY.md): that plan set the bar
before the prose existed; this report is what five adversarial referees found afterward, and
what was fixed.

Every finding names the claim under scrutiny, how it was checked, the verdict
(CONFIRMED / PLAUSIBLE / REFUTED), the severity, why it matters, and the fix. Status legend:
`[x]` fixed in this pass, `[-]` won't-fix (author's call / out of scope).

## Method

Five agents with deliberately distinct adversarial personalities scrutinized non-overlapping
slices, each with read access to the paper, the fold (`spine/`), the sibling modules, and the
committed JSON:

- **Alpha** (hostile physicist): the central derivation, mass/energy balance, the copy-time
  formula, the binding build regime, and whether the headline ratio is the right quantity.
- **Beta** (reproducibility auditor): re-ran the harness; checked every number traces to
  committed JSON and reproduces bit-for-bit; determinism and the clock invariant.
- **Gamma** (statistics pedant): ensembles, sweeps, break-even soundness, claim-sizing, and
  whether any precision exceeds its evidence.
- **Delta** (citations / novelty / venue): every citation's fidelity, missing prior art, and
  venue fit.
- **Epsilon** (consistency / house-rules editor): cross-location number consistency, typography
  (no em-dash, no emoji), plain-language, and clarity.

## The one-line verdict

> The computational core is bulletproof - exact, deterministic, bit-reproducible, drift-guarded,
> on one audited clock - and the conclusion (manufacturing is negligible at the nominal copy
> time) holds. The work needed was one **major honesty correction** (the robustness margin was
> stated on the wrong, more favorable quantity), naming the binding build regime, correcting the
> venue and several citations, and reconciling two field-size-dependent numbers. All are fixed.

## What is genuinely strong (verified, not taken on trust)

- **Reproducibility is exemplary.** Full suite `15 passed`; all three `results/*.json` regenerate
  bit-for-bit identical; the drift guard re-runs the fold and matches to `rel=1e-9`; the C4 clock
  invariant (`DAYS_PER_JULIAN_YEAR * 86400 == 3.15576e7`, the same Julian year the swarm's speed
  of light is built from) exists and passes. Figures are pure functions of committed JSON.
- **The arithmetic is correct.** Alpha re-derived the copy time (11650 kg / 20 kg/day = 582.5 d),
  the dwell (582.5/365.25 = 1.5948 yr), and confirmed the closure is a mass basis, all matching
  the fold.
- **The claim-sizing learned the sibling paper's lessons.** The dwell tax is a 24-seed ensemble
  with median + IQR, not a single seed; the unresolved max-boost case is reported as
  positive-but-unresolved, not a point estimate. Gamma recomputed the stats from the raw arrays
  and confirmed them exactly.

---

## MAJOR findings

### A1 - The robustness margin was stated on the per-copy ratio, not the physical cost
**Verdict: CONFIRMED. Severity: MAJOR.**

**Claim under scrutiny.** The abstract/results/figure headlined `f = tau/T100 ~ 8.5e-7` as the
manufacturing cost and claimed the verdict "survives an error of four orders of magnitude in the
build cadence" (break-even ~1.5e4x nominal).

**Finding.** `f` is one dwell as a fraction of the whole fill - a *per-copy* separation. But the
front pays one dwell at *every* settlement, so the physically meaningful cost is the cumulative
A/B slowdown of the fill, `(T100_with - T100_zero)/T100_zero`, which equals `f` times the number
of settlements on the critical path (~18 for the powered fill). Measured directly, the cumulative
powered tax is `1.5e-5` at nominal and rises in proportion to the copy time: it is 0.15% at 100x
nominal but **22% at 10^4x**. So the "four orders of magnitude" margin holds only for `f`; on the
physical cost the margin is about **two** orders (break-even near a few-hundredfold copy time),
and for the fastest slingshot front it is only ~3x, because the nominal tax there is already
~0.32%.

**Why it matters.** The headline number and its margin were the paper's central quantitative
claim, and they were stated on the quantity that flatters the result. The *conclusion* (negligible
at nominal) is intact, but the *margin* was overstated by the critical-path factor and the
policy-dependence was hidden.

**Fix.** `[x]` Added the cumulative tax and its break-even to the harness
(`_cumulative_tax`, `_break_even_cumulative`; `copy_time_robustness.json` and `policy_sweep.json`
regenerated, drift test extended). The figure now plots both curves; the abstract, results,
discussion, and conclusion lead with the cumulative cost (~1.5e-5 nominal, ~two-order margin) and
state the fast-front boundary (~3x) explicitly. `f` is kept and labelled as the per-copy floor.

### A2 - The binding build regime was unnamed; the solar-power framing was inert
**Verdict: CONFIRMED. Severity: MAJOR.**

**Claim under scrutiny.** The model section evaluated the copy time "at 1 AU where the solar
constant is 1361 W/m^2" and results claimed "the collector inputs ... factor of two ... a small
sub-interval of this margin."

**Finding.** At 1 AU the default seed is **machinery-limited**: `min(20 kg/day, ~3700 kg/day)` =
the 20 kg/day machinery rate, ~190x below the energy cap (which binds only past ~13.7 AU). So the
copy time is fixed by machinery throughput and `C*m_seed`; the solar constant, array area, and the
[ESTIMATE] 30% array efficiency do **not** move it at all. The "collector uncertainty" robustness
sub-claim was therefore vacuous, and the discussion's "a fainter star lengthens the copy time" was
false across essentially the whole target population. The pre-writing plan (C2) had required naming
the binding regime; the prose had not.

**Fix.** `[x]` Model section now states the machinery-limited regime (20 kg/day, ~190x, ~13.7 AU
crossover) and identifies the machinery rate and `C*m_seed` as the load-bearing inputs; results and
discussion corrected accordingly. Verified against the fold and `multi-probe/REFERENCES.md`.

### A3 - The rocket-equation scaling was misstated
**Verdict: CONFIRMED. Severity: MAJOR (peripheral).**

**Claim.** "the rocket equation makes shipping a finished installation exponentially more
expensive in propellant."

**Finding.** At fixed delta-v propellant is *linear* in payload mass; the exponential is in
`delta_v / v_e`. Cutting delivered mass by the leverage factor `1/(1-C)` is a *linear* saving on a
kilogram that is exponentially expensive to move.

**Fix.** `[x]` Rephrased so the exponential attaches to `delta_v/v_e` and the leverage is the
linear saving.

### D1 - Venue: IEEEtran conference template vs. the astrobiology lineage
**Verdict: CONFIRMED. Severity: MAJOR.**

The paper used `\documentclass[conference]{IEEEtran}` while its entire citation lineage (Tipler,
Hart, Freitas, Lubin, Nicholson & Forgan, Forgan-Papadogiannakis-Kitching, Borgue & Hein) and its
sibling coordination-tax paper target an astrobiology journal. **Fix:** `[x]` Converted to the
sibling's `article` / natbib / `plainnat` format (the user's explicit instruction); `\cite` ->
`\citep`/`\citet`, IEEE macros removed, a Data-availability section added.

### D2 - Missing canonical prior art: Armstrong & Sandberg 2013
**Verdict: CONFIRMED. Severity: MAJOR.**

"Eternity in six hours" (Acta Astronautica 89:1-13) - the canonical modern treatment of
directed-energy galactic/intergalactic settlement timescales - was absent from the bibliography.
**Fix:** `[x]` Added to `sources.ts` (DOI 10.1016/j.actaastro.2013.04.002, verified), `refs.bib`
regenerated, cited in the intro (galaxy-crossing timescale) and results (directed-energy regime).

### D3 - Embodied-energy citation mis-targeted
**Verdict: CONFIRMED. Severity: MAJOR (borderline).**

The per-kg embodied energy of the (metals-dominated) bill of materials was cited only to an
IC-manufacturing paper (Nagapurkar & Das). **Fix:** `[x]` The BOM-wide figure now cites the
structural embodied-energy sources (ICE coefficients, Gutowski 2009), with Nagapurkar & Das kept
for the integrated-circuit minority.

---

## MINOR findings (all actioned unless marked)

- **G1 / E1 - Break-even stated as two numbers (1.5e4 vs 10,000).** CONFIRMED. The two values were
  the same policy on different field sizes (1200 vs 400 stars). `[x]` Superseded by the A1 rewrite:
  the margin is now on the cumulative tax, field sizes are labelled at each use, and the table
  reports the cumulative margin (~600 powered / ~3 nearest).
- **D4 - 70-96% closure range: 96% upper bound cited to the wrong works.** CONFIRMED. `[x]` Now
  cites `nasa-cp-2255-1980` (which grounds 90-96%) alongside Shubov and Freitas & Merkle.
- **D5 - Missing Metzger et al. 2013** (the modern quantitative anchor for the seed numbers).
  `[x]` Added to the seed-grounding citation and `paper.json`.
- **D6 - "has never been checked" overclaims.** PLAUSIBLE. `[x]` Softened to "has not been derived
  from factory physics"; the zero is attributed to the settlement-front model used here, and
  Cotta & Morales (nearest prior treatment of a dwell-like imprint time) is cited.
- **A4 - Numerator excludes the power-plant infrastructure** the seed scenario treats as separate
  (can outmass the seed). PLAUSIBLE. `[x]` Named as a limitation; a ~100x correction stays inside
  the powered margin but would push the fastest slingshot fronts past 1%, consistent with the
  stated boundary.
- **B1 - Paper not self-contained for reproduction** (no seed, no data-availability statement).
  CONFIRMED. `[x]` Added a Data-availability section naming the harness, the committed JSON, the
  pinned seed (2654435769), and the branching factor.
- **B2 - `T100 ~ 1.9e6` was back-computed, not stored.** PLAUSIBLE. `[x]` `t100_years` now emitted
  in the JSON (as the zero-dwell baseline) and drift-guarded; the text notes `T100 = tau/f`.
- **B4 - Harness docstring "seconds, not hours" wrong** (regen takes minutes). CONFIRMED. `[x]`
  Corrected.
- **G3 - Finite-size trend called "scale-flat" in code** but is a mild monotone increase
  (0.31->0.34%). CONFIRMED. `[x]` Comment corrected; the paper already said "mild ... representative".
- **D7 - Sagan & Newman rebuttal to Tipler** absent. `[x]` Added at the Fermi framing.
- **D8 - Title vs. 1200-star field.** REFUTED as an overclaim (`f` shrinks with scale). Not added
  as a "strongest at galactic scale" line, because the *cumulative* tax is only scale-stable
  (mildly rising), not shrinking - so that framing would have been a new overclaim. `[-]`
- **E5 - Dense abstract; E6 - one comma-splice; E7 - Discussion/Conclusion recap overlap.** Minor
  prose. `[x]` The comma-splice was recast during the results rewrite; the abstract and recap are
  author's call and left as readable prose.
- **G4 - Nearest tax has IQR but no median CI.** Honestly sized (23/24 seeds positive; IQR entirely
  positive). `[-]` IQR is a legitimate spread; the resolution is unambiguous.

## Typography and consistency

Epsilon's scan and `check-typography.mjs` confirm the source is clean: **no U+2014, no U+2013, no
emoji, no LaTeX `---`** (CLAUDE.md 5). The two abstracts (`main.tex` and `paper.json`) are
byte-identical. All `\ref`/`\eqref`/`\citep` resolve; the rebuilt PDF has no undefined references.

## Acceptance test

> If a referee re-runs the archived harness and finds (a) the robustness margin stated on the
> cumulative fill tax, not the per-copy ratio, with the fast-front boundary named (A1); (b) the
> machinery-limited regime named and the inert solar framing removed (A2); (c) the venue, Armstrong
> & Sandberg, and the embodied-energy citation corrected (D1-D3) - then the headline (manufacturing
> is a rounding error on a *powered* galactic fill, rising toward a percent as the front is driven
> faster) is fully defensible and the paper is acceptable at IJA / JBIS / Acta Astronautica.

All MAJOR findings and the actionable minors are fixed; the paper rebuilds clean and the spine
suite stays green at `15 passed`.
