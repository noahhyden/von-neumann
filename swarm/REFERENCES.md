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

## Simplifications still deferred to later slices

- **Uniform cube star field**, not a galactic disk with a density gradient.
- **Replicate at the settled star**, not truly replicate-in-transit from the ISM (the
  effect is similar — one child per arrival, inheriting the parent's boosted speed).
- **Scalar speeds, not velocity vectors** (see the boost-geometry `[ESTIMATE]` above).
- **200k-star scale + WebGL rendering** — the frontend uses a spatial hash and canvas; the
  full 10⁵-star SoA/WebGL engine and the novel **light-speed-limited coordination**
  extension are the remaining slices (ROADMAP §4; light-speed is FRONTIER issue #1).
