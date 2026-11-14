# power-source - solar, fission, or a scarce isotope

A self-replicating probe has to power itself, and the lightest way to do that flips as
it travels. Near the Sun a solar array wins hands down; far out, sunlight is too thin and
nuclear power takes over. This module finds the crossover, picks between a fission reactor
and a radioisotope generator by power level, and then confronts the awkward fact that one
of those options runs on an isotope the entire United States makes only a kilogram or two
of per year.

## What it models

`power_source.py`, pure functions:

- **`solar_specific_power_at(distance)`** - solar W/kg falling as 1/d^2 (reusing
  `probe-sim`'s law).
- **`crossover_distance_au(sp_solar, sp_nuclear)`** = `sqrt(sp_solar_1AU / sp_nuclear)` -
  the solar/nuclear crossover, **independent of power level** (the power cancels). ~3.9
  AU against fission, ~4.4 AU against an RTG - the 4-5 AU band where Juno sits at the
  solar edge and everything beyond goes nuclear.
- **`choose_source(distance, power)`** - "solar", "fission", or "rtg", combining the
  distance crossover with the power-level crossover (RTG below ~1 kWe, fission above).
- **`pu238_required_kg` / `years_of_pu238_production`** - the **Pu-238 vitamin wall**:
  one GPHS-RTG needs 8.1 kg of plutonium-238, and the US makes only 0.5-1.5 kg a year, so
  a single RTG is years of the entire national supply.
- **`fission_reactor_radiator(power)`** - sizes a reactor's radiator by **calling
  `thermal`** (waste heat = P_e·(1-η)/η, then Stefan-Boltzmann).

All numbers sourced in [`REFERENCES.md`](REFERENCES.md). Pure, deterministic, no pimas,
no RNG (CLAUDE.md 7).

## What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No reactor neutronics, no Stirling-cycle model, no array-degradation curve (that is
`reliability`'s job). Specific powers are sourced flight figures; the radiator is
delegated to `thermal`.

## What it found

- **The solar/nuclear line sits at ~4-5 AU and does not care how much power you need** -
  a clean, level-independent result that matches which real missions fly solar vs
  nuclear.
- **Radioisotope power is the hardest vitamin in the whole project.** It cannot be made
  in place at all, and the global production rate (~1 kg/yr) means an RTG-powered fleet
  is throttled by plutonium, not by anything a factory can build.

## Interfaces

- **-> `power-budget`:** available power at a distance.
- **-> `closure-sim`:** source mass (BOM) and the Pu-238 import for RTG designs.
- **calls `thermal`:** reactor radiator sizing.
- **reuses `probe-sim`:** the 1/d^2 solar law.

## Run the tests

```
uv run --extra dev pytest -q
```

8 tests: the 1/d^2 solar fall-off, the 4-5 AU crossover and its power-level independence,
`choose_source` matching real missions, the power-level crossover, the Pu-238 wall
(5.4 years of US supply per RTG), and the reactor radiator delegating to `thermal`.
