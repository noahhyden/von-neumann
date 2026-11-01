# thermal - getting rid of the heat

Every watt a factory's power system delivers ends up as waste heat, and in the vacuum of
space the only way to get rid of it is to radiate it away. The project's own FINDINGS
call self-replication "a power-and-cooling problem, not a physics one" - but until this
module, the repo modelled the power and quietly ignored the cooling. `thermal` sizes the
radiator that rejects the heat and puts its mass on closure-sim's bill of materials, so
heat rejection stops being free.

## What it models

`thermal.py`, one physical law (Stefan-Boltzmann) turned into sizing:

- **`radiated_flux_w_m2(T)`** - `q = sides x eps x sigma x (T^4 - T_sink^4)`, the watts
  per square metre a radiator at temperature T rejects (two-sided by default).
- **`radiator_area_m2(heat, T)`** and **`radiator_mass_kg(area)`** - the area to reject a
  heat load and, at ~3 kg/m^2 (NASA's lightweight target), its mass.
- **`mass_per_kw_kg(T)`** - the **T^4 leverage**: because flux goes as T^4, a ~530 K
  smelting radiator is **~10x lighter per kilowatt** than a ~300 K electronics radiator.
  Heat must be binned by the temperature of the process that makes it, not lumped.
- **`net_flux_with_solar_load_w_m2(T, distance)`** - the **distance story**: a radiator
  also absorbs sunlight, and that parasitic load falls as 1/d^2, so radiators get better
  as you leave the Sun. Too close in, a cold radiator hot-soaks and the function refuses.

All numbers sourced in [`REFERENCES.md`](REFERENCES.md). Pure, deterministic, no pimas,
no RNG (CLAUDE.md 7).

## What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No heat-pipe network, two-phase-loop, or CFD solver - radiators are sized algebraically
from Stefan-Boltzmann. Deep-space sink defaults to ~0 K; a planetary environment enters
as parameters, not a sub-simulation.

## What it found

- **Hot heat is cheap heat.** A radiator's mass per kilowatt falls as 1/T^4, so rejecting
  a smelter's 500+ K waste heat costs ~10x less radiator than the same watts from 300 K
  electronics. A single factory needs several radiators at different temperatures.
- **The physics reproduces flight hardware.** Sizing 35 kW at the ISS's 275 K coolant
  temperature gives 67.5 m^2 - within 4% of a real ISS radiator assembly's 70.3 m^2,
  which rejects exactly that per loop.

## Interfaces

- **-> `closure-sim`:** radiator mass is a new BOM line.
- **<- `power-source` / `power-budget`:** the heat load is the waste power they deliver;
  `power-source` calls `thermal` to size its radiator mass.
- **reuses `probe-sim`:** the 1/d^2 solar law for the parasitic-load term.

## Run the tests

```
uv run --extra dev pytest -q
```

9 tests: the Stefan-Boltzmann constant and T^4 flux scaling, the ISS 35 kW / 275 K /
70.3 m^2 anchor to 4%, the ~10x hot-radiator leverage, mass = area x specific mass, the
solar-load distance effect, and the too-close-to-the-Sun refusal.
