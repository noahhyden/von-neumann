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
  `u_i ≈ u_esc` and falls off for fast probes, so speed does not run away.
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
  (`Λ ≈ 0.01`) up to directed-energy speeds (`0.1-0.2 c`, Carroll-Nellenback / Lubin). **`Λ` is
  the governing parameter of the FUEL tax:** at the resolved (event) timestep the fill-TIME tax
  is small at every speed, but the redundant-travel (wasted-journey) tax rises cleanly and
  monotonically with `Λ` - median +0.6% at `Λ=0.01`, +2.9/+4.2/+9.3% at 0.03/0.05/0.1, +19.5%
  at 0.2 (powered, N=500, 48 seeds). It is the right group for the right cost.
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
  hop - so proper motion would reshuffle the beacon geometry the gate reads. It is **bounded for
  our relative result**: both coordination modes run on the *identical* frozen field, so the paired
  difference still isolates the light-lag effect; it remains a genuine limitation on *absolute*
  fill times. (Displacements derived from the two `[ESTIMATE]` speeds; sources ground those speeds.)
- **Pure lag still fills a connected field to 100%** (re-targeting guarantees it). A
  steady-state settled fraction `X_eq = 1 − T_launch/T_settle < 1` (Carroll-Nellenback's
  "Aurora effect") requires a settlement *death* term - a separate sibling, not lag alone.
- **Probes built are ~mode-independent.** Both modes fill the field and each settlement launches
  `offspring` probes, so `total_probes_launched` differs by only a handful of terminal launches
  (well under 1%, no systematic sign at low `Λ`, ~+0.5% at `Λ=0.2`). The coordination cost is
  therefore redundant TRAVEL (wasted journeys), not extra manufacturing.

**Energy-weighted tax (basis; §1, §8).** Wasted journeys are also weighted by the kinetic energy
their launch speed cost, not counted flat. Primary weight: Newtonian specific energy
`E/m = (1/2)v²`, as a fraction of `c²` via `Λ = v/c`: `(1/2)Λ² =` 5.0e-5, 1.25e-3, 5.0e-3, 2.0e-2
at `Λ =` 0.01, 0.05, 0.1, 0.2. The only physical input is `c` (SI-exact); the rest is arithmetic.
Cross-check: the relativistic form `E/m = (γ−1)c²`, `γ = 1/√(1−Λ²)`, exceeds Newtonian by only
0.0075 / 0.19 / 0.76 / 3.10% at those `Λ`, so Newtonian is a safe primary metric (it mildly
under-estimates at 0.2c). Each wasted trip is scaled by a **rendezvous multiplier in [1, 2]**: a
flyby imparts one-way acceleration energy (1×), while landing requires braking to rest then
re-accelerating - ~2× by the quadratic v-dependence; beamed light sails have no braking beam at
arrival, so deceleration is a real, distinct cost ([lubin-2016]). We report the tax as a 1×-2×
band. Accumulators `settle_energy_c2` / `wasted_energy_c2` are read-only sums of `(1/2)(v/c)²` over
winning / wasted journeys (no RNG; the pinned baseline is unchanged).

**Finding (paired ensemble, event timestep).** Several parts, all deterministic.

*No fill-time tax; the coarse-dt one is an artifact* (`experiments/dt_artifact.py`). With the
slice-1 fixed `dt=5000 yr` the fill-100% penalty for slingshot-nearest looks like a robust
median **+30.3%** (32/32 seeds). It is an artifact of the step: a fixed dt >> hop time batches
many launches into one window so they decide from the same stale snapshot and collide. Refining
the step, the penalty falls monotonically - **30.3 → 27.6 → 25.0 → 12.8 → 5.3%** at dt =
5000/2000/1000/500/250 - and at the event (dt→0) limit it is **+0.0%**, no longer distinguishable
from zero. The same refinement restores the slingshot-vs-powered speedup to N&F's full ~two
orders of magnitude (**~166x**), where the coarse step gave only ~20x. **Light-speed lag does not
slow the fill.**

*The real cost is redundant travel, governed by `Λ = v/c`* (`experiments/measure.py::lambda_sweep`).
Probes-built is ~mode-independent (above), so the coordination cost is wasted journeys. For powered
flight swept across the speed axis (N=500, 48 seeds, lightspeed vs instant), the fuel tax (extra
wasted journeys as % of the perfect-info waste), median [bootstrap 95% CI], (seeds positive):
  - `Λ=0.01`: **+0.6% [0.5, 0.8]** (40/47)
  - `Λ=0.03`: **+2.9% [1.8, 4.1]** (42/48)
  - `Λ=0.05`: **+4.2% [3.4, 5.8]** (42/48)
  - `Λ=0.10`: **+9.3% [7.4, 11.4]** (46/48)
  - `Λ=0.20`: **+19.5% [17.8, 23.3]** (48/48)

  The fill-time tax is a small companion (0.0/0.1/0.3/2.6/6.6% across the same Λ), real but minor. We
  do NOT lean on a sign-test p-value: by construction a stale view can only ADD wasted journeys
  (never remove them), so the sign is built in - the magnitude and its scaling are the informative
  part (CIs and sweeps, not significance theatre). Honest correction of a round-1 overclaim.

