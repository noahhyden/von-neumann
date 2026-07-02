# launch-economics — the economics of not launching mass

Every kilogram you launch across the solar system is expensive, and getting more so
with distance: the rocket equation makes propellant (and therefore cost) grow
*exponentially* with the Δv to your destination. That exponential is the entire
economic reason to build things in place instead of shipping them — and this module
quantifies the payoff.

## What it models today

- **`launch.py`** — the physics and the bill. `launch_cost_usd(mass, $/kg)`, the
  Tsiolkovsky `rocket_equation_mass_ratio(Δv, v_e)` and `propellant_fraction(...)`
  (why a ~9.4 km/s LEO budget is ~93% propellant), and `exhaust_velocity_m_s(Isp)`.
- **`economics.py`** — `ReplicationLaunchComparison`: launch the whole finished mass
  vs. land a self-replicating seed and import only the vitamins. Reports the
  **launch-mass leverage** (installed kg per launched kg), the cost ratio, and the
  dollar savings.

Launch prices, Δv budgets, and Isp are scenario *inputs* (they vary by vehicle and
year); representative sourced values are in [`REFERENCES.md`](REFERENCES.md). Only
defined physical constants (standard gravity) are hardcoded.

## What's next (see [`../ROADMAP.md`](../ROADMAP.md))

Couple the vitamin mass to `closure-sim`: closure sets how much must be imported, so
leverage becomes a function of closure — closing the loop between "how self-
sufficient is the factory" and "how much does the mission cost". Then a `frontend`
surface to trade closure against launch cost interactively.

## Architecture

A pure, deterministic, one-shot calculation in plain data with **zero pimas imports**
(CLAUDE.md §7). Any interactive view lives in `frontend/` and reads this model.

## Develop

```sh
uv run --extra dev pytest -q
```

Figures trace to sources — see [`REFERENCES.md`](REFERENCES.md) (SpaceX published
capabilities, standard Δv tables, Sutton & Biblarz for Isp, the SI standard gravity).
