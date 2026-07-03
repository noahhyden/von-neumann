# Where the numbers come from

Slice 1 of the swarm has few physical inputs (the settlement dynamics are mostly
geometry + a policy). Each number is sourced or flagged (CLAUDE.md §1).

## Physics (derived / defined)

- **`C_PC_PER_YEAR ≈ 0.30660` pc/yr** — the speed of light in parsecs per Julian year,
  *derived* from defined constants: `c = 299792.458 km/s` (exact, SI), `1 pc =
  3.0856775814913673e13 km` (IAU 2015 definition), `1 Julian yr = 3.15576e7 s`. Shown in
  code as `299792.458 * 3.15576e7 / 3.0856775814913673e13`.

All scenario numbers below trace to **Nicholson & Forgan (2013)**, *Slingshot Dynamics
for Self-Replicating Probes and the Effect on Exploration Timescales*,
[arXiv:1307.1648](https://arxiv.org/abs/1307.1648) (*Int. J. Astrobiology* 12, 337),
read from the full text ([ar5iv](https://ar5iv.labs.arxiv.org/html/1307.1648)).

> **Correction (why the defaults changed):** an earlier version of this file claimed a
> "0.1c fiducial from Nicholson & Forgan" and a 0.14 stars/pc³ density. Both were wrong
> — 0.1c was **not** their value (it was ~3300× too fast and unsourced), and they use a
> uniform 1 star/pc³, not the solar-neighborhood figure. The defaults below are the
> paper's actual parameters, checked against the source. (CLAUDE.md §1: a mis-attributed
> number is worse than a gap.)

## Scenario inputs

- **Powered cruise speed = 3×10⁻⁵ c (≈ 9 km/s)** — the paper's stated maximum probe
  velocity ("The maximum velocity of the probes was chosen to be 3×10⁻⁵c"). This is the
  *powered-flight* speed; the paper's whole point is that **gravitational slingshots**
  (extracting energy from a star's ~200 km/s orbit about the Galactic centre) let a probe
  explore ~100× faster — slingshots are a later slice, so this module models powered
  flight only. 3×10⁻⁵c → ~9.2×10⁻⁶ pc/yr, so a ~1 pc hop takes ~110,000 years.
- **Stellar density = 1 star/pc³** — the uniform density the paper uses ("uniform density
  of 1 star per cubic parsec"). Denser than the real solar neighborhood (~0.14 stars/pc³,
  RECONS 10-pc census) — a modelling choice the paper makes; we follow it for fidelity.
  Sets the box size `(N/ρ)^(1/3)` and the mean hop (~1 pc here).
- **Offspring per settlement = 2** — a scenario **choice** (the replication branching
  factor). 0 → only the homeworld; 1 → a single roving probe (slow linear chain); ≥2 →
  the field fills exponentially fast until stars run out.
- **Settle/dwell time = 0 years default** — `[ESTIMATE]`; the time a probe spends
  building offspring before they depart. The paper assumes replication happens *in
  transit* (probes collect interstellar material and never stop), so 0 dwell is faithful
  to that; a nonzero value is a documented knob. (Replicate-in-transit vs our
  settle-then-launch is a later-slice refinement — see below.)
- **Timestep = 5000 years default** — a **numerical** choice, not physics: it must stay
  ≲ the mean hop time (~1.1×10⁵ yr at the defaults) or the fixed-step discretization
  inflates the exploration timescale. At `dt=5000` the timescale is within ~1% of the
  `dt→0` limit. Result: filling a 500-star box takes ~1.5 Myr, and the whole reachable
  field fills on a **Myr timescale** — the same order as the paper's 5–10 Myr for 200,000
  stars. The front advances at only ~40% of a single probe's speed (nearest-hop zig-zag +
  settling), consistent with the paper's finding that exploration is slower than naive.

## Slingshot dynamics (the `slingshot_*` policies)

The paper's core mechanism: a probe flying past a star is deflected elastically in the
star's frame, but because the star moves in the galactic frame the probe's galactic-frame
speed changes — extracting energy from the star's motion "for free." Boosted probes
accumulate speed across encounters and far outrun powered flight. All of the following is
from Nicholson & Forgan (2013); the numbers the paper defers are tagged `[ESTIMATE]`.

- **Max boost per encounter** — `Δv_max = u_esc² / ( u_esc²/(2·u_i) + u_i )` (their Eq. 4),
  with `u_i` = the probe's speed relative to the star. This *self-limits*: Δv_max peaks near
  `u_i ≈ u_esc` and falls off for fast probes, so speed does not run away.
- **Stellar escape velocity `u_esc = 617.5 km/s`** — solar, `u_esc = √(2GM☉/R☉)`. Derived:
  `√(2 · 6.674e-11 · 1.989e30 / 6.957e8) = 6.18×10⁵ m/s`. Sourced (the paper "assumes solar
  values for M∗ and R∗"); constants are IAU/CODATA nominal. **Derived, not a free number.**
- **Boost-optimal geometry `[ESTIMATE]`** — the paper gives `Δv = 2|u_i|·sin(δ/2)` (Eq. 3)
  but not how the deflection angle δ is set per flyby. We assume each slingshot achieves
  `Δv_max` (Eq. 4) in the boost-optimal direction, and we track **scalar speeds** (not full
  velocity vectors / true encounter geometry), taking `u_i ≈ probe speed + star speed`. A
  deliberate simplification for an experimental model.
- **Stellar speed `220 km/s ± 40 km/s` `[ESTIMATE]`** — the paper places stars in a shearing
  box to mimic Galactic rotation but **does not print the rotation speed or velocity
  dispersion** (it defers to Forgan, Papadogiannakis & Kitching 2012). We use the standard
  local circular speed (~220 km/s) with a thin-disc-like dispersion (~40 km/s), random per
  star (seeded). Stars are **fixed in position** but carry a speed that drives the boost —
  as the paper does ("stars remain fixed in position even though they have velocity vectors").
- **Max-boost candidate bound = 30 `[ESTIMATE]`** — policy (iii) targets the biggest boost;
  we scan only the 30 nearest unsettled stars so a probe doesn't cross the galaxy for a
  marginal kick. Our fallback when no candidate exists = stop (a modelling choice).
- **Speed cap = 0.05 c `[ESTIMATE]`** — a sanity ceiling on accumulated speed; Eq. 4's
  fall-off usually keeps speeds well below it.
- **Observed speedup is `dt`-limited.** Boosted probes are fast (~10³ km/s), so their hops
  (~10² yr) are shorter than `dt=5000 yr` and get quantized to one step. The measured
  slingshot-vs-powered speedup is therefore ~20× at the default `dt`; the paper's true
  figure is ~100×. Lowering `dt` recovers more of it (at more steps). The **qualitative**
  results are faithful: slingshots ≫ powered, and **nearest-slingshot beats max-boost on
  time** (max-boost reaches higher speed but wastes travel — the paper's finding).

## Coordination-horizon visualization (the light-speed rungs)

A frontend-only teaching overlay (FRONTIER issue #1, near-term slice) that turns an
inter-star distance into a *coordination mode* via the light-travel time. No new sim
physics — it reuses `C_PC_PER_YEAR` above; the only inputs are the rung thresholds and
the real-world analog distances below.

- **Round-trip latency = `2 · d / c`**, one-way = `d / c`. Both derived from
  `C_PC_PER_YEAR` (above): a distance `d` in pc has one-way light-time `d / 0.30660` yr.
  *Check:* 1 AU = `1.495978707e8 / 3.0856775814913673e13 = 4.8481e-6 pc` → one-way
  `4.8481e-6 / 0.30660 = 1.5813e-5 yr = 499.0 s = 8.32 min`, the textbook 1-AU light time. ✓
- **The ρ ratio** — `ρ = round-trip latency / decision timescale`. Coordination fidelity
  degrades as ρ grows (Olfati-Saber & Murray 2004, *IEEE TAC* 49(9),
  [DOI 10.1109/TAC.2004.834113](https://doi.org/10.1109/TAC.2004.834113): the standard
  consensus protocol is stable iff the one-hop delay `τ < π/(2λₙ)`, so tighter coupling
  tolerates *less* delay). The **decision timescale is a knob, default 1 yr `[ESTIMATE]`**
  — the literature gives no single value for "a probe's targeting-decision cadence," so ρ
  is presented as a tunable lens over the *sourced* absolute-latency rungs below, not as a
  hard number itself.

- **Rung thresholds (by round-trip latency) `[ESTIMATE]`** — the *transitions* are sourced
  from the teleoperation/networking literature; the round-number bucket edges (1 s, 1 min,
  1 hr, 1 yr) are a presentation choice, so the set is tagged `[ESTIMATE]`:
  - **≤ 1 s — real-time closed-loop.** Continuous closed-loop teleoperation breaks down and
    operators switch to "move-and-wait" once delay approaches ~1 s (Ferrell 1965, *Remote
    Manipulation with Transmission Delay*, NASA TN D-2665, [NTRS
    19650052768](https://ntrs.nasa.gov/citations/19650052768)).
  - **1 s – 1 min — move-and-wait.** The degraded regime Ferrell (1965) characterized:
    command open-loop, wait a full round trip, correct.
  - **1 min – 1 hr — supervisory.** Send goals, let the node execute; the operator
    supervises rather than pilots (Ferrell & Sheridan 1967, *Supervisory Control of Remote
    Manipulation*, IEEE Spectrum).
  - **1 hr – 1 yr — delay-tolerant / store-and-forward.** No continuous end-to-end path;
    hop-by-hop custody transfer, no real-time handshake (Cerf, Burleigh et al.,
    *Delay-Tolerant Networking Architecture*, IETF [RFC 4838](https://www.rfc-editor.org/info/rfc4838), 2007).
  - **> 1 yr — fully independent colonies.** No live command exists; each node acts on
    priors set before launch (Freitas 1980, *A Self-Reproducing Interstellar Probe*, *JBIS*
    33:251 — each probe "an independent agent").

- **Real-world analog distances** (each classified by the arithmetic above; used only as
  legend anchors — every value is a citable astronomical constant):
  - **LEO ≈ 550 km** (Starlink operational shell) → `1.7824e-11 pc`, round-trip **3.67 ms**
    → *real-time*. (SpaceX/FCC filings; 550 km is the primary shell.)
  - **Earth–Moon = 384,400 km** (mean distance, IAU) → `1.2458e-8 pc`, round-trip **2.564 s**
    → *move-and-wait*.
  - **Mars ≈ 0.52–2.52 AU** (min/max Earth–Mars range) → round-trip **~8.7–42 min** →
    *supervisory* across the whole range.
  - **Saturn = 9.5 AU** (semi-major axis 9.582 AU, NASA planetary fact sheet, rounded) →
    `4.606e-5 pc`, round-trip **~2.6 hr** → *delay-tolerant*.
  - **Proxima Centauri = 1.301 pc** (4.2465 ly; RECONS/Gaia parallax) → round-trip **8.49 yr**
    → *fully independent colonies* — and this is the regime **every ~1 pc inter-star hop in
    the sim already sits in** (mean hop ~1 pc → round-trip ~6.5 yr). That collapse is the
    lesson, not a rendering bug: at galactic scale the four faster rungs are sub-pixel.

## Light-speed-limited coordination (the `lightspeed` regime, FRONTIER #1)

Nicholson & Forgan grant every probe **perfect, instantaneous global knowledge** of which
stars are settled; finite light-speed is their explicit future work. The `coordination`
param adds it: under `"lightspeed"`, a probe deciding *at* star `frm` in year `Y` treats a
distant star `i` as settled only once the news has arrived —
`settled_year[i] + dist(frm,i)/c ≤ Y`. Under `"instant"` (default) this collapses to
`settled_year[i] ≥ 0`, bit-identical to the perfect-info slices.

- **Signal speed = c** — the news travels at lightspeed (an EM beacon is the physical upper
  bound on information). Reuses the already-derived `C_PC_PER_YEAR` (above); **no new
  constant.** A slower signal is a trivial future knob, not needed for the core question.
- **`Λ ≈ v_probe / c` `[ESTIMATE]`** — the dimensionless ratio (info-lag-per-hop ÷
  travel-time-per-hop = (d/c)/(d/v) = v/c) that governs how much the lag matters. At the
  paper's powered speed (3×10⁻⁵ c) `Λ ≈ 3×10⁻⁵` → the effect is **negligible**; it only bites
  in the fast/slingshot regime (boosted probes ~10³ km/s, or `probe_speed_c` swept toward
  0.1 c — Carroll-Nellenback's range, [arXiv:1902.04450](https://arxiv.org/abs/1902.04450)).
  Derived here from hop geometry; the constant of proportionality depends on the hop-length
  distribution, hence `[ESTIMATE]`.
- **`max_retargets = 8` `[ESTIMATE]`** — a **bookkeeping** cap, not a physical number: a probe
  that loses this many races in a row is retired as wasted, bounding pathological bounce
  chains late in the fill. No literature source; results must be shown insensitive to it (sweep).

**Modelling assumptions (stated as assumptions, not measured facts — §1):**
- **A settled star is an omnidirectional beacon emitting at year `settled_year[i]`.** No relay,
  no directionality.
- **Decision-site knowledge only.** Belief is evaluated at the decision star at decision time,
  so news a probe's worldline passes *through* mid-flight is ignored. This **undercounts**
  knowledge → probes are slightly pessimistic → a **conservative upper bound** on redundant
  effort. Mid-flight learning (two-endpoint cone) and true probe-to-probe **gossip relay** are
  the deferred sibling slice.
- **Pure lag still fills a connected field to 100%** (re-targeting guarantees it), just slower.
  A steady-state settled fraction `X_eq = 1 − T_launch/T_settle < 1` (Carroll-Nellenback's
  "Aurora effect") requires a settlement *death* term — a separate sibling, not lag alone.

**Finding (32-seed paired ensemble, `experiments/lightspeed_coordination.py`):** on the same
seeded galaxies (N=300), light-speed lag slows the fill-100% timescale by a median of **~0%
(powered), ~30% (slingshot-nearest, IQR +20…+38%), ~50% (slingshot-maxboost, IQR +46…+54%)** —
every case still reaches 100%. So the penalty is **not** simply `Λ = v/c`: powered
nearest-neighbour flight is nearly immune even when fast, because a probe that loses a race
just takes the star next door (cheap local recovery). The cost appears only with **long-range
hops made from stale views** (the slingshot regime), where a wasted trip is a long detour.
`Λ ≈ v/c` sets the *scale* of the lag; **hop non-locality decides whether it bites.** This
refines Nicholson & Forgan's perfect-info picture: their slingshot speed-up is real, but under
finite light-speed a meaningful fraction of it is eaten by uncoordinated long-range collisions.

## Simplifications still deferred to later slices

- **Uniform cube star field**, not a galactic disk with a density gradient.
- **Replicate at the settled star**, not truly replicate-in-transit from the ISM (the
  effect is similar — one child per arrival, inheriting the parent's boosted speed).
- **Scalar speeds, not velocity vectors** (see the boost-geometry `[ESTIMATE]` above).
- **200k-star scale + WebGL rendering** — the frontend uses a spatial hash and canvas; the
  full 10⁵-star SoA/WebGL engine and the novel **light-speed-limited coordination**
  extension are the remaining slices (ROADMAP §4; light-speed is FRONTIER issue #1).
