# Where the numbers come from

Every quantity traces to a source below, or is derived from ones that do. Units:
m/s, kg, seconds, USD. Prices are list prices and change over time - they are
scenario *inputs*, documented here, not baked into the model.

## Physics (hardcoded - defined/first-principles only)

- **`G0_M_S2 = 9.80665` m/s²** - standard gravity, *exact by definition* (BIPM/SI).
  Used only to convert specific impulse (s) to exhaust velocity.
- **Tsiolkovsky rocket equation**, `m0/mf = exp(Δv / v_e)` - Tsiolkovsky (1903);
  standard result (e.g. Curtis, *Orbital Mechanics for Engineering Students*, or
  Sutton & Biblarz, *Rocket Propulsion Elements*). Derived, not hardcoded.

## Scenario inputs (representative sourced values - not constants)

### Specific launch cost ($/kg to LEO)

- **Falcon 9 (reusable): ~$3,000/kg.** SpaceX list price ~$69.75M for ~22,800 kg to
  LEO → ~$3,060/kg. Source: SpaceX Capabilities & Services,
  https://www.spacex.com/media/Capabilities&Services.pdf . *Reasonable* - a widely
  cited ballpark; the marginal (internal, reused) cost is lower and not public.
- **Falcon Heavy: ~$1,500/kg.** ~$97M for ~63,800 kg to LEO → ~$1,520/kg (same source).
- **Starship (projected): `[ESTIMATE]`, ~$100–1,000/kg.** SpaceX targets are far
  lower (aspirational <$100/kg); no operational price exists yet. Treat as a wide
  `[ESTIMATE]` until real flight pricing is published.

### Δv budgets (m/s)

Representative one-way budgets, from standard Δv tables (e.g. NASA / Curtis):
- Earth surface → LEO: **~9,300–10,000 m/s** (including gravity and drag losses).
- LEO → trans-lunar injection: **~3,100 m/s**.
- LEO → Mars transfer injection: **~3,600 m/s**.
- LEO → Earth escape: **~3,200 m/s**.

These are inputs to `rocket_equation_mass_ratio`; a scenario must cite the specific
budget it uses.

### Specific impulse, Isp (s)

- LOX/RP-1 chemical: **~280–340 s** (e.g. Merlin 1D ~282 s sea level, ~311 s vacuum).
- LOX/LH2 chemical: **~450 s** (e.g. RS-25 ~452 s vacuum).
- Electric/ion: **~1,500–4,000 s**.
- Source: Sutton & Biblarz, *Rocket Propulsion Elements*; manufacturer data. Inputs,
  not constants.

## Notes

- The **launch-mass leverage** (`target / (seed + vitamins)`) links directly to
  `closure-sim`: the vitamin mass is set by mass closure, so higher closure → fewer
  vitamins → more leverage. Coupling the two is future work (see README).
