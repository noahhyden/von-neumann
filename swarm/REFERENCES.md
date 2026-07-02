# Where the numbers come from

Slice 1 of the swarm has few physical inputs (the settlement dynamics are mostly
geometry + a policy). Each number is sourced or flagged (CLAUDE.md §1).

## Physics (derived / defined)

- **`C_PC_PER_YEAR ≈ 0.30660` pc/yr** — the speed of light in parsecs per Julian year,
  *derived* from defined constants: `c = 299792.458 km/s` (exact, SI), `1 pc =
  3.0856775814913673e13 km` (IAU 2015 definition), `1 Julian yr = 3.15576e7 s`. Shown in
  code as `299792.458 * 3.15576e7 / 3.0856775814913673e13`.

## Scenario inputs

- **Probe cruise speed = 0.1c** — the fiducial value used by **Nicholson & Forgan
  (2013)**, *Slingshot Dynamics for Self-Replicating Probes*,
  [arXiv:1307.1648](https://arxiv.org/abs/1307.1648) (*Int. J. Astrobiology*). Sourced
  input, not a constant; their slingshot boosts (which can raise effective speed) are a
  later slice. 0.1c → ~0.0307 pc/yr, so a ~2 pc hop takes ~63 years.
- **Local stellar number density = 0.14 stars/pc³** — `[ESTIMATE]`. The solar
  neighborhood census (RECONS; the ~400 star systems within 10 pc → volume
  `(4/3)π·10³ ≈ 4189 pc³` → ~0.1 systems/pc³, ~0.13–0.14 stars/pc³ counting multiples).
  Sets the box size `(N/ρ)^(1/3)` and hence the mean interstellar hop (~1.9 pc at this
  density). Order-of-magnitude; the real disk has a strong radial/vertical gradient.
- **Offspring per settlement = 2** — a scenario **choice** (the replication branching
  factor). 0 → only the homeworld; 1 → a single roving probe (slow linear chain); ≥2 →
  the field fills exponentially fast until stars run out.
- **Settle/dwell time = 0 years default** — `[ESTIMATE]`; the time a probe spends
  building its offspring before they depart. Zero keeps slice 1 about travel; a nonzero
  value (thousands of years, comparable to a hop) is a documented knob.
- **Timestep = 25 years default** — a **numerical** choice, not physics: it must stay
  ≲ the mean hop time (~63 yr at the defaults) or the fixed-step discretization inflates
  the exploration timescale (a coarse `dt` quantizes every hop to a full step). At
  `dt=25` the timescale is within ~10% of the `dt→0` limit; the front then advances at
  ~40% of the probe speed (nearest-hop zig-zag + settling make the front slower than a
  lone probe — consistent with Nicholson & Forgan's finding that exploration is slower
  than a naive light-crossing estimate).

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
