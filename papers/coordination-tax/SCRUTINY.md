# Scrutiny report - the coordination-tax paper

This is a post-hoc adversarial scrutiny of `main.pdf` ("The Coordination Cost of
Light-Speed Delay in a Self-Replicating Probe Swarm Scales as v/c"), run as if the
paper were under review at a prestigious venue in this area (International Journal of
Astrobiology, JBIS, Acta Astronautica; MNRAS/Icarus considered and largely ruled out
on scope). It follows the discipline of `spine/SCRUTINY.md`: every finding names the
claim under scrutiny, how it was checked, the verdict, why it matters, and the fix.

Method: one agent built a field-specific review rubric from real reviewer guidance
(IJA/MNRAS/AAS) and the N&F-2013 lineage; five agents then scrutinized non-overlapping
slices - the central derivation, reproducibility (by re-running the code), statistics
and scale, physics and idealizations, and citations/novelty/venue. Sharpest claims
were verified against source by hand.

## The one-line verdict

> Major revision, and redirect the venue. The computational core is bulletproof (exact
> reproduction, deterministic, convergent, self-correcting). There are no fatal
> scientific errors. The work needed is tightening headline claims to match the
> evidence, hardening the one load-bearing weak spot (extrapolation to scale, exactly
> where this lineage is historically weakest), and routine citation hygiene.

Status legend: `[ ]` open, `[x]` fixed in this pass, `[~]` partially addressed / needs a
re-run flagged, `[-]` won't-fix (author's call).

---

## What is genuinely strong (verified, not taken on trust)

- **Reproducibility is exemplary.** Full suite `56 passed`; same-seed runs bit-identical;
  the N&F 166.4x speedup reproduced exactly against committed JSON; an independent
  scaled-down sweep reproduced the dt-artifact collapse to ~0. `test_measure_results.py`
  welds every figure's JSON to the live fold, so artifacts cannot silently drift.
- **The event scheme is genuinely resolved**, with deterministic tie-breaking of
  simultaneous arrivals `(arrive_year, id)`. RNG is a seeded mulberry32 threaded through
  state - no wall clock, no unordered-set iteration in the fold.
- **The paired same-seed design is correct** and is the real backbone: common-mode
  idealizations (frozen positions, uniform density, free manufacturing, no death term)
  cancel in the differential tax.
- **The energy retraction is sound.** Denominating in journeys is the physically correct
  currency: a losing probe keeps its gravitationally-sourced speed and re-targets, paying
  ~0 propellant, so weighting by (1/2)v^2 would count energy never spent.
- **v/c is relativistically exact for a journey-count tax** (all quantities are
  galaxy-frame coordinate times); the paper undersells this with a smallness argument.
- **Honest posture:** refuses the 10^11-star extrapolation; the 82%-baseline reframing is
  arithmetically correct; the CAP/FLP/Lamport citations are used explicitly by analogy
  with a disclaimer that none predicts the v/c law.

---

## MAJOR findings (ordered by threat to acceptance)

### M1 - The "tax shrinks with scale" trend is confounded by a hard-walled box

**Claim under scrutiny.** Section 3.6 / Fig 7: the tax fraction "does not grow with scale,
in fact shrinks" from ~19% (N=300) to ~13% (N=4800).

**Finding.** The field is a hard-walled, non-periodic cube (`sim.py` `_reflect`; plain
Euclidean distance, no minimum-image / wrap). The box grows ~8 pc (N=500) to ~17 pc
(N=4800), so the edge-star fraction falls as N^(-1/3). Edge probes have fewer candidate
targets and less contention, so the observed coefficient decline conflates genuine bulk
saturation with a shrinking-boundary artifact. This is the exact Achilles heel of the
N&F lineage. `measure.py` itself acknowledges a "box edge bias" in the Clark-Evans code.

**Severity:** MAJOR. **Verdict:** CONFIRMED (geometry), PLAUSIBLE (that it materially
biases the trend).

