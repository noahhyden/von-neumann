# swarm — how fast does a self-replicating probe fill the galaxy?

This is the **paradigm step beyond the deterministic fleet** (ROADMAP §4): probes
spread *star to star* through a field, each settling a star and launching copies, and
we watch the reachable field fill from a single homeworld outward. It's the
exploration-timescale question of **Nicholson & Forgan (2013)** — how long a
self-replicating probe takes to reach everywhere.

This is **slice 1**: the pure, seeded, fixed-step *algorithm core*, validated in
Python. It is deliberately small — the big performance engine and the novel physics
come in later slices (below).

## What it models now

- A **seeded star field**: N stars placed uniformly in a cube at the paper's density of
  1 star/pc³ (so the mean hop is ~1 pc).
- A **homeworld** at the field's centre launches probes.
- Each probe travels to a target star, settles it on arrival, and launches `offspring`
  new probes. Three **policies** (the paper's three scenarios), set by `policy`:
  - `powered` (default) — constant cruise (3×10⁻⁵c ≈ 9 km/s), nearest unsettled star.
  - `slingshot_nearest` — gain a **gravitational-assist boost** at each star (extracting
    energy from stellar motion, N&F Eq. 3–4), still targeting the nearest star.
  - `slingshot_maxboost` — target the star giving the **biggest boost**, not the nearest.
- The reachable field fills outward. We report the **exploration timescale** (years to
  settle 50 / 90 / 100%), the **settlement-front radius**, and the **peak probe speed**.
  Powered fills a 500-star box in ~1.5 Myr (Myr order, as in the paper's 5–10 Myr for
  200k); slingshots fill it **far faster** and probes reach ~10³ km/s — and, as the paper
  found, **nearest-slingshot beats max-boost** on time (chasing boosts wastes travel).

The headline result matches the paper's spirit: the settlement *front* advances at only
~40% of an individual probe's speed — nearest-hop zig-zag and settling make the wave
slower than any single probe.

## Determinism (ROADMAP §Design notes, CLAUDE.md §7)

Fixed timestep + a seeded mulberry32 generator threaded through the state (byte-identical
to `multi_probe` and `frontend/scripts/gen-diff.mjs`). Fix the seed → the star field,
every arrival, and every target choice are bit-exact → `speculate` and replay are exact,
and the future TypeScript SoA port can match. The star field is held struct-of-arrays
style (parallel coordinate lists) — the shape the scale slice will make typed arrays.

## Run it

```sh
uv run --extra dev pytest -q      # 13 behavior tests

uv run --extra dev python -c "
from swarm import SwarmParams, simulate_swarm
r = simulate_swarm(SwarmParams(n_stars=500))
print(f'settled {r.final_settled}/{r.n_stars}; 50/90/100% at {r.t50_years}/{r.t90_years}/{r.t100_years} yr; front {r.front_radius_pc:.1f} pc')
"
```

Knobs (`SwarmParams`): `n_stars`, `density_stars_per_pc3`, `probe_speed_c`,
`offspring_per_settlement`, `settle_time_years`, `dt_years` (keep ≲ mean hop time), and
`policy` (`powered` | `slingshot_nearest` | `slingshot_maxboost`).

## Done since slice 1

- **Slingshot dynamics** — the three policies above (this section's boost physics).
- **Spatial hashing** — the frontend TS port uses a uniform-grid index (proven identical
  to brute force) so the live "Swarm" surface scales to thousands of stars smoothly.

## What's still deferred

1. **Full 200k-star scale + WebGL rendering** — the frontend uses canvas today (fine to
   ~10⁴); the WebGL instanced draw for 10⁵⁺ (Canvas→WebGL→WebGPU ladder) is future work.
   pimas stays the control/metrics skin, never the hot loop (§7).
2. **Light-speed-limited coordination** — *the novel extension* (FRONTIER issue #1): the
   source paper grants every probe perfect instantaneous global knowledge; finite-c is
   explicitly its future work. Probes deciding from stale, propagation-delayed local views
   (and reconciling) is new work — a natural fit for `speculate` (a choice against a
   probe's *believed* world) and `explain` (why a decision was made on lagged info).

## Shape (CLAUDE.md §7)

`step(state, params)` and `simulate_swarm(params, seed=…) -> SwarmResult` are the pure,
seeded, fixed-step fold. State is plain data with the RNG carried inside it — framework-
agnostic, serializable, independently testable (Layer A). Sources and flagged choices
are in [`REFERENCES.md`](REFERENCES.md).
