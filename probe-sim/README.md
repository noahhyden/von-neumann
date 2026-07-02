# probe-sim — a single self-replicating probe

The step up from `closure-sim`'s factory: one **solar-electric, self-replicating
probe**, after Borgue & Hein (2020). A < 100 kg spacecraft of six modules that can
build ~70% of its own mass and imports the rest (electronics) as "vitamins" — the
electronics wall again, now flying.

What makes a *probe* different from a factory sitting in one place is **where it is**:
being solar-powered, how far from the Sun it can operate is set by how much power
sunlight delivers there, and sunlight falls off as the inverse square of distance.
This module starts from exactly that gate.

## What it models today

- **`environment.py`** — the solar environment. `solar_irradiance_w_m2(distance_au)`
  (inverse-square from the measured 1 AU solar constant) and a `SolarArray`
  (area + efficiency) that turns it into delivered electrical power, plus
  `max_distance_au(required_power)` — the range a given array can sustain a demand to.
- **`range.py`** — the **operational range**. Feeds the array's delivered power into
  `closure-sim`'s replication model (via its public API, not a copy) and bisects on
  heliocentric distance to find where the probe stops reaching its target output —
  i.e. how far out replication stays viable before the falling power budget stalls
  it. `is_viable_at()` answers the question at one distance; `operational_range()`
  finds the crossover (and flags underpowered / saturated edges).
- **`models.py`** — the probe's sourced facts: the six modules and the 70% replicated
  mass fraction. (Per-module masses are an open `[GAP]` — see REFERENCES.md — and are
  not invented.)

## What's next (see [`../ROADMAP.md`](../ROADMAP.md))

Instantiate the real Borgue & Hein probe factory once the per-module mass `[GAP]` is
resolved (currently the range machinery is exercised on a synthetic fixture). Then a
`frontend` surface: drag the array size / efficiency and watch the operational range
move across the solar system.

## Architecture

A pure, deterministic fold in plain data with **zero pimas imports** (CLAUDE.md §7):
framework-agnostic, serializable, independently testable. Any interactive view lives
in `frontend/` and reads this model; it never lives here.

## Develop

```sh
uv run --extra dev pytest -q     # real-number assertions (inverse-square, Jupiter ~50 W/m², roundtrips)
```

Every number traces to a source — see [`REFERENCES.md`](REFERENCES.md). Figures come
from Borgue & Hein (2020, arXiv:2005.12303), Kopp & Lean (2011) for the solar
constant, and the NASA Planetary Fact Sheet for distances.