**Why it matters.** The derivation predicts a scale-free coefficient of 1; the measured
decline is the paper's one scale claim, and if it is partly a wall artifact the "shrinks
with scale" conclusion is unsupported in the direction that matters.

**Fix.** Re-run finite-size on interior stars only (exclude a one-hop boundary shell), or
in a periodic (minimum-image) box, and show whether the decline survives. If it persists,
the saturation reading is vindicated; if it flattens, "shrinks with scale" must be
withdrawn and the section restated as scale-stable-to-mildly-declining over the tested
range.

**Status:** `[x]` interior-only test run and folded into the paper. Added a read-only wall-distance
histogram to the fold (`sim.py` `_wall_bin`, `settle_wall_hist`/`wasted_wall_hist`) and a new
`m_finite_size_interior` measurement; recomputed the paired tax on bulk stars over 300-4800.
**Result: partially confirmed.** Restricting to targets >= 1 mean-NN distance from any wall halves the
decline and leaves it unresolved from zero (slope `-1.8 [-6.4, +1.2]` pp/decade vs all-stars
`-4.4 [-8.2, -2.5]` on the same run); the deep interior (>= 2 NN) gives `+2.0 [-6.6, +9.3]`, consistent
with no decline. So a substantial part of the "shrinks with scale" trend is a hard-wall boundary
artifact and the bulk tax is statistically consistent with scale-stable - which *strengthens* the
paper's no-fixed-percentage-extrapolation conclusion while correcting the mechanism. The scale section
now reports this.

### M2 - The headline scale statistic is not reproducible and over-reads a non-linear decline

**Claim under scrutiny.** "a regression of the median tax on log10 N ... gives a slope of
-4.6 percentage points per decade ... [-7.4, -2.6]."

**Finding.** That regression and its bootstrap interval exist only as prose in the `.tex`;
they are computed nowhere in the pipeline (`m_finite_size`, `fig_fuel_tax_vs_n` emit only
per-N medians/CIs), contradicting the Data Availability claim that "every reported
statistic regenerates from source." The per-decade drops are 0.81, 0.34, 1.62, 3.14 pp -
a visibly accelerating (convex) decline a single linear slope misdescribes - and the
bootstrap resampling unit is undocumented.

**Severity:** MAJOR. **Verdict:** CONFIRMED.

**Fix.** Move the regression (with named resampling unit) into `measure.py` /
`paper_figures.py` so it regenerates; characterize the decline as monotone/non-linear, or
flag the linear slope as a local approximation over a curve. Update the paper's numbers to
whatever the reproducible computation actually gives.

**Status:** `[x]` regression wired into the pipeline (`stats_util.loglog_slope_ci`, emitted by
`m_finite_size` into `finite_size.json`); paper now cites the regenerable value and the accelerating
per-doubling drops. Note: the reproducible interval is `[-7.3, -2.6]`, so the paper's prior `-7.4`
lower bound (which never regenerated from source) was corrected to `-7.3`.

### M3 - The 0.96-vs-1 "saturation" narrative is unnecessary and quantitatively self-inconsistent

**Claim under scrutiny.** The measured through-origin slope is 0.96; the paper narrates a
resolved sub-unity coefficient rescued by a "saturation" argument, and sells "the
coefficient is the derived one."

**Finding.** (a) The only slope CI in the paper, 0.97 [0.89, 1.19] (uniform clumpy-field
null), brackets 1 - so 0.96 is not statistically distinguishable from the derived
coefficient. (b) The saturation story is quantitatively backwards at the paper's own 82%
baseline: a single-candidate exposure model at 82% occupancy would push the coefficient to
~0.3, not 0.96. The paper both over-claims (a resolved 0.96) and under-claims (it should
say "= 1 within error").

**Severity:** MAJOR. **Verdict:** CONFIRMED.

