# Where the numbers come from

`multi-probe` introduces **no new physical constants** — the physics it uses (solar
power vs distance, local build rate/energy, closure) is sourced in the sibling
modules it composes. What lives here are (a) pointers to those sources and (b) the
fleet-dynamics **scenario choices**, each flagged as a choice or `[ESTIMATE]`, never
an unmarked guess (CLAUDE.md §1).

## Numbers inherited from sibling modules (sourced there)

| Quantity | Value / basis | Source |
|----------|---------------|--------|
| Seed (one probe copy) mass | 12,000 kg | closure-sim `lunar_regolith_seed.yaml` (`replication.seed_mass_kg`) |
| Closure ratio | ~0.9708 (derived) | closure-sim `compute_closure` |
| Local build energy `e_local` | ~18.1 kWh/kg (local build energy ÷ local mass) | derived from closure-sim `ClosureReport` |
| Machinery throughput `local_build_rate` | 20 kg/day | closure-sim scenario (`replication.local_build_rate_kg_per_day`) |
| Solar power vs distance | S₀/d² · A · η, S₀ = 1360.8 W/m² | probe-sim/environment.py (Kopp & Lean 2011) |

The build rate is exactly closure-sim's `min(alpha·F, energy_cap)` for a **fixed-size**
probe (a probe makes copies; it does not grow itself, so `alpha·F` ≈ its constant
`local_build_rate`). Near the Sun the machinery binds; beyond ~13.6 AU the 1/d² energy
cap binds — the spatial power wall is emergent, not hard-coded.

## Scenario choices this module makes (flagged, not facts)

- **Array ≈ 9,798 m² at 30% efficiency** — same basis as the `mission` module: efficiency
  is `[ESTIMATE]` (probe-sim/REFERENCES.md); area is *derived* to deliver ~4 MW at 1 AU
  (`4e6 / (1360.8 · 0.30)`), matching the closure scenario's power.
- **Manufacturing fraction = 0.70** — design **choice** (share of power to building vs
  compute/housekeeping), consistent with the `mission` split.
- **Dispersal factor = 1.3×, max distance = 40 AU** — design **choices** modeling how
  far a child settles from its parent (outward, into less-contested territory) and the
  outer bound of a useful solar-electric probe (~Jupiter and beyond becomes marginal,
  probe-sim). Not physical laws; the parameters the swarm step will generalize.
- **Transit time = 365 days base** — `[ESTIMATE]`: an order-of-magnitude interplanetary
  cruise time (inner/mid solar system transfers are months to a few years; e.g. Earth→Mars
  Hohmann ≈ 259 days, Earth→Jupiter ≈ 2–6 years). A single representative figure for the
  small model; the swarm will replace it with per-leg travel physics.
- **Transit jitter = 0 by default** — the seeded ± noise fraction on transit time. Zero
  keeps the baseline fully deterministic and seed-independent; > 0 exercises the threaded
  RNG (real-world navigation/thrust variability as noise, CLAUDE.md §3) while staying
  bit-exactly reproducible per seed (§7).
- **Vitamin pool = 1,000,000 kg default** — a scenario **choice** standing for the total
  imported non-replicable mass (electronics) available to outfit new copies. A finite pool
  is the electronics wall at fleet scale: `floor(pool / (1−C)·seed)` children can ever be
  built. Ties directly to launch-economics / mission (the vitamins you launch bound the
  fleet you can grow).
- **Max probes = 64 default** — a **scope bound**, not physics: this is deliberately the
  *small* deterministic model (tens of probes), the intermediate step before the 10⁵-star
  swarm (ROADMAP §3–4).

## Open gap (inherited)

- **`[GAP]` — probe-specific bill of materials.** As in `mission` and `probe-sim`, there is
  no sourced per-module mass breakdown for the Borgue & Hein probe, so the factory here is
  closure-sim's lunar-regolith seed scenario used as a stand-in — a real BOM, not
  probe-specific. No masses are invented.
