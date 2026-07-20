# Analytical bounds for the coordination-tax fold: what works, what doesn't

Log of an analytical-bounds investigation run against the 512-seed regenerated
JSONs (PR #72) and the paper's derivation in `papers/coordination-tax/body/the-coordination-tax.tex`.
Goal: find closed-form shortcuts that could replace or short-circuit the
paired instant/lightspeed fold. Two rounds of adversarial pro/contra reports
plus direct numerical verification against the committed JSONs.

## Purpose

Every "DO" here is a bound or estimator that was **numerically verified** and
should be considered when writing the paper or optimizing the fold. Every
"DON'T" is an avenue that was tried and shown to fail, so future contributors
do not spend cycles re-litigating it. The DON'Ts are the point of this file:
they are the negative results that prevent wasted work.

## DOs (verified analytical results, in decreasing order of value)

### D1. `wasted_arrivals ≡ 0` under `inflight` coordination (theorem)

**Statement.** For any `v < c` and any non-tied arrival times, every doomed
probe learns its target is settled and aborts *strictly before* arriving. So
`SwarmResult.wasted_arrivals == 0` under `coordination="inflight"`.

**Derivation.** From `_learn_year` (`sim.py:995`):
`t_learn = (settled + (v/c)·arrive) / (1 + v/c)`. For any `settled < arrive` and
`v < c`, algebra gives `t_learn < arrive` and `t_learn > launch`. So the
probe's redirect is scheduled strictly in the flight window, before arrival.

**Empirical check.** `floor_bracket_scale.json` N=200,000: inflight
`wasted_arrivals = 0` across all 8 seeds at every `Λ ∈ {0.05, 0.1, 0.2}` —
`~1.79M` would-be wasted arrivals eliminated. Never observed non-zero.

**Compute value.** Small. Can be short-circuited but the fold is already fast
in this branch.

### D2. `frac = (s + Λ) / (1 + Λ)` per-hop abort fraction under `inflight` (exact)

**Statement.** For every doomed probe under `inflight`, define
`s = (settled_year[target] − launch_year) / (arrive_year − launch_year)`. Then
the *fraction of the hop actually flown before abort* is exactly
`frac = (s + Λ) / (1 + Λ)`. Bracket: `Λ/(1+Λ) ≤ frac ≤ 1`.

**Derivation.** Substitute `_learn_year` into
`frac = (t_learn − launch) / (arrive − launch)` and simplify.

**Empirical check.** Aggregate mean over the doomed subset:
`<frac> = (<s> + Λ) / (1 + Λ)`. `sim.py:1052-1053` already computes the
per-probe `frac` correctly; the closed form is a diagnostic, not a code change.

**Compute value.** Analytical shape, doesn't save compute directly. Useful for
paper narrative and for anyone instrumenting the `s`-histogram (see D6).

### D3. `W_inst/N` as retarget-cap plateau locator (verified compute-saver)

**Statement.** The instant-run bounce depth `b = wasted_arrivals / n_stars` is a
paired-free sentinel for the retarget-cap plateau: `Δb → 0 ⇔ Δτ → 0`. To
locate `cap*(N)` at a new N, run instant-only at `cap ∈ {8, 16, 32}` and stop
when `b` converges. Then one paired run at `cap*(N)` gives the tax value.

**Empirical check.** Verified across all 10 rows of `retarget_cap.json`
(N=400, 5 caps) + `retarget_cap_scale.json` (N=200k, 5 caps). Per-seed Pearson
`r(b, τ) ∈ [-0.51, -0.97]`; anticorrelation strongest at scale
(-0.97 at N=200k, cap=8/16). At N=400 the b-plateau at cap=16 coincides with
the τ-plateau (both zero increment 16→32). At N=200k, `b` still climbs at
cap=32 (`+4.03`) exactly when `τ` still climbs (`+3.85%`).

**Compute value.** ~3× speedup on retarget-cap scale companion by avoiding
paired sweep to *locate* the plateau; still need one paired run at cap* for the
value. Tracked as issue #73.

### D4. `τ_fuel ≤ Λ` at default branching (k=2) (empirically robust; not a theorem)

**Statement.** At `offspring_per_settlement = 2` (paper default), the fuel
coefficient `a = τ_fuel / Λ ≤ 1` holds on every measured configuration.

**Empirical rows** (all with `a ≤ 1`): `lambda_sweep.json` at all Λ (0.01-0.2);
`finite_size.json` at all 9 N points; `finite_size_interior.json` and
`finite_size_periodic.json` (same); `clumpiness.json` at all 5 clumpiness
levels; `floor_bracket.json` at all Λ.

**Analytical mechanism.** Under a uniform local claim rate, per hop
`p_lag ≤ (1+Λ) p_perfect` (proof: `f(a) = 1 − e^{−xa}` has `f(a)/a`
decreasing in `a`). Sharpened per-hop: `a(hop) ≤ h(x) ≤ 1` where
`h(x) = xe^{−x}/(1 − e^{−x})`. This is a **per-hop** identity; the aggregate
requires matched hop sets under both modes, which is broken by the retarget
cascade. So the empirical `a ≤ 1` is a *finding about the k=2 cascade
coupling*, not a derived inequality.

**Diagnostic use.** If a k=2 run produces `a > 1`, something is wrong with the
fold. Do not use as a compute shortcut — the fold produces `a` directly.

### D5. `−7 ± 1 pp/decade` finite-size decline (regression, robust across edge controls)

**Statement.** The fuel-tax median at Λ=0.2 falls by `~7` percentage points per
decade of N, robust across the three boundary controls (open, interior-masked,
periodic).

**Empirical.** Regression slopes: main `−7.0 [-7.8, −6.4]`, interior
`−6.2 [-8.0, −5.3]`, periodic `−7.1 [-8.1, −6.3]` (from `scale_regression`
blocks in each JSON). All three CIs overlap. The rate is stable; the *level* at
any N is not (the decline is convex, not linear-in-log — see DON'T DN5 below).

**Compute value.** None (still needs the sweep). Value is diagnostic: the
paper's bulk-vs-boundary claim holds because the three CIs agree, not because
any single N matches across the three.

### D6. `s`-distribution shape observation (moment identity, curious not deep)

**Statement.** In the instant fold, the normalized claim-margin
`s = (settled_year[target] − launch_year) / (arrive − launch)` is
approximately exponential across all tested configs, with fitted decay
`k ≈ 1.5-2.2`. The moment product `ψ(0) · <s>` lands near 1 in the paper's
operating regime (uniform through moderate clumping) and diverges only at
extreme clumping.

**Empirical.** Uniform Λ=0.2: `ψ(0) · <s> = 0.97` vs `a_meas = 0.96` (1% error).
sigma0.30: `1.00` vs `0.98` (2%). Breaks by sigma0.08 (0.83 vs 0.70).

**Physical interpretation.** For exponential-family densities on `[0,1]`,
`f(0) · <s> → 1` asymptotically. The identity holds *because* the empirical
distribution is exponential-like *and* the paper's operating regime has
`a ≈ 1`. It does **not** derive `a`; it detects "we're in the exponential
regime where `a ≈ 1` empirically".

**Compute value.** Zero as a compute shortcut. Worth ~1 paragraph in the paper
as an analytical observation, if the moment shape is worth documenting.

**Instrumentation.** This investigation added `SwarmState.wasted_s_hist` and
`SwarmResult.wasted_s_hist` (a 32-bin histogram of `s ∈ [0, 1]`), populated at
the wasted-arrival branch in `_process_arrivals`. Fold determinism preserved
(observational only, no decision touches the histogram).

## DON'Ts (verified failures — do not re-litigate)

### DN1. The `h(p) = (1-p) ln(1/(1-p))` kernel as a scalar estimator of `a`

**Attempted form.** `a = Σ_hops h(p_h) / Σ_hops p_h` where `p_h` is the wasted
fraction per hop-length bin.

**Failure mode.** Systematically **undershoots by ~3×**. At uniform Λ=0.2:
predicted `a = 0.314`, measured `a = 0.995`. Predicted `a` is *nearly flat*
across all Λ and clumpiness levels (0.25 to 0.31) while measured `a` spans
0.41 to 1.02.

**Root cause.** The instant-fold `wasted_hop_hist` conflates two channels:
same-instant assignment collisions (Λ-independent, dominant) and lag-eligible
exposure collisions (Λ-dependent, the tax's signal). h(p) treats them
identically. Separating them requires the lightspeed fold itself.

**Verification.** `scratchpad/hp_verify.py` against `clumpiness.json`.

### DN2. The `ψ(0⁻) / <ψ>` scalar estimator from the `s`-histogram

**Attempted form.** `a = 32 · hist[0] / total` from the instant-fold
`wasted_s_hist`. Derivation: extending an s-density to `s < 0` (lightspeed's
pre-launch danger window) gives extra wasted arrivals `≈ Λ · ψ(0⁻) · W_inst`.

**Failure mode.** Systematically **overshoots by ~3×**. At uniform Λ=0.2:
predicted `a = 2.91`, measured `a = 0.96`.

**Root cause.** The retarget cascade coupling: the lightspeed fold is not the
instant fold plus extra hops at `s < 0`. It is a genuinely different causal
trajectory. The smooth-extension assumption across `s = 0` fails because the
state-space diverges once the first extra hop happens.

**Verification.** `scratchpad/psi_verify.py`, `scratchpad/psi_iterate.py`,
`scratchpad/psi_shape.py`. Even the second-order exponential-model prediction
`(e^{kΛ} − 1)/(Λ(1 − e^{-k}))` overshoots by the same factor.

### DN3. `τ_fuel = Λ` (the naive equality from `eq:tax`) as an N-invariant law

**Attempted form.** `τ_fuel = Λ`, i.e. `a = 1` at all N.

**Failure mode.** **13× miss at N=200,000.** `finite_size.json`: measured
`τ_fuel = 1.52%` at Λ=0.2, N=200k. Equation `eq:tax` predicts 20%. The
paper's derivation explicitly documents this shortfall via saturation.

### DN4. `τ_fuel ≤ Λ` as a general theorem across branching

**Attempted form.** `a = τ_fuel/Λ ≤ 1` universally.

**Failure mode.** **Violated at any branching factor k ≥ 3.** From
`branching.json` at Λ=0.2: `a = 0.96 / 1.17 / 1.27 / 1.53 / 1.77` at
`k = 2 / 3 / 4 / 8 / 16`. The CIs at k=3 and above are disjoint from `a = 1`.

**Root cause.** More offspring per settlement → more correlated stale-view
launches sharing a pre-launch blind window → the retarget cascade coupling
adds Type-B hops (spurious first-hops under lag) faster than the per-hop
`p_lag ≤ (1+Λ) p_perfect` identity can absorb.

**Consequence.** `τ_fuel ≤ Λ` is valid only at default branching (k=2). Do not
present it as a general bound.

### DN5. Power-law finite-size decay `τ_fuel ∝ N^{−α}`

**Attempted form.** A single scaling exponent `α` for the N-dependent decline.

**Failure mode.** The local exponent is **not constant** across N. Fitted
locally from `finite_size.json`: `α ≈ 0.13` over `N = 300 → 4,800`, but
`α ≈ 0.39` over `N = 300 → 200,000`. The curve is genuinely convex; the
paper's "-7 percentage points per decade of N" is a chord across a convex
curve, not a power law.

**Root cause.** The N-decline is a functional of the instant-run p-distribution
shifting toward saturation. `base_waste_frac` rises monotonically 0.81 → 0.90
across the ladder; `h(p) → 0` at `p → 1`; so the coefficient collapses
super-polynomially, not as a fixed power law.

### DN6. Saturating `τ_fuel(k)` in branching

**Attempted form.** `τ_fuel(k) = τ_∞ (1 − e^{-c·k})` — a saturating shape.

**Failure mode.** **No saturation observed to k=16.** `branching.json` at
Λ=0.2 shows monotone rise `19.2 → 23.4 → 25.4 → 30.6 → 35.4%` at
`k = 2 / 3 / 4 / 8 / 16` with CIs disjoint between k=8 and k=16. An earlier
draft of the paper called the 24.9 → 25.5% step a plateau; the current 512-seed
data (k=8 vs k=16 disjoint) proves the plateau was a stopping-early artifact.

**What holds instead.** The marginal `d τ_fuel / d log₂(k) ≈ 0.25 · Λ` is
approximately Λ-independent from k=3 upward. So a **two-anchor** (k=2, k=16)
log-linear fit captures the whole curve, but the *level* at any k requires
measurement.

### DN7. `a(R)` as a separable function of Clark-Evans R

**Attempted form.** `a = f(R)` for some universal `f` derivable from
point-process statistics.

**Failure mode.** **Not separable in R and N.** At N=500, `a(R)` is monotone
0.97 → 0.42 across the clumpiness ladder. At N=200,000, `a(R)` is **flat**
(0.078, 0.076, 0.088, 0.072, 0.076 — noise-consistent with a single value).
The R-dependence itself vanishes with N.

**What holds instead.** The clumpiness multiplier `m(R, N) = a(R,N)/a(uniform,
N)` runs from 0.43 at N=500 to 0.97 at N=200k, tracking `a(uniform, N)`. So R
and N move you along the same saturation coordinate; neither is a separate
axis. The paper's `sec:clumpy` mechanism story (mass shifts to high `p` where
`h → 0`) is *directionally* right without needing a closed form for `f(R)`.

### DN8. Single-formula retarget-cap plateau `τ(cap) = τ_∞(1 − s^cap)`

**Attempted form.** A saturating shape with N-independent convergence rate `s`.

**Failure mode.** Both `τ_∞` and the convergence rate are N-dependent. Successive
deficit ratios from `retarget_cap*.json`: at N=400, `0.56 → 0.225 → 0`
(accelerating, plateaued by cap=16); at N=200k, `0.994 → 0.864 → 0.507`
(barely converging, not yet plateaued at cap=32, and `τ_∞` itself unknown).

**What holds instead.** The plateau *locator* via `W_inst/N` (see D3), but not
a closed-form curve.

### DN9. Concurrency `P_peak = γ · N` linear law

**Attempted form.** A fixed peak-to-N ratio.

**Failure mode.** `P_peak / N = 0.95` at N=500 vs `0.38` at N=200,000. Ratio
is not fixed; a sub-linear exponent applies.

**What holds instead.** The scaling bracket `P_peak ~ N^γ` with `γ ∈ [2/3, 1]`.
Lower bound `N^{2/3}` is derivable (launch rate × hop time); measured value is
`γ ≈ 0.845`. But `γ ∈ [2/3, 1]` is a factor-**58× interval in absolute peak
count** at N=200k, so it does not tighten any downstream claim.

### DN10. Two-channel decomposition of instant `p_bin` into assignment vs exposure

**Attempted form.** Separate the instant-fold's `wasted_hop_hist` into
assignment collisions (Λ-independent) and exposure collisions (Λ-dependent) to
rescue `h(p)` (DN1).

**Failure mode.** **Requires the lightspeed run to distinguish the two
channels.** The instant fold has no tag on each wasted arrival marking which
channel it came from. The only observable that separates them is
`W_lag − W_inst` — which is the paired measurement the estimator was trying to
replace.

## Method

- Adversarial two-round pro/contra debate between two `claude -p` agents at
  Opus 4.8, high effort. Reports are in the working scratchpad
  (`analytical_bounds_FOR{,_r2}.md`, `analytical_bounds_AGAINST{,_r2}.md`);
  not committed.
- Numerical verification of every candidate bound against the 512-seed
  regenerated JSONs from PR #72 (`lambda_sweep`, `finite_size`,
  `clumpiness`, `retarget_cap`, etc.).
- Instrumentation: `SwarmState.wasted_s_hist` + `SwarmResult.wasted_s_hist`
  added for the D6 / DN2 verification. Fold determinism preserved; existing
  measurement JSONs remain bit-identical.

## Bottom line

- **One genuinely new compute-saver**: the `W_inst/N` plateau locator (D3),
  worth ~3× speedup on retarget-cap scale companions. Issue #73.
- **Two theorems**: inflight `wasted_arrivals ≡ 0` (D1) and the per-hop
  `frac = (s+Λ)/(1+Λ)` formula (D2). Analytical shape, no compute change.
- **One diagnostic gate**: `τ_fuel ≤ Λ` at k=2 (D4). Never a theorem; violates
  at k ≥ 3.
- **Everything else in the DON'Ts list has been tried and does not work.** The
  fold's paired instant-vs-lightspeed measurement is genuinely necessary for
  the tax value at any (N, k, R) combination; the retarget cascade is the
  irreducible coupling.
