# propellant - the fuel you can (or cannot) make in place

A probe can smelt its own girders and still be helpless: if it has to wait for a tanker
of propellant from Earth, it is not self-replicating in any meaningful sense. This module
adds the closure axis the structural models miss - **propellant closure** - and lays bare
the trade at its centre.

## What it models

`propellant.py`, pure functions reusing physics already in the repo:

- **Reaction-mass demand** - `reaction_mass_kg(delta_v, isp, dry_mass)`, the Tsiolkovsky
  rocket equation (reused from `launch-economics`) fed by `transfer`'s Delta-v.
- **Production energy** - `water_electrolysis_hhv_min_kwh_per_kg()` returns the
  thermodynamic floor to make propellant from water: HHV(H2) = 39.4 kWh/kg times water's
  11.2% hydrogen = **4.41 kWh/kg**. The practical full chain (mining, purification,
  electrolysis, liquefaction) is ~11 kWh/kg (Kornuta et al.).
- **Propellant closure and the import wall** - `propellant_closure(route, body_has_water)`
  is 1.0 for water/O2 routes on a water-bearing body (H and O are local) but **0.0 for
  noble-gas EP**: xenon cannot be mined off-world, and Earth makes only **~40-60 tonnes a
  year** - a 10-tonne load is already >10% of world supply (NASA).
- **The trade** - `compare_routes(...)` puts it side by side: high-Isp xenon EP minimises
  propellant *mass* but leaves 100% of it imported; a water route carries more mass but
  imports none. `imported = (1 - closure) x mass`.

All numbers sourced in [`REFERENCES.md`](REFERENCES.md). Pure, deterministic, no pimas,
no RNG (CLAUDE.md 7).

## What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No thruster, plume, or electrochemistry simulation; no tankage/boil-off model. Reaction
mass is Tsiolkovsky, production energy is a sourced specific energy, closure is a routing
rule. The seam with `isru` is deliberate: isru turns regolith into parts, propellant
turns water-ice into reaction mass - shared water-energy literature, separate modules.

## What it found

- **High-Isp electric propulsion is a Faustian bargain.** Xenon EP slashes the propellant
  mass a hop needs, but every kilogram is a permanent tether to Earth - and the global
  xenon supply physically caps how large such a fleet can grow.
- **Propellant closure is a separate axis from structural closure.** To be truly self-
  sufficient a probe must fly a water-derived chemical or water-electric route on a
  water-bearing body; the moment it chooses noble-gas EP, propellant closure is zero no
  matter how well its structure closes.

## Interfaces

- **<- `transfer`:** consumes the Delta-v it derives.
- **reuses `launch-economics`:** the rocket equation and g0.
- **shares Kornuta's water-ice energy with `isru`** (same figure, distinct seam).
- **-> `closure-sim` / `mission`:** imported-propellant mass is a new Earth-import term;
  the xenon wall caps electric-propulsion fleet size.

## Run the tests

```
uv run --extra dev pytest -q
```

11 tests: the 4.41 kWh/kg HHV floor, the reaction-mass round-trips against
launch-economics and transfer, the closure axis (water vs dry body vs noble gas), the
NASA xenon anchor (10 t > 10% of supply), and the mass-versus-tether trade.
