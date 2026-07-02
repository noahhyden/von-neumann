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

## Slice-1 simplifications (documented, deferred to later slices)

- **Uniform cube star field**, not a galactic disk with a density gradient.
- **Straight-line, constant-speed travel** — no gravitational slingshots, no stellar
  motion (the core of Nicholson & Forgan's paper; a later slice).
- **Nearest-unsettled policy only** — not their nearest-powered / nearest-slingshot /
  max-boost policies.
- **Settle-on-arrival**, not replicate-in-transit from the ISM.
- **Modest N (hundreds–few thousand)** with an O(N) nearest search — the 200k-star SoA +
  spatial-hash performance engine, WebGL rendering, and the novel **light-speed-limited
  coordination** extension are the later slices (ROADMAP §4).
