# multi-probe — a small, deterministic fleet that copies and spreads

This is the **intermediate step between the single probe and the swarm** (ROADMAP §3).
A handful of probes — *tens, not 100,000* — each an **agent** that builds copies of
itself at a rate its local sunlight allows and sends children outward. It exists to
validate the "probe-as-agent" abstraction and to keep `speculate` exact **before** the
paradigm jump to a stochastic, 10⁵-star spatial simulation.

It writes **no new physics**: solar power vs distance comes from `probe-sim`, and the
build rate, closure, and seed mass come from `closure-sim`. `multi-probe` is only the
fleet dynamics on top — and it is a **pure, seeded, deterministic fold** (CLAUDE.md §7),
so a fixed seed replays bit-for-bit and a what-if forks the future exactly.

## What one probe does each day

1. **Build.** An active probe adds local structure at `min(machinery rate, energy cap)`
   kg/day — exactly `closure-sim`'s regime logic for a *fixed-size* probe. Near the Sun
   the machinery binds (~20 kg/day); far out, 1/d² sunlight drops the energy cap below
   that and *power* binds.
2. **Copy.** When it has built one copy's worth of local structure (`closure × seed`)
   **and** the fleet still has imported **vitamins** (the non-replicable electronics),
   it spawns a child, consuming `(1 − closure) × seed` from the vitamin pool.
3. **Disperse.** The child travels outward (a settling distance × its parent's, capped),
   arrives after a transit time, and then becomes active itself.

## Two walls emerge — neither hard-coded

- **The electronics wall, at fleet scale.** The vitamin pool is finite, so at most
  `floor(pool / (1−C)·seed)` copies can ever exist. This is `closure-sim`'s lesson made
  spatial, and it ties straight to `launch-economics`/`mission`: the vitamins you launch
  bound the fleet you can grow.
- **A spatial power wall.** Children spread outward, sunlight falls as 1/d², so
  far-flung probes build too slowly to copy within the mission — the fleet stops
  expanding not because of parts, but because of *distance from the Sun* (~13.6 AU
  crossover for the default scenario).

## Determinism is the whole point (ROADMAP §Design notes)

Randomness (optional transit-time jitter) is a **seeded generator threaded through the
state** — never `Math.random()`, never a wall clock. Fix the seed → bit-exact replay →
exact `speculate` and free per-seed Monte-Carlo. With jitter = 0 the run is fully
deterministic and independent of the seed (a property the tests assert). The PRNG is
mulberry32, byte-identical to `frontend/scripts/gen-diff.mjs`, so a future TypeScript
port produces the same sequences.

## Run it

```sh
uv run --extra dev pytest -q     # 11 end-to-end behavior tests

uv run --extra dev python -c "
from closure_sim.scenarios import load_factory; import closure_sim, pathlib
from multi_probe import params_from_factory, simulate_fleet
root = pathlib.Path(closure_sim.__file__).resolve().parents[2]
f = load_factory(root/'scenarios'/'lunar_regolith_seed.yaml')
r = simulate_fleet(params_from_factory(f), duration_days=14600)
print('fleet:', r.final_population, 'probes, doubling', r.doubling_time_days, 'd, binding', r.binding.model_dump())
"
```

Override any knob via `params_from_factory(factory, start_distance_au=30.0, ...)`:
`start_distance_au` (spatial power wall), `vitamin_pool_kg` (electronics wall),
`max_probes` (fleet cap), `dispersal_factor`, `transit_days`, `transit_jitter_frac`.

## Shape (CLAUDE.md §7)

`step(state, params, dt) -> state` is pure; `simulate_fleet(params, seed=…) -> FleetResult`
folds it over time. State is plain data with the RNG carried inside it — framework-agnostic,
serializable, independently testable (Layer A). Sources and flagged choices are in
[`REFERENCES.md`](REFERENCES.md). A `frontend` surface (a live, dispersing fleet) is the
next step.
