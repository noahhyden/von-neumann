# Where the numbers come from

Slice 1 of the swarm has few physical inputs (the settlement dynamics are mostly
geometry + a policy). Each number is sourced or flagged (CLAUDE.md §1).

## Physics (derived / defined)

- **`C_PC_PER_YEAR ≈ 0.30660` pc/yr** - the speed of light in parsecs per Julian year,
  *derived* from defined constants: `c = 299792.458 km/s` (exact, SI), `1 pc =
  3.0856775814913673e13 km` (IAU 2015 definition), `1 Julian yr = 3.15576e7 s`. Shown in
  code as `299792.458 * 3.15576e7 / 3.0856775814913673e13`.

All scenario numbers below trace to **Nicholson & Forgan (2013)**, *Slingshot Dynamics
for Self-Replicating Probes and the Effect on Exploration Timescales*,
[arXiv:1307.1648](https://arxiv.org/abs/1307.1648) (*Int. J. Astrobiology* 12, 337),
read from the full text ([ar5iv](https://ar5iv.labs.arxiv.org/html/1307.1648)).

> **Correction (why the defaults changed):** an earlier version of this file claimed a
> "0.1c fiducial from Nicholson & Forgan" and a 0.14 stars/pc³ density. Both were wrong
> - 0.1c was **not** their value (it was ~3300× too fast and unsourced), and they use a
> uniform 1 star/pc³, not the solar-neighborhood figure. The defaults below are the
> paper's actual parameters, checked against the source. (CLAUDE.md §1: a mis-attributed
> number is worse than a gap.)

## Scenario inputs

- **Powered cruise speed = 3×10⁻⁵ c (≈ 9 km/s)** - the paper's stated maximum probe
  velocity ("The maximum velocity of the probes was chosen to be 3×10⁻⁵c"). This is the
  *powered-flight* speed; the paper's whole point is that **gravitational slingshots**
  (extracting energy from a star's ~200 km/s orbit about the Galactic centre) let a probe
  explore ~100× faster - slingshots are a later slice, so this module models powered
  flight only. 3×10⁻⁵c → ~9.2×10⁻⁶ pc/yr, so a ~1 pc hop takes ~110,000 years.
- **Stellar density = 1 star/pc³** - the uniform density the paper uses ("uniform density
  of 1 star per cubic parsec"). Denser than the real solar neighborhood (~0.14 stars/pc³,
  RECONS 10-pc census) - a modelling choice the paper makes; we follow it for fidelity.
  Sets the box size `(N/ρ)^(1/3)` and the mean hop (~1 pc here).
- **Offspring per settlement = 2** - a scenario **choice** (the replication branching
  factor). 0 → only the homeworld; 1 → a single roving probe (slow linear chain); ≥2 →
  the field fills exponentially fast until stars run out.
- **Settle/dwell time = 0 years default** - `[ESTIMATE]`; the time a probe spends
  building offspring before they depart. The paper assumes replication happens *in
  transit* (probes collect interstellar material and never stop), so 0 dwell is faithful
  to that; a nonzero value is a documented knob. (Replicate-in-transit vs our
  settle-then-launch is a later-slice refinement - see below.)
- **Timestep = 5000 years default** - a **numerical** choice, not physics: it must stay
  ≲ the mean hop time (~1.1×10⁵ yr at the defaults) or the fixed-step discretization
  inflates the exploration timescale. At `dt=5000` the timescale is within ~1% of the
  `dt→0` limit. Result: filling a 500-star box takes ~1.5 Myr, and the whole reachable
  field fills on a **Myr timescale** - the same order as the paper's 5–10 Myr for 200,000
  stars. The front advances at only ~40% of a single probe's speed (nearest-hop zig-zag +
  settling), consistent with the paper's finding that exploration is slower than naive.

## Slingshot dynamics (the `slingshot_*` policies)

The paper's core mechanism: a probe flying past a star is deflected elastically in the
star's frame, but because the star moves in the galactic frame the probe's galactic-frame
speed changes - extracting energy from the star's motion "for free." Boosted probes
accumulate speed across encounters and far outrun powered flight. All of the following is
from Nicholson & Forgan (2013); the numbers the paper defers are tagged `[ESTIMATE]`.

- **Max boost per encounter** - `Δv_max = u_esc² / ( u_esc²/(2·u_i) + u_i )` (their Eq. 4),
  with `u_i` = the probe's speed relative to the star. This *self-limits*: Δv_max peaks near
  `u_i ≈ u_esc/√2` (≈ 437 km/s for solar values) and falls off for fast probes, so speed does not
  run away. (The implementation uses Eq. 4 directly; only this prose peak-location note is corrected
  from an earlier "u_i ≈ u_esc".)
- **Stellar escape velocity `u_esc = 617.5 km/s`** - solar, `u_esc = √(2GM☉/R☉)`. Derived:
  `√(2 · 6.674e-11 · 1.989e30 / 6.957e8) = 6.18×10⁵ m/s`. Sourced (the paper "assumes solar
  values for M∗ and R∗"); constants are IAU/CODATA nominal. **Derived, not a free number.**
- **Boost-optimal geometry `[ESTIMATE]`** - the paper gives `Δv = 2|u_i|·sin(δ/2)` (Eq. 3)
  but not how the deflection angle δ is set per flyby. We assume each slingshot achieves
  `Δv_max` (Eq. 4) in the boost-optimal direction, and we track **scalar speeds** (not full
  velocity vectors / true encounter geometry), taking `u_i ≈ probe speed + star speed`. A
  deliberate simplification for an experimental model.
- **Stellar speed `220 km/s ± 40 km/s` `[ESTIMATE]`** - the paper places stars in a shearing
  box to mimic Galactic rotation but **does not print the rotation speed or velocity
  dispersion** (it defers to Forgan, Papadogiannakis & Kitching 2012). We use the standard
  local circular speed (~220 km/s) with a thin-disc-like dispersion (~40 km/s), random per
  star (seeded). Stars are **fixed in position** but carry a speed that drives the boost -
  as the paper does ("stars remain fixed in position even though they have velocity vectors").
- **Max-boost candidate bound = 30 `[ESTIMATE]`** - policy (iii) targets the biggest boost;
  we scan only the 30 nearest unsettled stars so a probe doesn't cross the galaxy for a
  marginal kick. Our fallback when no candidate exists = stop (a modelling choice).
- **Speed cap = 0.05 c `[ESTIMATE]`** - a sanity ceiling on accumulated speed; Eq. 4's
  fall-off usually keeps speeds well below it.
- **Observed speedup is `dt`-limited.** Boosted probes are fast (~10³ km/s), so their hops
  (~10² yr) are shorter than `dt=5000 yr` and get quantized to one step. The measured
  slingshot-vs-powered speedup is therefore ~20× at the default `dt`; the paper's true
  figure is ~100×. Lowering `dt` recovers more of it (at more steps). The **qualitative**
  results are faithful: slingshots ≫ powered, and **nearest-slingshot beats max-boost on
  time** (max-boost reaches higher speed but wastes travel - the paper's finding).

## Coordination-horizon visualization (the light-speed rungs)

A frontend-only teaching overlay (FRONTIER issue #1, near-term slice) that turns an
inter-star distance into a *coordination mode* via the light-travel time. No new sim
physics - it reuses `C_PC_PER_YEAR` above; the only inputs are the rung thresholds and
the real-world analog distances below.

- **Round-trip latency = `2 · d / c`**, one-way = `d / c`. Both derived from
  `C_PC_PER_YEAR` (above): a distance `d` in pc has one-way light-time `d / 0.30660` yr.
  *Check:* 1 AU = `1.495978707e8 / 3.0856775814913673e13 = 4.8481e-6 pc` → one-way
  `4.8481e-6 / 0.30660 = 1.5813e-5 yr = 499.0 s = 8.32 min`, the textbook 1-AU light time.
- **The ρ ratio** - `ρ = round-trip latency / decision timescale`. Coordination fidelity
  degrades as ρ grows (Olfati-Saber & Murray 2004, *IEEE TAC* 49(9),
  [DOI 10.1109/TAC.2004.834113](https://doi.org/10.1109/TAC.2004.834113): the standard
  consensus protocol is stable iff the one-hop delay `τ < π/(2λₙ)`, so tighter coupling
  tolerates *less* delay). The **decision timescale is a knob, default 1 yr `[ESTIMATE]`**
  - the literature gives no single value for "a probe's targeting-decision cadence," so ρ
  is presented as a tunable lens over the *sourced* absolute-latency rungs below, not as a
  hard number itself.

- **Rung thresholds (by round-trip latency) `[ESTIMATE]`** - the *transitions* are sourced
  from the teleoperation/networking literature; the round-number bucket edges (1 s, 1 min,
  1 hr, 1 yr) are a presentation choice, so the set is tagged `[ESTIMATE]`:
  - **≤ 1 s - real-time closed-loop.** Continuous closed-loop teleoperation breaks down and
    operators switch to "move-and-wait" once delay approaches ~1 s (Ferrell 1965, *Remote
    Manipulation with Transmission Delay*, NASA TN D-2665, [NTRS
    19650052768](https://ntrs.nasa.gov/citations/19650052768)).
  - **1 s – 1 min - move-and-wait.** The degraded regime Ferrell (1965) characterized:
    command open-loop, wait a full round trip, correct.
  - **1 min – 1 hr - supervisory.** Send goals, let the node execute; the operator
    supervises rather than pilots (Ferrell & Sheridan 1967, *Supervisory Control of Remote
    Manipulation*, IEEE Spectrum).
  - **1 hr – 1 yr - delay-tolerant / store-and-forward.** No continuous end-to-end path;
    hop-by-hop custody transfer, no real-time handshake (Cerf, Burleigh et al.,
    *Delay-Tolerant Networking Architecture*, IETF [RFC 4838](https://www.rfc-editor.org/info/rfc4838), 2007).
  - **> 1 yr - fully independent colonies.** No live command exists; each node acts on
    priors set before launch (Freitas 1980, *A Self-Reproducing Interstellar Probe*, *JBIS*
    33:251 - each probe "an independent agent").

- **Real-world analog distances** (each classified by the arithmetic above; used only as
  legend anchors - every value is a citable astronomical constant):
  - **LEO ≈ 550 km** (Starlink operational shell) → `1.7824e-11 pc`, round-trip **3.67 ms**
    → *real-time*. (SpaceX/FCC filings; 550 km is the primary shell.)
  - **Earth–Moon = 384,400 km** (mean distance, IAU) → `1.2458e-8 pc`, round-trip **2.564 s**
    → *move-and-wait*.
  - **Mars ≈ 0.52–2.52 AU** (min/max Earth–Mars range) → round-trip **~8.7–42 min** →
    *supervisory* across the whole range.
  - **Saturn = 9.5 AU** (semi-major axis 9.582 AU, NASA planetary fact sheet, rounded) →
    `4.606e-5 pc`, round-trip **~2.6 hr** → *delay-tolerant*.
  - **Proxima Centauri = 1.301 pc** (4.2465 ly; RECONS/Gaia parallax) → round-trip **8.49 yr**
    → *fully independent colonies* - and this is the regime **every ~1 pc inter-star hop in
    the sim already sits in** (mean hop ~1 pc → round-trip ~6.5 yr). That collapse is the
    lesson, not a rendering bug: at galactic scale the four faster rungs are sub-pixel.

## Light-speed-limited coordination (the `lightspeed` regime, FRONTIER #1)

Nicholson & Forgan grant every probe **perfect, instantaneous global knowledge** of which
stars are settled; finite light-speed is their explicit future work. The `coordination`
param adds it: under `"lightspeed"`, a probe deciding *at* star `frm` in year `Y` treats a
distant star `i` as settled only once the news has arrived -
`settled_year[i] + dist(frm,i)/c ≤ Y`. Under `"instant"` (default) this collapses to
`settled_year[i] ≥ 0`, bit-identical to the perfect-info slices.

- **Signal speed = c** - the news travels at lightspeed (an EM beacon is the physical upper
  bound on information). Reuses the already-derived `C_PC_PER_YEAR` (above); **no new
  constant.** A slower signal is a trivial future knob, not needed for the core question.
- **`Λ = v_probe / c`** - the dimensionless ratio (info-lag-per-hop ÷ travel-time-per-hop =
  (d/c)/(d/v) = v/c). Derived, not free, and hop-length-independent (d cancels). At the powered
  cruise (3×10⁻⁵ c) `Λ ≈ 3×10⁻⁵` → negligible; it grows through the slingshot regime
  (`Λ ≈ 0.01`) up to beamed directed-energy speeds (`0.1-0.2 c`, [lubin-2016]; NOT
  Carroll-Nellenback, whose ships cruise at ~10 km/s ~ 3×10⁻⁵ c - that source grounds the Aurora
  settlement-death term, not the top-end speed). **`Λ` is
  the governing parameter of the FUEL tax:** at the resolved (event) timestep the fill-TIME tax
  is small at every speed, but the redundant-travel (wasted-journey) tax rises cleanly and
  monotonically with `Λ` - median +0.7% at `Λ=0.01`, +2.5/+4.5/+9.3% at 0.03/0.05/0.1, +19.3%
  at 0.2 (powered, N=500, 512 seeds). It is the right group for the right cost.
- **Effective speed `v_eff` and hop lengths (derived observables, read-only accumulators).**
  `mean_launch_speed_km_s` is the mean launch speed (so `Λ_eff = v_eff/c` can be checked per
  policy); `mean_wasted_hop_pc` / `mean_settle_hop_pc` are the mean lengths of lost-race and
  winning trips. Pure functions of fold state, no RNG, do not perturb the pinned baseline
  (test `test_new_observables_do_not_perturb_the_pinned_fold`). The slingshot policies self-limit
  near `v_eff ~ 2500-3900 km/s` (`Λ ~ 0.01`), which is why they sit at the low end of the tax
  and cannot reach the directed-energy regime.
- **`max_retargets = 8` `[ESTIMATE]`** - a **bookkeeping** cap, not physics: a probe that loses
  this many races is retired (bounding stale-view bounce chains). Applied to **both** coordination
  modes (symmetric), so the paired wasted-journey comparison is fair - `instant` also loses
  in-transit races and re-targets, so capping only `lightspeed` would inflate `instant`'s waste.
  The measured fuel tax at `Λ=0.2` (powered, N=400, 32 seeds) *converges* with the cap rather than
  being flat: +6.3 / +12.9 / +18.4 / +20.4 / +20.4% at cap = 2/4/8/16/32. It rises while the cap
  still truncates live bounce chains, then saturates by cap ~16. The default cap = 8 sits near
  convergence (+18.4%, ~90% of the +20.4% asymptote) - a mild lower bound, not a knob the result is
  blind to. Honest correction of an earlier "insensitive" note (`experiments/measure.py::retarget_cap`).

- **Plateau-locator threshold `= 0.05` `[ESTIMATE]` - a diagnostic tolerance, not a physical
  number.** Issue #73's `--locate-plateau` finds `cap*(N)` from the instant-only bounce depth
  `b = W_inst / N` (arrivals per star): the smallest cap `k` where doubling to `2k` moves the
  median `b` by less than the threshold. `0.05` is a step in `b` (units: arrivals/star), a tunable
  knob on the tool (every use site exposes `--plateau-threshold`), not a measured quantity. Its
  default is motivated by the committed N=400 rows, where the converged step is `Δb = 0.000`
  (cap 16→32) and the last still-climbing step is `Δb = 0.120` (cap 8→16): `0.05` sits cleanly
  between them, so the locator returns `cap* = 16` at N=400 and (correctly) *no plateau* at
  N ≥ 32 768 where `b` never flattens (see `experiments/SPEC_PLATEAU_LOCATOR.md`,
  `experiments/measure.py::locate_plateau`, `tests/test_winst_locator.py`). The `Δb ⇔ Δτ`
  correspondence the shortcut rests on is pinned against `retarget_cap*.json` in that test.

**Modelling assumptions (stated as assumptions, not measured facts - §1):**
- **A settled star is an omnidirectional beacon emitting at year `settled_year[i]`.** No relay,
  no directionality.
- **Decision-site knowledge only (in `lightspeed`).** Belief is evaluated at the decision star at
  decision time, so news a probe's worldline passes *through* mid-flight is ignored. This
  **undercounts** knowledge → probes are pessimistic → `lightspeed` is a **conservative upper
  bound** on redundant effort. The optimistic complement is now implemented as
  `coordination="inflight"` (below); true probe-to-probe **gossip relay** of the settled map
  remains a deferred sibling, and `inflight` (beacon-only) is a conservative subset of it.
- **`coordination="inflight"` - the physical-floor bound.** A probe listens *while flying*: when
  the beacon from its now-claimed target overtakes it, at the closed-form time
  `t_learn = (settled + (v/c)·arrive)/(1 + v/c)`, it aborts the doomed hop at its interpolated
  mid-flight position and re-aims at cruise speed. Event-exact (the loop advances to the
  global-minimum actionable time, so no learning is ever skipped - no dt artifact). It is the
  optimistic bound on what in-flight relay recovers; the floor finding below reports it.
- **Fixed stars / stellar proper motion (inherited idealization).** Stars carry velocity vectors
  (for the slingshot boost) but are held **fixed in position**, following both source models:
  Nicholson & Forgan 2013 and Forgan, Papadogiannakis & Kitching 2013 each freeze positions and
  each flag it as their *most important* simplification. It is a real idealization on the fill
  timescale - at the local circular speed (~220 km/s, [kerr-lynden-bell-1986]) a star sweeps
  ~225 pc/Myr (220 × 1.0227 pc·Myr⁻¹·(km/s)⁻¹), and even the peculiar component alone (~30-40 km/s
  thin-disc dispersion, [nordstrom-2004-gcs]) carries it ~31-41 pc/Myr, far past the ~1 pc mean
  hop - so proper motion would reshuffle which stars are near which over a Myr fill. It is **bounded
  for our relative result**: both coordination modes run on the *identical* frozen field, so the
  paired difference still isolates the light-lag effect; it remains a genuine limitation on
  *absolute* fill times. The narrower worry that the belief gate itself needs *retarded* stellar
  positions (the beacon leaves where the star was) is separately negligible: during a beacon's
  light-crossing a star moves only the fraction `v_star/c ~ (40 km/s)/c ~ 1e-4` of the distance it
  signals across, a hundredth of a percent, so the gate geometry is right at decision time; the
  idealization is the slow Myr-scale layout drift, which the paired design controls. (Displacements
  derived from the two `[ESTIMATE]` speeds; sources ground those speeds.)
- **Pure lag still fills a connected field to 100%** (re-targeting guarantees it). A
  steady-state settled fraction `X_eq = 1 − T_launch/T_settle < 1` (Carroll-Nellenback's
  "Aurora effect") requires a settlement *death* term - a separate sibling, not lag alone.
- **Probes built are ~mode-independent.** Both modes fill the field and each settlement launches
  `offspring` probes, so `total_probes_launched` differs by only a handful of terminal launches
  (well under 1%, no systematic sign at low `Λ`, ~+0.5% at `Λ=0.2`). The coordination cost is
  therefore redundant TRAVEL (wasted journeys), not extra manufacturing.

**Energy accounting (why we do NOT headline an energy tax; §1, §3).** An earlier revision weighted
each wasted journey by its Newtonian specific kinetic energy `(1/2)(v/c)²` and reported an "energy
tax" several times the journey-count tax for the slingshot policies. We retract that as a headline:
it double-counts. Under the slingshot policies the probe's kinetic energy is **gravitationally
sourced** (extracted from stellar motion, Nicholson & Forgan) rather than spent as propellant, and a
probe that re-targets on arrival keeps its speed and pays nothing further - so weighting a wasted
slingshot trip by its full `(1/2)v²` counts free energy as a fuel cost. The genuine energy cost of a
wasted trip is **mission-dependent**: the braking + re-acceleration a rendezvous needs (~`v²` for a
fuel-braked craft; [lubin-2016] notes beamed sails carry no braking beam), or ~0 for a flyby or a
gravitational capture. Our scalar-speed fold does not model deceleration, so we denominate the tax
in **journeys** and give the energy reading only as a mission-conditional bound (0 for a flyby,
~`v²` for a fuel rendezvous). The read-only accumulators `settle_energy_c2` / `wasted_energy_c2`
(sums of `(1/2)(v/c)²`, no RNG, pinned baseline unchanged) and `experiments/measure.py::energy_tax`
remain available for anyone wanting the KE-weighted numbers, but the paper does not feature them.
(Arithmetic, for reference: `(1/2)Λ² =` 5.0e-5 / 1.25e-3 / 5.0e-3 / 2.0e-2 at `Λ` = 0.01/0.05/0.1/0.2;
the relativistic `(γ−1)c²` exceeds Newtonian by < 3.1% up to 0.2c.)

**Finding (paired ensemble, event timestep).** Several parts, all deterministic.

*No fill-time tax; the coarse-dt one is an artifact* (`experiments/dt_artifact.py`). With the
slice-1 fixed `dt=5000 yr` the fill-100% penalty for slingshot-nearest looks like a robust
median **+30.3%** (32/32 seeds). It is an artifact of the step: a fixed dt >> hop time batches
many launches into one window so they decide from the same stale snapshot and collide. Refining
the step, the penalty falls monotonically - **30.3 → 27.6 → 25.0 → 12.8 → 5.3%** at dt =
5000/2000/1000/500/250 - and at the event (dt→0) limit it is **+0.0%**, no longer distinguishable
from zero. The same refinement restores the slingshot-vs-powered speedup to N&F's full ~two
orders of magnitude (**~166x**), where the coarse step gave only ~20x. **The tens-of-percent
fill-time tax was the artifact**; at the resolved timestep the fill-time cost is ~0 at slingshot
speeds and only a few percent at directed-energy speeds (below), far below the redundant-travel cost.

*The real cost is redundant travel, governed by `Λ = v/c`* (`experiments/measure.py::lambda_sweep`).
Probes-built is ~mode-independent (above), so the coordination cost is wasted journeys. For powered
flight swept across the speed axis (N=500, 512 seeds, lightspeed vs instant; the headline is cheap at
N=500 (~1.6 s/paired seed), so it is sized to a precision target, not to compute), the fuel tax (extra
wasted journeys as % of the perfect-info waste), median [bootstrap 95% CI], (seeds positive):
  - `Λ=0.01`: **+0.7% [0.7, 0.8]** (442/512)
  - `Λ=0.03`: **+2.5% [2.3, 2.7]** (460/512)
  - `Λ=0.05`: **+4.5% [4.1, 4.8]** (471/512)
  - `Λ=0.10`: **+9.3% [8.9, 9.6]** (498/512)
  - `Λ=0.20`: **+19.3% [18.8, 20.1]** (512/512)

  The delay adds wasted journeys IN EXPECTATION; the sign is statistical, not structural - retarget
  cascades make the paired difference non-monotone per seed (68 of 512 negative at Λ=0.01), so the
  median and its CI, not a sign test, are the finding. Where informative, a two-sided sign test agrees
  overwhelmingly (442/512 positive at Λ=0.01, all 512 at Λ=0.2). (Honest correction of a round-1
  "sign is built in" overclaim.)

  *Derived law (collision model), confirmed.* The measured tax follows **`tax ≈ Λ`**: a through-origin
  fit gives slope **0.95** (the exposure model predicts exactly 1), and the raw ratio
  `waste_ls / waste_inst` tracks **`1 + Λ`** almost exactly - 1.010 / 1.051 / 1.099 / 1.199 measured
  against 1.010 / 1.050 / 1.100 / 1.200 predicted at Λ = 0.01/0.05/0.1/0.2. The argument (a blind stale
  window `d/c` added to the travel exposure `d/v` gives ratio `1 + v/c`) is in the paper as a numbered
  equation; it also predicts the observed hop-length- and density-independence (both cancel).

  *Fill-time tax: small, regime-dependent, not a tail spike.* A companion fill-time tax rides along:
  median 0.0 / 0.0 / 0.6 / 2.2 / **6.0%** across Λ = 0.01/0.03/0.05/0.1/0.2. At 512 seeds it is a clean
  [0,0] for Λ ≤ 0.03 (a genuine null, not an unresolved margin), becomes resolvable at Λ=0.05
  (0.6% [0.3,0.9]) and is unambiguous by Λ = 0.1. It is present throughout the fill, not concentrated
  at the end: at Λ=0.2 it is +4.0 / +4.7 / +5.3 / +6.0% at t50 / t90 / t99 / t100. The near-constant in-flight
  population (~480, still near-peak at 99% coverage) holds it to ~1/3 of the fuel tax rather than zero.

*Contention scales with branching, without saturating* (`experiments/measure.py::branching`, N=400,
32 seeds). The tax grows with the offspring branching factor and does NOT level off over the range
tested (2 to 16 offspring): at `Λ=0.2`, +18.4 / +24.9 / +25.5 / +31.9 / +36.5% for offspring =
2/3/4/8/16 (the intervals at 8 and 16 are disjoint from those below); at `Λ=0.05` it climbs gently,
+5.8 / +5.6 / +6.0 / +7.8 / +9.6%. The tax keeps rising roughly linearly in the logarithm of the
branching factor, so the default of 2 is a genuine lower bound, not a plateau - a factory that
branches harder pays a larger tax, reaching about a third more wasted journeys at 16 offspring. This
is an honest correction of a round-1 note that read the 24.9-to-25.5% step (offspring 3 to 4) as
saturation: carrying the sweep to 16 shows that was an artifact of where it stopped. The growth is
in the tax's coefficient, not its scaling - the whole `Λ=0.2` column stays of order `Λ` (18 to 37%),
so the `v/c` law holds at fixed branching and the branching factor sets its coefficient.

*Why the time cost stays below the fuel cost: concurrency* (`experiments/measure.py::concurrency`,
N=500, 16 seeds). A median ~480 probes are in flight at the peak of a fill, and the population stays
near that peak into the final percent (~478 at 99% coverage; branching launches until stars run out),
nearly identical between the two regimes (~470 vs ~480). So the fills proceed almost in lockstep and
the light-lag swarm falls behind only by the small rate at which wasted trips dilute its productive
settlements - holding the time tax to ~1/3 of the fuel tax rather than to zero.

*Physical floor: relaying in flight* (`experiments/measure.py::floor_bracket`, N=400, 48 seeds,
powered). The decision-site (`lightspeed`) tax is an upper bound. Under `inflight` (a probe listens
while flying and aborts a doomed hop when its beacon overtakes it) completed wasted arrivals fall to
**0** at every `Λ`, and redundant travel drops BELOW even the perfect-info baseline (at `Λ=0.2`:
~3580 pc lightspeed, ~2930 pc instant, **~1640 pc inflight**), because listening also averts the
assignment collisions perfect knowledge leaves. Cost: mid-flight detours lengthen the fill by ~2% at
`Λ=0.2`. So in-flight relay recovers essentially all of the wasted-arrival tax; the residual floor is
the partial travel flown before a beacon arrives, which grows with `Λ`.

**Fuel tax vs scale (`experiments/measure.py::finite_size`, powered, `Λ=0.2`, event, high-seed).** As
a *percent* of the perfect-info waste the tax holds near ~18-19% up to ~1000 stars then DECLINES at
larger fields - **+19.0 / +18.2 / +17.9 / +16.3 / +13.1%** at N = 300 / 600 / 1200 / 2400 / 4800
(48 / 48 / 48 / 48 / 32 seeds; the super-linear per-run cost caps N, not the seed count - see
**Performance and the scale ceiling** below) - while the *absolute*
wasted-journey count grows with the field (median +237 / +494 / +1056 / +2228 / +4010). With 32-48
seeds per point the decline is **resolved, not scatter**: the bootstrap CIs at N=300 ([+16.4,+22.5])
and N=4800 ([+11.6,+14.0]) do not overlap. This is an honest correction of a round-1 "scale-stable
fraction" claim (which rested on a 4x span to N=1200): over a 16x span the fraction does NOT grow with
scale, it gently shrinks, so there is no support for extrapolating a fixed-percentage tax to a
10¹¹-star galaxy. (An earlier 4-seed N=4800 point read ~11%; 32 seeds tighten it to 13.1%.)

**Density-rescaling invariance (checked):** changing the *uniform* density rescales every
distance by a common factor, so travel time and light-time scale together and `Λ` (hence the
relative penalty) is unchanged - a pure geometric rescaling of the absolute clock, confirmed to
the printed digit across 0.14 → 5 stars/pc³.

**Clumpy (non-uniform) field (`experiments/measure.py::clumpiness`, event, 48 seeds, N=500):** the
sharper test the density rescaling does NOT settle. A non-uniform field is where the law could
genuinely break: hop length and local claim rate can correlate, and the `d`-cancellation in
`tax = Λ` assumes a locally uniform claim rate. We place the stars with a **Thomas cluster process**
(`n_clumps = 25` centres; each star scattered `parent + Gaussian(σ)` and reflected into the box, so
`N` and the mean density are held EXACTLY fixed - only the spatial arrangement changes) and sweep the
scatter `σ/L` from the uniform limit to strong clustering, crossed with `Λ ∈ {0.05, 0.1, 0.2}`.
Clumpiness is reported by the measured **Clark-Evans aggregation index R** (observed / Poisson mean
nearest-neighbour distance; `R = 1` uniform, `R < 1` clustered). Result: the through-origin slope `a`
of `tax = a·Λ` is `0.97 [0.89, 1.19]` at the uniform null (reproducing the headline `0.95` - the
generator's hard correctness check), stays statistically consistent with 1 up to moderate clustering
(`a = 0.90, 0.86, 0.88` at `R = 1.03, 0.97, 0.78`), and drops resolvably only at EXTREME substructure
(`a = 0.51 [0.41, 0.70]` at `R = 0.56`, more clumped than a dynamically-relaxed stellar field). Every
deviation is DOWNWARD, so **`tax = Λ` is a conservative upper bound**: clumpiness makes the coordination
tax smaller, never larger. Mechanism (the hop-length-stratified wasted-trip ratio in the same JSON):
the per-hop ratio `p_lag/p_perfect` is squeezed below `1 + Λ` wherever the baseline per-hop waste
probability approaches 1 (long hops, dense clumps) - a **saturation** effect, identical in shape between
uniform and clumpy fields, which is also why the measured slope is `0.95` and not a clean `1.0`. Since
`v` and `c` are global constants they factor out of both exposure sums, so the `(d, claim-rate)`
correlation cancels EXACTLY in the linear regime; clumpiness can bite only through this saturation. The
knobs are geometry, not measured physical quantities: `n_clumps = 25` (~20 stars/clump at N=500, dense
enough to over-subscribe under 2-offspring branching) and the `σ/L` ladder are a swept dimensionless
robustness axis `[ESTIMATE]`; the Clark-Evans Poisson expectation uses the 3D coefficient
`E[NN] = 0.55396·ρ^(-1/3)`, with `0.55396 = Γ(4/3)/(4π/3)^(1/3)` derived from the Poisson
nearest-neighbour distribution (Clark & Evans 1954).

**Baseline validation (`experiments/measure.py::validation`, event).** (1) `"instant"` is the c→∞
limit of the gate and reproduces the plain perfect-info fold **bit-for-bit** (pinned by
`test_instant_mode_is_the_perfect_info_baseline`). (2) We reproduce Nicholson & Forgan
**quantitatively** at the resolved timestep: slingshots ≫ powered (nearest fills a 400-star field
~166× sooner than powered - their ~two orders of magnitude, where the coarse dt=5000 fold gave
only ~20×), and **nearest beats maxboost on time** while maxboost reaches the higher peak speed.

**The measurement/figure pipeline (heavy compute stays local; §2, §4).** The full ensemble runs in
`experiments/measure.py`, which writes deterministic seeded JSON to `experiments/results/*.json`
(committed). That heavy driver is **kept out of CI** - it is minutes-to-hours of compute. The paper
figures are then RENDERED from the committed JSON by `experiments/paper_figures.py` (no simulation),
which CI runs in a few seconds; `tests/test_measure_results.py` re-runs a tiny slice of each
measurement and asserts it still matches the committed JSON, so the artifacts cannot drift from the
fold. Seven figures regenerate: `fig_fuel_tax_vs_lambda` (headline, with the derived `tax = Λ` line
overlaid), `fig_fuel_tax_by_seed`, `fig_time_tax_vs_dt`, `fig_concurrency` (mechanism),
`fig_branching`, `fig_floor_bracket`, and `fig_fuel_tax_vs_n` (scale). The energy-tax figure was cut
(see the energy-accounting note above). Regenerate the numbers via
`uv run --extra dev python -m experiments.measure` and the figures via
`uv run --extra dev python -m experiments.paper_figures`.

## Performance and the scale ceiling (issues #27, #30)

The fold was sped up to push toward Nicholson & Forgan's 200,000-star field, under a hard
constraint: **every change is bit-identical** - the committed `results/*.json` reproduce to the
printed digit (`tests/test_measure_results.py` stays green) and the pinned-baseline tests are
unchanged. Timing never changes a number (the fold is a pure seeded function, CLAUDE.md 7); these
are wall-clock changes only.

Profiling a large-N run (`experiments/scaling_benchmark.py`) showed the cost was **four** O(N)- or
O(P)-per-event terms, not the one the nearest-neighbour scan alone. Three were removed outright:

- **Cell-list nearest-neighbour index.** `_nearest_unsettled_at` / `_nearest_k_unsettled_at`
  replace the O(N) linear scan with a uniform grid of `grid_res = round(N^(1/3))` cells per axis
  (`grid_res³ ≈ N`, so ~1 star per cell at the paper's 1 star/pc³), built once over the fixed
  positions. A query expands cell shells outward and stops once the best distance provably beats
  every unexamined cell. It reproduces the linear scan's `(distance, lowest-index)` result exactly
  (the equality case expands one more shell so boundary ties keep the lowest index). The plain,
  non-wrapped metric matches target selection, which never uses the periodic minimum image.
- **Event heap.** A lazy min-heap of `(actionable_year, probe_id)` plus an id-keyed `probes` dict
  replaces the O(P) `min`-over-all-probes each event and the O(P) probe-list rebuilds. Under
  `inflight`, a settled star reschedules the probes still heading to it (the decrease-key: their
  mid-flight learning time), via a `by_target` index; stale heap entries are discarded on pop.
- **Incremental snapshot.** `settled_count` and `front_radius` are maintained at the single settle
  site instead of rescanned O(N) every event. (`n_settled()` / `_front_radius()` remain as the
  O(N) ground truth used once at the end - a built-in cross-check against the incremental values.)

Together these make the **event loop and bookkeeping near-linear**, and the whole run 5-9x faster
at N ≈ 2400-4800. The seed ensemble is also parallelised across cores (`experiments/measure.py`,
`experiments/lightspeed_coordination.py`; `SWARM_WORKERS` env, `=1` forces serial), giving another
~N_cores, bit-identical because each `(seed, mode)` run is independent and results are re-collected
in seed order.

**The #27 ceiling, and how #30 broke it.** After #27 a single run still stayed **super-linear
(empirically ~O(N²))**, and a flat cell list could not fix it. The reason is intrinsic: a wasted
probe re-targets from wherever it landed - often deep inside the already-settled core - and the
nearest *believed*-unsettled star from such a point sits out at the front. That is a genuinely
**non-local** query, so the ring search had to expand out to the front (some queries spanning the
whole box; measured `cells/query` grew with N). Under `lightspeed` the target may even be a
recently-settled star whose beacon is still in transit, so the truly-unsettled set alone does not
answer it.

Issue #30 replaced the flat cell list with a **k-d tree over the unsettled set**
(`sim._build_kdtree`, `sim._nearest_unsettled_at`). It is a balanced median-split tree built once
over the fixed positions, carrying two aggregates maintained as stars settle (`_kd_mark_settled`,
O(depth) per settle):

- `kd_nuns[node]` - the count of still-unsettled stars in the subtree (a deletion counter), and
- `kd_tsmax[node]` - the latest `settled_year` in the subtree.

A branch-and-bound nearest search then prunes two ways, and **each prune only ever skips stars that
cannot be the answer**, so the argmin over the stars actually examined is bit-identical to the old
linear scan (same `(distance, lowest-index)` tie-break; verified directly in
`tests/test_kdtree_oracle.py` against a brute-force reference, and end-to-end by the pinned-baseline
and JSON drift-guard tests):

- **Distance prune** - skip a subtree whose nearest possible point is strictly farther than the
  best found (a true lower bound, so nothing skipped could beat or tie it; equality descends, so a
  same-distance lower-index star is never lost).
- **Belief prune** - skip a subtree provably entirely *believed*-settled from the query point:
  every star settled (`kd_nuns == 0`) and, for the light-delayed regimes, the beacon of even the
  most-recently-settled star (`kd_tsmax`) already reached the box's farthest corner
  (`kd_tsmax + dhi/c ≤ year`, mirroring the leaf gate's own arithmetic so the bound is exact).
  This is the **news-in-transit** correctness point: a recently-settled star whose beacon is still
  in flight is *not* pruned - it is believed-unsettled and a valid target, so it is examined.

The effect is that the settled core is skipped in O(log N) and a deep-core-to-front query examines
a near-**constant** local patch (a few leaves, ~tens of candidates) instead of O(core). The residual
mild super-linearity is not the index: it is (i) the model's own arrival count, which grows
**~N^0.09 per star** as a larger field breeds more stale-view races (a physics/combinatorics
property of the racing model, unchanged by any index), and (ii) the O(log N) tree descent. The
local scaling exponent drops from the old ~2 toward ~1 (the doubling-ratios keep shrinking as the
polylog flattens), and the `finite_size` / `finite_size_interior` / `finite_size_periodic` sweeps
now reach **N = 200,000** (a single run fills in ~140-170 s; seeds are scaled to a precision target,
not to compute). Out of scope, as in #27: no Rust beyond a pure `pyo3` drop-in, no distributed
ensemble, no GPU.

**What the 200,000-star reach shows.** The long lever arm confirms and extends the paper's scale
result. The coordination-tax paper already reports that the redundant-travel (fuel) tax as a
*fraction* of effort does not grow with N - it trends downward, a genuine bulk decline that survives
a periodic-box control - but measured over only a 16x range (N <= 4800), because the old O(N^2) cost
capped the sweep there. The k-d tree removes that cap, so the committed `finite_size` sweep now spans
a ~670x range (N = 300 .. 200,000), and the decline continues and accelerates:

| N | 300 | 600 | 1200 | 2400 | 4800 | 9600 | 24000 | 48000 | 200000 |
|---|---|---|---|---|---|---|---|---|---|
| fuel tax % (median) | 19.0 | 18.2 | 17.9 | 16.3 | 13.1 | 11.2 | 6.4 | 3.5 | **1.5** |
| seeds | 48 | 48 | 48 | 48 | 32 | 32 | 24 | 16 | 8 |

**P2 companion ladder (Issue #38 p2 scope, `experiments/results/*.json`).** Every
committed measurement JSON now carries a **top-level `p2` key** with a companion
sweep at `n_stars = 2^k` alongside the historical (non-p2) block. Historical top-level
keys (`config`, `data`, `scale_regression`, ...) are untouched byte-for-byte and their
drift guards stay load-bearing; the `p2` companion adds its own self-contained
`{config, data, scale_regression}` under `p2`. Sweep sizes:

- **N-sweeps** (`finite_size`, `finite_size_interior`, `finite_size_periodic`):
  historical ladder `[300, 600, 1200, 2400, 4800, 9600, 24000, 48000, 200000]` with
  p2 companion `[256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 262144]`. Nine
  points each; seed counts match historical rows exactly so the two lever arms are
  directly comparable.
- **Scale companions** (`*_scale.json`, historical N=200_000): p2 companion at
  N=262_144, the next power of two above 200k. Same seed counts.
- **Fixed-N base sweeps** (`branching`, `concurrency`, `floor_bracket`,
  `retarget_cap`, `lambda_sweep`, `dt_artifact`, `validation`, `clumpiness`,
  `energy_tax`): p2 companion at N=512. Historical N was 300/400/500 depending on
  the sweep; N=512 is a shared p2 anchor 2%-70% above historical.

Byte-identity of the flat vs pointer path at matching p2 N is proven in
`swarm/tests/test_flat_run_fill_oracle.py`, so p2 numbers are trustworthy to the
same standard as the frozen non-p2 numbers - and the p2 pass exercises the fast
path (`run_fill_flat`; PR #80) end-to-end for every measurement. The p2 companion
also gives every headline claim a second lever arm: the tax-vs-N slope from
`finite_size.p2`, the tax-at-scale question from `*_scale.json.p2`, and the
"does the shape hold?" cross-checks from the fixed-N base sweeps.

Generated with `uv run --extra dev python -O -m experiments.measure --p2`; the
p2 key is skipped if already present unless `--force` is passed. See
`swarm/experiments/SPEC_P2_LADDER.md` for the full schema and sweep-size
justifications.

**The coordination-tax paper cites the p2 ladder as canonical (Issue #38).** Every
quantitative claim in `papers/coordination-tax/` now sources from the `p2` keys
above (the ladder `run_fill_flat` computes; figures read them via
`experiments.paper_figures.load(..., p2=True)`).

**Each fixed-N base sweep runs at its own 1-minute-ceiling N.** Rather than a shared
N=512 anchor, every fixed-N p2 base sweep runs on the largest power-of-two field it
completes in <= ~1 min wall-clock at SWARM_WORKERS=8 on k02 (`P2_FIXED_N` in
`experiments/measure.py`; the folds are deterministic, so N is a pure wall-clock
choice). The chosen N and their measured wall-clock: lambda_sweep 2048 (30.7s),
branching 8192 (57.9s), energy_tax 2048 (57.3s), concurrency 32768 (33.3s),
floor_bracket 32768 (64.2s, marginally over and kept),
dt_artifact 8192 (53.4s, fixed-step rows use the pointer path so this caps lowest),
clumpiness 4096 (26.4s). The measurements therefore sit at different points on the
size decline, and the paper reads each on its own terms rather than as a shared-N
cross-check.

One deliberate exception to the 1-minute ceiling: **retarget_cap runs at the top of
the ladder, N=262,144 (723s @ 32 seeds, k02)**, not its 1-min N. Its p2 companion
exists precisely to test whether the cap=8 plateau survives to scale, and that
finding is sharpest at the largest field; the wall-clock cost is paid once and
committed. This puts it at the same N as `retarget_cap_scale`'s p2 companion (8
seeds), so the two are an independent 32-seed / 8-seed cross-check at N=262,144.

Two exceptions stay on the historical (non-p2) block:
- The Nicholson & Forgan speed-up replication (`validation.json`, "about 166x on a
  400-star field, against their factor of about 100") is kept on the historical
  N=400 measurement, because its whole purpose is to reproduce the external result
  at a comparable field.
- The clumpiness slope narrative (`clumpiness.json`, `fig_fuel_tax_vs_clumpiness`)
  stays on the historical N=500 ensemble, because its scale companion
  (`clumpiness_scale.json`) is the one measurement Issue #38 left without a p2
  rerun. The `clumpiness_scale` uniform slope (a = 0.078 at N=200,000) is likewise
  the historical value the paper still quotes at scale.

**Two findings that the larger fields turned from clean claims into honest caveats
(these are results, not bugs):**
- The headline through-origin coefficient of tax = a*v/c is a = 0.069 at the N=262,144
  headline field (`lambda_sweep.json` p2, 128 seeds), resolvably below the derived ceiling of
  one. The v/c *form* holds; the coefficient sits below one because saturation
  removes waste the delay would add, and it *declines with N*: a ~ 0.97 at N=500
  (clumpiness), ~0.85 at N=2048 and ~0.71 at N=4096 (from finite_size tax/Lambda), 0.069 at
  the N=262,144 headline, and 0.040 at the N=524,288 scale companion. The paper reframes
  "tax IS v/c" as "tax scales as v/c with a coefficient below one that shrinks with N," and the
  Lambda=0.2 headline fuel tax falls from ~16% (N=2048) to ~1.3% (N=262,144).
- The retarget-cap plateau that justified the default cap=8 does not survive to
  scale (`retarget_cap.json` p2, now at N=262,144, 32 seeds): the tax climbs
  monotonically 0.27/0.27/1.31/4.79/8.97% across caps 2/4/8/16/32 with no levelling,
  so cap=8 captures only ~15% of the cap-32 tax (the shortfall grew from ~40% at the
  earlier N=32,768 companion - the plateau is *more* absent at larger N). The 8-seed
  `retarget_cap_scale` p2 at the same N=262,144 agrees (0.27 .. 8.60%). cap=8 is
  documented as a *lower bound* whose downward bias grows with N; every fuel-tax
  figure using it is "at least this much."
- The in-flight-relay fill-time cost at Lambda=0.2 is ~27% at the N=262,144 headline
  (`floor_bracket.json` p2, 32 seeds), and ~28% at the N=524,288 scale companion; the
  relay still drives completed wasted arrivals to exactly zero, at a substantial fill-time price.
- New at scale: the *fill-time* tax overtakes the *fuel* tax. On the N=262,144 headline the
  Lambda=0.2 fill-time (completion) tax is ~10.5% [8.9,13.3] against a ~1.35% fuel tax - the
  parallel population dilutes wasted-arrival (fuel) waste as N grows, but not the front lag at the
  fill tail, so the small-field "fuel-dominated" ordering reverses at galactic scale.

**Flat p2 kd-tree substrate (Issue #38 p2 scope, `swarm/rust/`).** For sweeps
at `n_stars = 2^k, k >= 3`, `swarm_rust` exposes a second, heap-indexed kd-tree
where children of node `i` sit at `2i+1` and `2i+2` and the parent at
`(i-1) >> 1` - so the `lo`, `hi`, `parent` arrays vanish and each leaf's 8 stars
are stored contiguously in permuted coordinate arrays. Same median-split rule as
the pointer tree above (widest axis, sort by `(coord, index)`, split at
`len/2`), which at matching p2 N makes the flat tree partition-identical -
verified as bit-identical `nearest_unsettled` answers across `N in {8, 16, 32,
128, 512, 4096}` and half-settled interleaved settle/query schedules
(`swarm/tests/test_flat_kdtree_oracle.py`, 36 tests, mutation-red-teamed for
parent-walk / tie-break / leaf-boundary bugs). The immediate query-side
wall-clock win is ~4% at N in {1024, 4096, 32768}
(`swarm/experiments/bench_flat_kdtree.py`), and the whole-fill loop
(`run_fill_flat`) posts a 1.3-1.8x speedup on the same sizes because the
per-query win compounds through ~2M event-loop nearest queries and, under
inflight, the decrease-key reschedule path
(`swarm/experiments/bench_flat_run_fill.py`). `simulate_swarm` at p2 N now
dispatches to the flat path automatically (byte-identical to the pointer path,
verified in `swarm/tests/test_flat_run_fill_oracle.py` across the three
coordination modes and periodic/non-periodic). The substrate value beyond
this is the SIMD-ready 8-star contiguous leaf memory (each leaf fills 1
AVX-512 lane or 4 AVX-256 lanes worth of f64), reserved for a follow-up. The pointer tree stays
in place at non-p2 N to keep the frozen result JSONs as oracles; see
`swarm/rust/SPEC_FLAT_KDTREE.md` for the layout, API, and non-perfect-p2 escape
paths. Reference: Bentley (1975), "Multidimensional binary search trees",
CACM 18(9):509-517 (the median-split kd-tree); the heap-indexed flat layout is
the standard perfect-binary-tree array embedding, applied here to a kd-tree.

The 300..4800 records are byte-identical to the prior committed sweep (the fold is bit-identical);
the higher-N points are new. OLS regression of the median tax on log10(N) over the full ladder is
**-7.0 percentage points per decade** (95% CI [-7.8, -6.4]), and the drop is convex/accelerating. At
N = 200,000 the median tax over 8 seeds is **+1.5%** (IQR [+1.4, +1.9]; instant vs lightspeed wasted
arrivals ~1.79M vs ~1.81M). So at galactic scale the light-speed coordination fuel tax as a fraction
of total effort largely *vanishes*; the absolute wasted-journey count still grows with the field
(237 -> 27,073 median), it is the fraction that falls. This does not overturn the paper - it
sharpens it: the paper's downward trend and its bulk-not-boundary conclusion (the interior-masking
and periodic-box controls of referee finding M1) now hold over ~670x instead of 16x, and the
extrapolation caution ("a sixteen-fold lever arm cannot support" a galactic-scale claim) is stated
against a much longer arm. The `finite_size_interior` and `finite_size_periodic` edge controls are
regenerated to the same 200,000-star range so the bulk-vs-boundary comparison holds at scale.

**Scale companions: every fixed-N sweep repeated beyond the headline.** With the k-d tree unlocking
the sweep at large N, we repeat each fixed-N measurement of `tab:ensembles` at scale
(`*_scale.json`, seed count set to the finite-size sweep's precision target). This turns each
result into a paired claim: the fixed-N number for a tight CI on the coefficient, and the
scale companion to test whether the number was a scale-dependent artifact. Since the at-scale batch
moved the fixed-N sweeps themselves to N=262,144, the `p2` scale companions now run one power of two
further, at **N=524,288** (the paper's canonical scale point; `clumpiness_scale` stays at 200,000 with
no p2 rerun, and `retarget_cap_scale` stays at 262,144 as the 8-seed cross-check). The top-level
(non-p2) `*_scale.json` blocks below stay at N=200,000, byte-identical to before.

- `concurrency_scale.json` - the median peak in-flight rises to ~75,500 (instant) and ~69,500
  (lightspeed) at N=200,000 (up from ~480 at N=500), and stays above 47,000 at the 99% coverage
  tail bin. The two regimes still track: this near-identical population dilutes the *fuel* waste,
  while the fill-time cost is set by the front lag at the tail (which, on the 262,144 headline,
  overtakes the fuel tax - see the "findings" caveats above).
- `lambda_sweep_scale.json` - the through-origin slope `a` of tax = a*Lambda drops from
  ~0.97 at N=500 to ~0.076 at N=200,000, a ~13x reduction that matches the finite-size
  decline of the tax at fixed Lambda. Linearity persists (fuel taxes: -0.13, 0.16, 0.40, 0.82, 1.52
  percent at Lambda = 0.01, 0.03, 0.05, 0.1, 0.2 respectively); only the coefficient rescales.
- `floor_bracket_scale.json` - at N=200,000 the wasted-arrival count under `inflight` is exactly zero
  at every Lambda in {0.05, 0.1, 0.2} across all eight seeds. The N=400 result "recovers nearly all
  of it" tightens to "recovers all of it" at scale. Wasted travel drops 80-96% (probes still burn
  distance before aborting).
- `clumpiness_scale.json` - the slope `a` is flat across the Thomas-clump ladder at N=200,000:
  0.078, 0.076, 0.088, 0.072, 0.076 across uniform / sigma=0.30 / 0.15 / 0.08 / 0.05 (matching the
  speed-sweep-companion uniform slope within noise). The exposure-cancellation argument holds over
  the ~670x scale span crossed with a ~4.5x span in Clark-Evans R. Note: `n_clumps=25` is held
  fixed with N, so at 200,000 the tightest sigma has ~8,000-star mega-clumps by design.
- `retarget_cap_scale.json` - the fixed-N insensitivity plateau at cap>=8 (N=400: 18.4%, 20.4%,
  20.5% at caps 8, 16, 32) moves right at scale. At N=200,000 the tax climbs monotonically from
  0.27% (cap=2) to 9.11% (cap=32) and does not saturate over the tested ladder. This is a
  bookkeeping-cap sensitivity, not a physical claim: the finite-size number the paper reports uses
  the same default cap=8, so the 1.5% headline at N=200,000 is unchanged. But the paper's operating
  claim "the tax is insensitive to the cap" is a statement about being on the small-N plateau, not
  a general one; at 200,000 stars we sit on the ascending part of the curve, and how far the
  plateau extends at galactic scale is a natural next question.
- `branching_scale.json` - **not committed**: at offspring=16 with N=200,000, the per-worker
  SwarmResult footprint (~1.2-2 GB peak from the ~8x more arrivals) x 4 concurrent paired workers
  saturates k02's 27 GB RAM + 8 GB swap. The at-scale branching claim is a `[GAP]` for k02 as
  written; running to offspring=8 was clean, but that alone doesn't test the paper's
  "up to sixteen without saturating" claim, so the artifact is deferred until either a wider-RAM
  machine or an intra-run memory reduction (do not retain `steps` in `SwarmResult`, or subsample it
  per bin) lands.

## Simplifications still deferred to later slices

- **Uniform cube star field** by default, not a galactic disk with a density gradient (the
  `clumpiness` measurement above tests a Thomas-cluster non-uniform field for robustness, but a
  full disk with a radial gradient is still deferred).
- **Replicate at the settled star**, not truly replicate-in-transit from the ISM (the
  effect is similar - one child per arrival, inheriting the parent's boosted speed).
- **Scalar speeds, not velocity vectors** (see the boost-geometry `[ESTIMATE]` above).
- **200k-star scale + WebGL rendering** - the frontend uses a spatial hash and canvas; the
  full 10⁵-star SoA/WebGL engine is a remaining slice (ROADMAP §4).
- **Mid-flight learning and probe-to-probe relay** - the light-speed model (now done, FRONTIER
  #1) uses decision-site knowledge only, a conservative upper bound; a two-endpoint knowledge
  cone and gossip relay of the settled map are the deferred sibling slice that would lower the
  fuel tax without removing its physical floor.

## Further reading and cross-checks (bibliography)

Sources that ground this module's ideas or cross-check its numbers, consolidated in the project bibliography (frontend/src/sources.ts) and shown on the site's Sources page. These add context; they are not new numbers in the code.

- **Forgan, Papadogiannakis & Kitching 2013** - D. H. Forgan, S. Papadogiannakis & T. Kitching (2013). The Effect of Probe Dynamics on Galactic Exploration Timescales (arXiv:1212.2371). Journal of the British Interplanetary Society 66:171-178. https://arxiv.org/abs/1212.2371. The single-probe slingshot study that Nicholson & Forgan extend to self-replicators and that swarm/REFERENCES.md defers to for the shearing-box setup and Galactic rotation speed. Establishes the headline result the swarm reproduces: slingshots cut exploration time by up to two orders of magnitude versus powered flight.
- **Bjork 2007** - R. Bjork (2007). Exploring the Galaxy using space probes (arXiv:astro-ph/0701238). International Journal of Astrobiology 6(2):89-93. https://arxiv.org/abs/astro-ph/0701238. The direct precursor to the box-of-stars exploration-timescale simulations the module runs: probes with subprobes sweeping a defined stellar volume, giving concrete fill times to sanity-check the swarm's Myr-scale fill of a finite field.
- **Newman & Sagan 1981** - W. I. Newman & C. Sagan (1981). Galactic civilizations: Population dynamics and interstellar diffusion. Icarus 46(3):293-327. https://www.sciencedirect.com/science/article/abs/pii/0019103581901354. The analytic settlement-front model behind the swarm's advancing boundary: colonization as a density-dependent diffusion process with a travelling-wave solution limited by carrying capacity - the continuum counterpart to the module's discrete nearest-hop front.
- **Jones 1981** - E. M. Jones (Los Alamos Scientific Laboratory) (1981). Discrete calculations of interstellar migration and settlement. Icarus 46(3):328-336. https://www.sciencedirect.com/science/article/abs/pii/0019103581901366. The Monte Carlo settlement model most like the swarm's own discrete fold, and a numerical check on its front speed: Jones finds a migration wavefront of ~1.4e-5 pc/yr filling the Galaxy in ~60 Myr, the same order as the swarm's front advancing at a fraction of a probe's cruise speed.
- **Hart 1975** - M. H. Hart (1975). An Explanation for the Absence of Extraterrestrials on Earth. Quarterly Journal of the Royal Astronomical Society 16:128-135. https://ui.adsabs.harvard.edu/abs/1975QJRAS..16..128H/abstract. The founding statement of the colonization / Fermi argument the module engages: if interstellar settlement is possible it should already be complete, so a Galaxy filling on a Myr timescale (which the swarm demonstrates) is exactly what makes the observed silence a paradox.
- **Tipler 1980** - F. J. Tipler (1980). Extraterrestrial Intelligent Beings Do Not Exist. Quarterly Journal of the Royal Astronomical Society 21:267-281. https://ui.adsabs.harvard.edu/abs/1980QJRAS..21..267T/abstract. Introduces the self-replicating (von Neumann) probe into the Fermi argument - the exact entity the swarm simulates: exponentially branching probes that saturate the Galaxy in a few million years, the few-Myr-fill claim the module makes quantitative and stress-tests under finite light-speed.
- **Cotta & Morales 2009** - C. Cotta & A. Morales (2009). A Computational Analysis of Galactic Exploration with Space Probes (arXiv:0907.0345). Journal of the British Interplanetary Society 62:82-88. https://arxiv.org/abs/0907.0345. A computational exploration model that turns fleet size, probe lifetime, and imprint persistence into bounds on how many civilizations could be quietly exploring undetected - framing the parameters (probe count, dwell / imprint time) the swarm exposes as knobs.
- **Forgan 2009** - D. H. Forgan (2009). A numerical testbed for hypotheses of extraterrestrial life and intelligence (arXiv:0810.2222). International Journal of Astrobiology 8(2):121-131. https://arxiv.org/abs/0810.2222. Establishes the Monte Carlo, seeded-realization methodology for Fermi-paradox questions that the swarm's deterministic seeded fold follows, situating exploration timescales within a distribution of parameters rather than single-point estimates.
- **Sheridan 1993** - T. B. Sheridan (1993). Space Teleoperation Through Time Delay: Review and Prognosis. IEEE Trans. Robotics and Automation 9(5):592-606, DOI 10.1109/70.258052. https://doi.org/10.1109/70.258052. The canonical review of how human control degrades as round-trip delay grows - closed-loop, then move-and-wait, then supervisory - and why beyond a delay budget you must hand autonomy to the remote node. Grounds the coordination-rung ladder and is the natural successor to the Ferrell pair already cited.
- **Olfati-Saber, Fax & Murray 2007** - R. Olfati-Saber, J. A. Fax & R. M. Murray (2007). Consensus and Cooperation in Networked Multi-Agent Systems. Proceedings of the IEEE 95(1):215-233, DOI 10.1109/JPROC.2006.887293. https://doi.org/10.1109/JPROC.2006.887293. The survey generalizing the 2004 delay-bound result into a full framework for consensus under switching topology, link failures, and delays. Grounds the rho = round-trip-latency / decision-timescale lens on when delayed agreement stays stable, and supports that a connected field still converges to 100% despite lag.
- **Burleigh et al. 2003** - S. Burleigh, A. Hooke, L. Torgerson, K. Fall, V. Cerf, B. Durst, K. Scott & H. Weiss (2003). Delay-Tolerant Networking: An Approach to Interplanetary Internet. IEEE Communications Magazine 41(6):128-136, DOI 10.1109/MCOM.2003.1204759. https://doi.org/10.1109/MCOM.2003.1204759. Motivates delay-tolerant networking from the interplanetary case specifically - links with light-minutes to light-hours of latency and no continuous end-to-end path. Grounds the delay-tolerant rung with the actual space-communications rationale behind RFC 4838, at the Mars/Saturn latency scale the visualization anchors use.
- **RFC 9171 (Bundle Protocol v7)** - S. Burleigh, K. Fall & E. J. Birrane III (2022). Bundle Protocol Version 7. IETF RFC 9171 (Internet Standards Track). https://www.rfc-editor.org/info/rfc9171. The current Internet-standard store-and-forward protocol for delay-tolerant links, superseding the experimental RFC 5050. Grounds the delay-tolerant rung as a deployed standard - hop-by-hop custody transfer with no real-time handshake - complementing the architecture-level RFC 4838.
- **Lamport 1978** - L. Lamport (1978). Time, Clocks, and the Ordering of Events in a Distributed System. Communications of the ACM 21(7):558-565, DOI 10.1145/359545.359563. https://doi.org/10.1145/359545.359563. Establishes that when information travels at finite speed, events have only a partial (happened-before) ordering - you cannot know a remote event until its signal reaches you. Grounds the swarm's light-delayed belief model: a probe treats star i as settled only once settled_year[i] + dist/c <= Y.
- **Fischer, Lynch & Paterson 1985** - M. J. Fischer, N. A. Lynch & M. S. Paterson (1985). Impossibility of Distributed Consensus with One Faulty Process. Journal of the ACM 32(2):374-382, DOI 10.1145/3149.214121. https://groups.csail.mit.edu/tds/papers/Lynch/jacm85.pdf. The FLP impossibility result: in a fully asynchronous system (no bound on message delay) no protocol can guarantee agreement if even one node can fail. Grounds why the fully-independent-colonies rung is qualitatively different - guaranteed real-time consensus is not merely slow but impossible, so each node acts on pre-launch priors.
- **Gilbert & Lynch 2002** - S. Gilbert & N. A. Lynch (2002). Brewer's Conjecture and the Feasibility of Consistent, Available, Partition-Tolerant Web Services. ACM SIGACT News 33(2):51-59, DOI 10.1145/564585.564601. https://doi.org/10.1145/564585.564601. The formal CAP theorem: under network partition you must trade consistency against availability. Grounds why light-delayed probes favour availability (act now on a local view) over consistency (a single global settled-map) - the mechanism that produces the wasted long-range trips measured in the lightspeed regime.
- **Demers et al. 1987** - A. Demers, D. Greene, C. Hauser, W. Irish, J. Larson, S. Shenker, H. Sturgis, D. Swinehart & D. Terry (1987). Epidemic Algorithms for Replicated Database Maintenance. PODC '87 (6th ACM Symp. on Principles of Distributed Computing) 1-12, DOI 10.1145/41840.41841. https://doi.org/10.1145/41840.41841. The foundational gossip / anti-entropy work: how state (here, which stars are settled) propagates by pairwise relay rather than central broadcast. Grounds the deferred probe-to-probe gossip-relay sibling slice named in swarm/REFERENCES.md, beyond the current omnidirectional-beacon assumption.
- **Clark & Evans 1954** - P. J. Clark & F. C. Evans (1954). Distance to Nearest Neighbor as a Measure of Spatial Relationships in Populations. Ecology 35(4):445-453, DOI 10.2307/1931034. https://doi.org/10.2307/1931034. The aggregation index R = (observed mean nearest-neighbour distance) / (expected under a Poisson process), R=1 random, R<1 clustered, R>1 regular - the measured clumpiness x-axis for the `clumpiness` experiment. The 3D Poisson expectation `E[NN] = 0.55396·ρ^(-1/3)` (coefficient `Γ(4/3)/(4π/3)^(1/3)`) generalizes their 2D form; used comparatively across fields at fixed N and box so the box edge bias cancels.
- **Thomas / Neyman-Scott cluster process** - M. Thomas (1949), A generalization of Poisson's binomial limit for use in ecology, Biometrika 36:18-25, DOI 10.1093/biomet/36.1-2.18 (https://doi.org/10.1093/biomet/36.1-2.18); J. Neyman & E. L. Scott (1958), Statistical approach to problems of cosmology, J. R. Stat. Soc. B 20:1-43. The parent-plus-offspring point process used to generate the non-uniform star field: cluster centres scattered uniformly, stars placed Gaussian around them. A standard, tunable clustering model whose scatter interpolates cleanly to the uniform limit, which is what lets the `clumpiness` sweep use the uniform slope as a hard null.
- **Lubin 2016** - P. Lubin (UC Santa Barbara) (2016). A Roadmap to Interstellar Flight (arXiv:1604.01356). Journal of the British Interplanetary Society 69:40-72. https://arxiv.org/abs/1604.01356. The far end of the propulsion spectrum for a self-replicating seed: beamed directed-energy light-sail acceleration of gram-scale craft toward ~0.2c, sidestepping the rocket-equation penalty by leaving the energy source at home. Connects to the swarm's interstellar cruise-speed assumptions.

## Invariants (issue #48, phase A)

Swarm mutates state in place, so `_verify_step_invariants(before_snap, after)` is called
under `if __debug__:` in both `step` (fixed) and `step_event` (event). The snapshot is a
small frozen dataclass holding the scalar counters plus a tuple copy of `settled_year`
(cheap at test scale, N=300; `python -O` strips both the snapshot and the checks for
the 200k-star sweeps in `experiments/`). Positive + negative tests live in
`tests/test_invariants.py`.

- **[inv:sw-year-monotone]** `after.year >= before.year`. Time never runs backwards.
  Uses `>=` rather than `>` because `step_event` no-ops when no probe is due, leaving
  `year` unchanged.
- **[inv:sw-settled-monotone]** `after.settled_count >= before.settled_count`. Stars only
  settle once; the count only rises.
- **[inv:sw-settled-latch]** For every star `i`, if `before.settled_year[i] >= 0` then
  `after.settled_year[i] >= 0`. Once settled, never unsettled. The stronger companion to
  the count-monotone invariant.
- **[inv:sw-front-monotone]** `after.front_radius >= before.front_radius`. Follows from
  the latch (a settled star at distance `r` stays settled and stays at `r`), but the
  incrementally-maintained counter can drift under a bug - assert it directly.
- **[inv:sw-launched-monotone]** `after.total_launched >= before.total_launched`. The
  cumulative launch count only rises.
- **[inv:sw-probe-ids-unique]** No `Probe.id` appears twice in `after.probes.values()`.
  The dict key is unique by construction; this catches a bug where the `.id` field
  drifts from its key.

## Self-stabilization scenarios (issue #49)

`tests/test_self_stabilization.py` answers the Dijkstra question for the
interstellar settlement front. Perturbations mutate `SwarmState` in place
(matching swarm's fold discipline) and are seeded through the caller's RNG.

- **`is_legal_swarm(history, n_stars)`** - the legality predicate: the front
  reached terminal saturation (`settled_count == n_stars`), or `settled_count`
  grew across the recent window and in-flight probes remain.
- **Perturbation classes:**
  - `[pert:sw-star-loss(frac)]` - delete `frac` of in-flight probes.
  - `[pert:sw-settle-loss(frac)]` - flip `frac` of settled stars to unsettled
    (violates `[inv:sw-settled-latch]` if it happened *inside* a step; applied
    between steps this exercises the recovery question directly).
  - `[pert:sw-retarget-cap-shock]` - set every in-flight probe's `retargets`
    counter to `max_retargets - 1`, forcing near-retirement.
- **Analytical claim** - a monotone relation between `settle-loss` fraction and
  convergence time: worse setback -> slower recovery. Asserted on a small sweep.
- **Honest null** - killing every in-flight probe pre-settlement halts progress;
  the suite records that as the terminal state rather than pretending the front
  advances by other means.

## Analytical companion: coordination-tax scaling (issue #50, Phase 2)

`docs/FINDINGS_CLASSIFICATION.md` #6 classifies the coordination tax as
class **B** (rigorous bound). The derivation, formalized here as a numbered
argument, matches the 512-seed sweep in this file's "Fuel tax vs Λ" section.

**Setup.** Consider one hop of length `d` at speed `v`. Let `rho` be the
local settlement rate (density of competing arrivals per unit time near the
target).

**(4a) Instant regime.** The probe sees the true settled set at every
moment. Exposure to a competing settlement claim is the travel time:

    Δt_inst = d / v

**(4b) Lightspeed regime.** At launch, recent settlements within `d/c` of
the target have not yet been observed. Exposure widens by the light-lag:

    Δt_ls  = d/v + d/c

**(4c) Ratio.** Paired ensembles share `rho`, `d`, and the collision
geometry, so:

    E[waste_ls] / E[waste_inst] = (d/v + d/c) / (d/v) = 1 + v/c = 1 + Λ

**Structural consequences.** The `d` factor cancels (hop-length independence)
and `rho` cancels (density independence). The ratio is a clean function of
the dimensionless `Λ` alone.

Measured against predicted at Λ = 0.01 / 0.05 / 0.1 / 0.2:
`1.010 / 1.051 / 1.099 / 1.199` vs `1.010 / 1.050 / 1.100 / 1.200`. Full
agreement at 512 seeds.

A **fast smoke check** at N=200 with 16 seeds is in
`tests/test_coordination_tax_analytical.py` - it guards against a code
change silently breaking the `1 + Λ` relation without pretending to be the
finding itself (which is the paired 512-seed sweep).

## Numba-jitted nearest-unsettled kernel (issue #27 Part 4)

The `_nearest_unsettled_at` k-d tree branch-and-bound moved into a
`@njit(cache=True, fastmath=False, parallel=False, nogil=False)` function in
`swarm/kd_njit.py`. The Python wrapper in `sim.py` unpacks `SwarmState` and
passes flat numpy arrays; the jitted body reproduces the DFS traversal, the
`(distance^2, lowest-index)` tie-break, and the inlined
`_believes_settled_at` gate bit-identically. Environment override
`SWARM_NO_NJIT=1` selects the pure-Python reference (still bit-identical, but
slower - kept in-tree as the readable ground truth).

State fields converted to numpy arrays so the jit function reads them
directly without per-call conversion: `xs, ys, zs, star_speed_pc_yr,
settled_year, kd_axis, kd_split, kd_lo, kd_hi, kd_parent, kd_bucket_flat,
kd_bucket_offsets, kd_bxmin..bzmax, kd_nuns, kd_tsmax, star_leaf`. The
former list-of-lists `kd_bucket` is now `kd_bucket_flat` (concatenated star
ids) + `kd_bucket_offsets` (start index per leaf).

Bit-identical to the pre-refactor list-based fold on every drift-guard
committed artifact (`test_measure_results.py`) and the whole test suite. The
`_nearest_unsettled_at` cumulative time drops ~8x on a small N=2000 event
run (0.30 s -> 0.036 s); overall wall clock for a fresh run drops ~40-60%
because Python overhead outside the kernel remains.

## Per-arrival hot-loop speed-up (post-#27)

Follow-up to #27 Part 4. After the njit kernel landed, `_nearest_unsettled_at`
dropped from ~60% self-time to a wrapper cost; the leading cost shifted to
`_process_arrivals` (~15% self-time in the profile). Three small changes shave
another ~2x off the residual:

- **Tuple storage for the fixed star field.** `xs, ys, zs,
  star_speed_pc_yr` become tuples of Python floats. Numpy mirrors
  (`xs_np, ys_np, zs_np`) exist alongside for the njit kernel. Per-element
  scalar access is ~40% faster than numpy in the tight loop and, unlike
  numpy scalars, does not implicitly return `np.float64` (avoids downstream
  numpy overhead).
- **Inlined `_wall_bin` and `_hop_bin` inside `_process_arrivals`.** Two
  function calls per arrival * 40k arrivals per N=5000 run were the leading
  per-loop cost. The inlined version also caches `1/d_nn`
  (~`density^(1/3)` constant) rather than recomputing per call.
- **`@dataclass(slots=True)` on `SwarmState`** and a pre-built `_njit_args`
  tuple. Attribute lookups compress from ~20 per query to one lookup + one
  tuple unpack.

Full monorepo tests remain green (drift-guard bit-identical). Wall-clock
speedups vs. pre-#27 baseline, event mode, warm JIT:

| N     | pre-#27 (list) | this state | overall |
|-------|----------------|------------|---------|
| 1000  | 0.088 s        | 0.043 s    | 2.0x    |
| 2000  | 0.163 s        | 0.081 s    | 2.0x    |
| 5000  | 0.542 s        | 0.259 s    | 2.1x    |