*Energy-weighted tax* (`experiments/measure.py::energy_tax`, N=400, 32 seeds). Counting journeys
understates the cost where speeds vary. Weighting each wasted trip by `(1/2)(v/c)²`: powered (uniform
speed) count = energy = +0.0%; slingshot-nearest count **+0.8%** but energy **+4.2% (flyby) to +8.4%
(rendezvous)** (its wasted trips fly at ~2700 km/s); slingshot-maxboost count **~+0.0%** yet energy
**+11.3% to +22.6%** - the count sees almost no extra wasted arrivals, but they are its fastest and
farthest, so the energy tax is large. The weighting reveals a cost the journey count hides.

*Contention scales with branching* (`experiments/measure.py::branching`, N=400, 32 seeds). The tax
grows with the offspring branching factor at high `Λ` then saturates: at `Λ=0.2`, +18.4 / +24.9 /
+25.5% for offspring = 2/3/4; at `Λ=0.05` it is ~flat (~+6%). The default of 2 is not a floor hiding
a much larger tax; the whole effect stays within an order of magnitude.

*Why no fill-time tax: concurrency* (`experiments/measure.py::concurrency`, N=500, 16 seeds). A
median ~480 probes are in flight at the peak of a fill and ~440 at 90% coverage, and the light-lag
swarm carries essentially the same in-flight population as perfect info (peaks ~470 vs ~480). So a
loser's wasted trip is one of hundreds and never on the critical path to the last star - the
mechanism behind the null time result.

*Physical floor: relaying in flight* (`experiments/measure.py::floor_bracket`, N=400, 48 seeds,
powered). The decision-site (`lightspeed`) tax is an upper bound. Under `inflight` (a probe listens
while flying and aborts a doomed hop when its beacon overtakes it) completed wasted arrivals fall to
**0** at every `Λ`, and redundant travel drops BELOW even the perfect-info baseline (at `Λ=0.2`:
~3580 pc lightspeed, ~2930 pc instant, **~1640 pc inflight**), because listening also averts the
assignment collisions perfect knowledge leaves. Cost: mid-flight detours lengthen the fill by ~2% at
`Λ=0.2`. So in-flight relay recovers essentially all of the wasted-arrival tax; the residual floor is
the partial travel flown before a beacon arrives, which grows with `Λ`.

**Fuel tax is a scale-stable fraction (`experiments/finite_size.py`, powered, `Λ=0.2`, event,
16 seeds).** As a *percent* of the perfect-info waste the fuel tax is flat in N - **+17.9 /
+18.9 / +19.2%** at N = 300 / 600 / 1200 (16/16 seeds each) - while the *absolute* wasted-journey
count grows with the field (median +232 / +508 / +1160). So the cost is a size-independent
fraction of effort, not a small-box artifact. Reach is bounded by the O(N²) event-mode cost at
high `Λ`; this is the trend over the reachable range.

**Density-rescaling invariance (checked):** changing the *uniform* density rescales every
distance by a common factor, so travel time and light-time scale together and `Λ` (hence the
relative penalty) is unchanged - a pure geometric rescaling of the absolute clock, confirmed to
the printed digit across 0.14 → 5 stars/pc³. A *non-uniform* (clumpier) field is a separate,
unaddressed case expected to lengthen long-range hops - a documented limitation.

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
fold. Eight figures regenerate: `fig_fuel_tax_vs_lambda`, `fig_fuel_tax_by_seed`, `fig_time_tax_vs_dt`,
`fig_concurrency` (mechanism), `fig_energy_tax`, `fig_branching`, `fig_floor_bracket`, and
`fig_fuel_tax_vs_n` (scale). Regenerate the numbers via `uv run --extra dev python -m experiments.measure`
and the figures via `uv run --extra dev python -m experiments.paper_figures`.

## Simplifications still deferred to later slices

- **Uniform cube star field**, not a galactic disk with a density gradient.
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
- **Lubin 2016** - P. Lubin (UC Santa Barbara) (2016). A Roadmap to Interstellar Flight (arXiv:1604.01356). Journal of the British Interplanetary Society 69:40-72. https://arxiv.org/abs/1604.01356. The far end of the propulsion spectrum for a self-replicating seed: beamed directed-energy light-sail acceleration of gram-scale craft toward ~0.2c, sidestepping the rocket-equation penalty by leaving the energy source at home. Connects to the swarm's interstellar cruise-speed assumptions.
