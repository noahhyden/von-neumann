# isru - making feedstock from what's already there

The whole economic case for self-replication is that you don't ship mass across the
solar system - you dig it up and refine it where you land. But refining costs energy,
and some things simply cannot be made from local dirt at all. This module derives both:
the **energy** to turn regolith into usable oxygen and metal, and the **closure ceiling**
- the hard upper bound on how much of a copy can be built locally, set by which chemical
elements the body actually has.

Before this module, `closure-sim` took a hand-set ~5 kWh/kg for in-situ iron and a
hand-set `producible_locally` boolean per subsystem. `isru` grounds both.

## What it models

- **`energy.py` - specific energy of in-situ processing.**
  - **Oxygen:** `oxygen_energy_kwh_per_kg()` returns **24.3 +/- 5.8 kWh/kg** LOX for the
    full hydrogen-reduction-of-ilmenite chain (2025 PNAS), dominated by reduction (~55%)
    and electrolysis (~38%). This is the module's most solid number - a whole chain with
    a stated uncertainty band, cross-checked against Taylor & Carrier's 18-35 kWh/kg.
  - **Metal:** `metal_energy_kwh_per_kg()` returns **2.6 (thermodynamic) to 4.0
    (practical) kWh/kg** iron via molten oxide electrolysis - below closure-sim's 5.0, so
    that guess is now grounded (and slightly conservative).
- **`closure.py` - the closure ceiling.** `closure_ceiling(parts, available_elements)`
  is the mass fraction of a copy whose parts need only locally-available elements.
  Lunar regolith has O/Si/Fe/Ca/Al/Mg/Ti in abundance but only ppm C/H/N, so anything
  needing bulk carbon, hydrogen, or nitrogen (polymers, much of the electronics) sits
  *above* the ceiling and must be imported. This is the hard cap on closure-sim's C:
  `C <= ceiling`.

Lunar tiers are solid; in-situ non-iron metal and asteroid extraction are `[ESTIMATE]`
(terrestrial proxies). All numbers sourced in [`REFERENCES.md`](REFERENCES.md). Pure,
deterministic, no pimas, no RNG (CLAUDE.md 7).

## What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No reactor, electrochemistry, or geochemistry simulation - specific energies are sourced
values with uncertainty bands, and the closure ceiling is pure mass accounting over a
sourced composition. Two internal stages (excavate -> refine) collapse into one energy
figure per material rather than a process sub-simulation.

## What it found

- **Oxygen, not metal, is the energy sink.** LOX costs ~6-7x per kg what iron does - the
  majority of regolith is oxygen, and prying it loose dominates the energy chain.
- **The Moon caps closure below 1.0 no matter how good your factory is.** With no bulk
  carbon, hydrogen, or nitrogen, every C/H/N-bearing part is a permanent import - the
  physical reason a lunar seed can never be 100% self-closing.

## Interfaces

- **-> `closure-sim`:** supplies per-material build energy (retiring the 5.0 iron
  figure) and grounds `producible_locally` / caps the closure ratio.
- **-> `propellant`** (proposed): the water-ice LOX route (~11.3 kWh/kg) as oxidiser
  energy, kept distinct from the regolith route.
- **-> `power-source` / `power-budget`:** these energies size the electrical load.

## Run the tests

```
uv run --extra dev pytest -q
```

16 tests: the LOX band and its step breakdown, the Taylor & Carrier envelope check, the
metal figures undercutting closure-sim's 5.0, oxygen-vs-metal dominance, and the closure
ceiling (full local => 1.0; absent-element parts capping it below 1.0; monotonic in
available elements; all-absent => 0.0).