**Fix.** Quote the slope CI at the headline; state a = 1 is confirmed within uncertainty;
either drop the saturation narrative to a one-line "leading-order corrections are within
our error," or reconcile it numerically with the 82% baseline. Note the expanding-front
non-stationarity (the extra d/c window sits before launch, when contention was lower) as
an equally plausible reason the slope sits just under 1.

**Status:** `[x]` reframed (saturation demoted, CI quoted, "consistent with 1").

### M4 - The frozen-field defense covers static geometry but not dynamic reshuffling

**Claim under scrutiny.** Section 4.2: fixed stellar positions are acceptable because the
paired design makes the field bias common-mode and the retarded-position correction is
negligible.

**Finding.** The paired argument correctly cancels the static field bias, and the
retarded-position correction is genuinely negligible (a star moves v_star/c of the
signalling distance during a beacon crossing). But it does not argue why moving stars
(Carroll-Nellenback showed motion can dominate fronts) perturb the baseline contention
p_perfect equally in both regimes; a Myr fill lets stars drift ~225 pc >> 1 pc hop.

**Severity:** MAJOR (borderline). **Verdict:** PLAUSIBLE.

**Fix.** Add a paragraph bounding the dynamic-reshuffling cancellation (contention rate is
local density x branching, both mode-independent, and both regimes see the identical
drift), ideally backed by one moving-field spot-check at Lambda=0.2.

**Status:** `[x]` cancellation argument added to the text; moving-field spot-check flagged
as a deferred experiment.

### M5 - The equivalence claim contradicts its own interval

**Claim under scrutiny.** Section 3.3: fill-time "equivalence to no delay at a 1% margin"
for Lambda <= 0.03.

**Finding.** The cited bootstrap interval reaches [0, 1.3]% at Lambda=0.03 - outside the
stated 1% bound. This is non-significance relabeled as equivalence, the exact failure mode
the paper elsewhere avoids; the 1% margin is also un-justified. (At Lambda=0.01 the
interval is [0,0], genuinely inside 1%.)

**Severity:** MAJOR (as a claimed equivalence; the result is fine restated). **Verdict:**
CONFIRMED.

**Fix.** State the demonstrated bound honestly (equivalence at a 1.3% margin for
Lambda<=0.03, or a clean 1% only at Lambda=0.01) and tie the margin to something
decision-relevant.

**Status:** `[x]` corrected to the 1.3% margin.

### M6 - "Reproduces Nicholson & Forgan quantitatively" overstates an order-of-magnitude match

**Claim under scrutiny.** Repeated assertions that the model reproduces N&F
"quantitatively" at "about 166x."

**Finding.** 166x on a 400-star field vs N&F's ~100x on 200,000 stars is same-order
agreement, not quantitative reproduction (the author's own REFERENCES.md concedes "the
true figure is ~100x"). The qualitative findings (two orders of magnitude;
nearest-beats-max-boost) are correctly reproduced and verified.

**Severity:** MAJOR (over-claim). **Verdict:** CONFIRMED.

**Fix.** Replace "quantitatively" with "reproduces the qualitative findings / agrees to
the same order of magnitude," and state the field sizes differ (400 vs 200,000 stars) so
the factor is not expected to match exactly.

**Status:** `[x]` softened at all sites.

### M7 - Citation and provenance fidelity (violates the project's own sourcing rule)

**M7a - Carroll-Nellenback (2019) mis-attributed for the 0.1-0.2c regime** (LIVE in
current source, 3 sites: `introduction.tex:29`, `the-light-delayed-belief-model.tex:35`,
`the-coordination-tax.tex:229`). Their ships move ~10 km/s (~3e-5 c); 0.1-0.2c is Lubin
(2016) alone. **Verdict:** CONFIRMED. **Fix:** cite Lubin alone for 0.1-0.2c; keep
Carroll-Nellenback only for the Aurora / stellar-motion / settlement-death points, where
it is correct. **Status:** `[x]`.

**M7b - swarm/REFERENCES.md branching section is stale** - stops at offspring=4 and claims
saturation "within an order of magnitude," directly contradicting the paper's
non-saturation-through-16 headline; the 8- and 16-offspring numbers appear in no
provenance doc. **Verdict:** CONFIRMED. **Fix:** update to the 2/3/4/8/16 series and the
non-saturation conclusion. **Status:** `[x]`.

**M7c - the originally-reviewed PDF was a stale build** (17pp; current source is 18pp with
von Neumann + Amigoni + Burgard + the multi-robot prior-art paragraph). **Fix:** rebuild
from current source before submitting. **Status:** `[x]` rebuilt in this pass.

---

## MINOR findings (precision and presentation)

- **m1** "tax = v/c" (coefficient 1) is branching-specific - holds at the 2-offspring
  default; tax/Lambda runs 0.92/1.24/1.27/1.60/1.83 for offspring 2/3/4/8/16. State it as
  `tax = a(branching) . Lambda, a ~ 1 at default` in the abstract. **Status:** `[x]`.
- **m2** Lead the linearity evidence with the four-point ratio table (measured
  1.006/1.042/1.093/1.195 vs 1+Lambda, <1% each), not the through-origin slope, which is
  ~76% determined by the single Lambda=0.2 point. **Status:** `[x]`.
- **m3** "The sign is built in" is empirically false - 7/48 seeds at Lambda=0.01 go the
  other way (retarget cascades make it non-monotone per realization; monotone only in
  expectation). Rephrase and cite the sign-test the code already computes. **Status:**
  `[x]`.
- **m4** Clumpy-field "law survives" overstated where it resolvably breaks - the
  coefficient halves to 0.51 [0.41, 0.70] at R=0.56, disjoint from the uniform 0.97; and a
  Thomas process has no radial gradient, so it under-tests the real-disk case. **Status:**
  `[x]` softened.
- **m5** Round headline figures to CI-supported precision ("~20%", not 19.5%); ensemble
  sizes are compute-driven so CIs are the reportable quantity. **Status:** `[-]` author's
  call (paper always shows the CI, so imprecision is visible).
- **m6** gamma-1 = 2.06% at 0.2c, not "under 2%". **Status:** `[x]`.
- **m7** REFERENCES.md slingshot peak is at u_esc/sqrt(2) ~ 437 km/s, not "u_i ~ u_esc"
  (implementation is correct; only the prose is off). **Status:** `[x]`.
- **m8** Strengthen the relativity claim: v/c is exact for the tax (one-frame), so drop the
  smallness hedge that concedes ground. **Status:** `[x]`.
- **m9** Figs 1, 2, 6 plot bare medians - add CIs, especially Fig 1 (underpins the null).
  Figs 3/5 x-axes are log and the "tax = Lambda" line renders curved - label "(log
  scale)". **Status:** `[~]` log-axis labels added; CI bands on Figs 1/2/6 flagged (needs
  per-seed series in the figure driver).
- **m10** Foreground the genuinely non-obvious contributions (fill-time penalty is a
  discretization artifact; the real cost is wasted journeys not time; d and density both
  cancel) even harder in the abstract's opening. **Status:** `[x]`.
- **m11** Typography: source is house-compliant (no U+2014, no emoji); LaTeX `--` renders as
  en-dashes - author's call whether the rule governs rendered output. **Status:** `[-]`.

---

## Acceptance test

> If a referee re-runs the archived code at a periodic/interior-only finite-size sweep and
> the "shrinks with scale" claim survives (M1); if the scale regression regenerates from
> source and is stated as the non-linear decline it is (M2); if the coefficient claim reads
> "= 1 within error" rather than a saturation-rescued 0.96 (M3); and if the
> Carroll-Nellenback and "quantitatively" claims are corrected (M6, M7) - then the paper's
> headline (relative tax ~ v/c over the tested window) is fully defensible and the paper is
> acceptable at IJA/JBIS/Acta Astronautica.

---

## Fix log

Applied in this pass (all numbers traced to committed `swarm/experiments/results/*.json`; the
`swarm` suite stays green at 58 passed, and the paper rebuilds clean with no undefined references):

- **M7a** removed `carroll-nellenback-2019` from the three "0.1-0.2c" citation sites
  (`introduction.tex`, `the-light-delayed-belief-model.tex`, `the-coordination-tax.tex`); it remains
  cited for the Aurora / settlement-death points, where it is correct. Same correction noted in
  `swarm/REFERENCES.md`.
- **M6** replaced "reproduces quantitatively" with "reproduces to the same order of magnitude" at all
  six sites (abstract, intro, results, model, discussion, conclusion) and added the field-size
  caveat: 166x on 400 stars vs N&F's ~100x on 200,000 stars.
- **M3** reframed the coefficient claim (`the-coordination-tax.tex`, `the-light-delayed-belief-model.tex`):
  leads with the four-point ratio table, quotes the slope CI `[0.89, 1.19]`, states "consistent with
  the derived value of one within uncertainty", and demotes saturation to one of two downward
  leading-order corrections (adding the non-stationary-front effect).
- **M5** corrected the equivalence language to a `1.3%` margin (clean `1%` only at `Lambda=0.01`), and
  stated the margin is the resolved width, not a pre-set tolerance. Same in `REFERENCES.md`.
- **M4** rewrote the frozen-field limitation: the retarded-position argument now uses the *relative*
  stellar velocity (peculiar/shear ~40 km/s; bulk rotation common-mode; full 220 km/s still <0.1%),
  and a dynamic-reshuffling cancellation argument was added (contention is local density x branching,
  both mode-independent, both regimes see the identical drift). Moving-field spot-check flagged as the
  natural next test.
- **M2** added `loglog_slope_ci` to `stats_util.py`, wired it into `m_finite_size`, and populated
  `finite_size.json` from the same code path; paper now states the accelerating (convex) per-doubling
  drops (0.8/0.3/1.6/3.1 pp) and the corrected `[-7.3, -2.6]` interval. Two unit tests added.
- **M7b** refreshed the `REFERENCES.md` branching section to the full 2/3/4/8/16 series
  (18.4/24.9/25.5/31.9/36.5% at `Lambda=0.2`) and the non-saturation conclusion.
- **M7c** rebuilt `main.pdf` from current source (19 pp), so the von Neumann and multi-robot prior-art
  citations render.
- **Minors:** m1 (abstract now says "at the default replication branching"; branching sets the
  coefficient), m2 (lead with ratio table), m3 (sign is "in expectation"; 40/48 positive at
  `Lambda=0.01` cited), m4 (clumpy: form survives, coefficient bends; radial-gradient disk named as
  the open case), m6 (gamma-1 ~ 2%), m7 (`REFERENCES.md` peak at `u_esc/sqrt(2)`), m8 (v/c stated
  *exact* for the tax, one-frame), m9 (log-axis labels on Figs 1/3/7; Fig 5/branching confirmed
  linear, so left as-is), m10 (already foregrounded).

- **M1 (now done)** added the wall-distance instrumentation and the `finite_size_interior`
  measurement (`stats_util.loglog_slope_ci` reused for the by-shell regression), regenerated the
  committed `finite_size_interior.json` over 300-4800 (re-running only the cheap 300-2400 points and
  reusing the already-computed 4800 point), and rewrote the scale section. A `test_swarm.py` guard
  pins the accumulator invariants and determinism. Verdict: partially confirmed - substantially an
  edge artifact; bulk tax consistent with scale-stable.

Deferred (need heavy re-runs, not rushed):

- **M4** moving-field spot-check at `Lambda=0.2` to convert the dynamic-reshuffling argument from
  PLAUSIBLE to CONFIRMED.
- **m9** CI bands on Figs 1, 2, 6 (needs the per-seed series threaded into the figure driver).
