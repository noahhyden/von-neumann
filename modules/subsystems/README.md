# subsystems - spacecraft subsystem physics

Ten subsystem models that feed the probe, fleet and mission folds. Each is a submodule
(`subsystems.thermal`, `subsystems.transfer`, ...) rather than a module of its own,
because none of them has a presentation surface, a paper, or a second importer.

| Submodule | What it answers |
|---|---|
| `assembly` | Robotic build rate from published metal-AM deposition rates and OEE; the fleet doubling clock, with a 12-274 kg/day band |
| `autonomy` | Onboard compute demand against probe-sim's 1/d^2 supply, and the autonomy wall |
| `comms` | Deep-space downlink rate vs distance, `min(k/d^2, R_max)`, and the data-return wall |
| `isru` | Electrical energy to make oxygen and metal from regolith, and the closure ceiling a body's elements set |
| `power_source` | Solar vs fission vs RTG: the distance crossover `d = sqrt(sp_solar/sp_nuclear)`, and the Pu-238 vitamin wall |
| `propellant` | Reaction-mass demand (Tsiolkovsky), in-situ propellant energy, and the noble-gas import wall |
| `reliability` | Array and dose decay, a seeded per-day hazard fold, and the Aurora steady state `X_eq = 1 - T_l/T_s` |
| `shielding` | Shielding mass from areal-density attenuation: monotonic TID, the non-monotonic GCR dose minimum, and the shared `radenv` primitive |
| `thermal` | Heat rejection and radiator sizing (Stefan-Boltzmann), and the `T^4` leverage of hot radiators |
| `transfer` | Hohmann and impulsive delta-v, synodic windows, and low-thrust Edelbaum trip time |

Each submodule's full write-up is under [Submodule detail](#submodule-detail) below.

## Why one module and not ten

A directory per model is the right default when a model is something a reader can be
shown. None of these ten is. Measured over the import DAG before the merge: none had a
frontend surface, none sourced a paper, and nothing outside this set imported any of
them. The only cross-module edges among them (`reliability -> shielding`,
`power_source -> thermal`, `propellant -> transfer`) had both ends inside the set, so
folding turned three cross-module dependencies into ordinary internal imports and lost
no seam that anything else could see.

What ten directories did cost was ten `pyproject.toml` files, ten `uv.lock` files, ten
virtualenvs and ten test suites for about 1900 lines of code, plus ten entries in
`modules/` for a reader to scan before finding the models that do have surfaces.

The rule this follows is in [`modules/README.md`](../README.md): a module earns its own
directory by having a presentation surface, a paper, or two or more importers.

## Interfaces

Depends outward on `vn-core`, `probe-sim`, `power-budget` and `launch-economics`.
Nothing imports `subsystems`, so it sits at the top of the import DAG; if something
comes to depend on one of these submodules, that is the signal to look again at whether
it should be promoted back out.

Each submodule re-exports its public API from its own `__init__.py`, so
`from subsystems.thermal import size_radiator` is the supported form. Reaching past that
into a submodule's internals is the same mistake across submodules as it was across
modules.

## References

Numbers and their sources are in [`REFERENCES.md`](REFERENCES.md), one section per
submodule. That file is the ten former per-module `REFERENCES.md` files concatenated
without edit; nothing was reworded or dropped in the merge.

## Develop

```sh
uv run --extra dev pytest -q              # the whole module
uv run --extra dev pytest -q tests/thermal   # one submodule
```

Test basenames repeat across submodules (every one has a `test_distributions.py`), so
the suite runs under `--import-mode=importlib`, set in `pyproject.toml`.

---

# Submodule detail

The ten former per-module READMEs, restored verbatim when those modules became
submodules; each section is one former file, its headings demoted one level. The
prose was not rewritten or shortened, so the plain-language 'why' for every
submodule is still here rather than only in git history.

## assembly

## assembly - the build rate that sets the whole clock

How fast can a self-replicating factory turn raw feedstock into installed machinery?
That single number - kilograms built per day - is the most load-bearing assumption in
the entire project. `closure-sim` and `multi-probe` take it as a hand-set input
(~20 kg/day), and it alone fixes the fleet's doubling cadence: the time to build one
copy is `closure_ratio * seed_mass / build_rate`, which is FINDINGS #9's ~582-day clock
for the lunar seed. This module derives that rate from published numbers instead of
assuming it.

### What it models

`rate.py`, pure algebra (no discrete-event assembly simulator - that would be
over-nesting, CLAUDE.md §3):

    build_rate = manipulators * deposition_rate * hours_per_day * duty_cycle * yield

- **`machinery_build_rate_kg_per_day(...)`** - the derivation, from real metal additive
  manufacturing (WAAM ~1-10 kg/h, LPBF ~0.2-1.4 kg/h) and Overall Equipment
  Effectiveness (world-class 85%, quality 99.9%; typical ~60%).
- **`aasm_implied_rate_kg_per_day()`** - NASA's 1980 self-replicating lunar factory: a
  100-tonne seed that copies itself in a year implies **274 kg/day**.
- **`build_rate_band()`** - the honest `[ESTIMATE]`: `low` ~2.9 (one LPBF head, typical
  OEE), `anchor` ~20.4 (one slow WAAM head, world-class OEE - reproducing closure-sim's
  20), `high` ~274 (NASA). A **>10x** spread.
- **`copy_time_days(rate, seed_mass, closure)`** - the fleet copy time (the same formula
  multi-probe uses), so the module can show its rate setting the doubling clock.

Every input is a terrestrial-robot proxy for a space factory that does not yet exist, so
the whole result is tagged `[ESTIMATE]` (see [`REFERENCES.md`](REFERENCES.md)). Pure,
deterministic, no pimas, no RNG (CLAUDE.md §7).

### What it found

- **closure-sim's 20 kg/day is a single slow head at world-class OEE.** It is not wrong -
  it is one defensible corner of a wide band. That the assumed number falls out of the
  derivation is the calibration check.
- **The build rate is a >10x uncertainty band, and so is the doubling clock.** NASA's own
  1980 study implies 274 kg/day - 13.7x closure-sim's 20 - which would cut the ~582-day
  lunar copy time to ~42 days. The fleet's entire cadence hinges on which end of this
  band is right.

### What it does NOT model (over-nesting guardrails, CLAUDE.md §3)

No discrete-event floor simulation, no per-part process planning, no thermal/mechanical
AM physics - throughput is a sourced parameter, not a simulated assembly line. Feedstock
availability is assumed (that is `isru`'s job).

### Interfaces

- **-> `closure-sim` / `multi-probe`:** supplies the `local_build_rate_kg_per_day` both
  currently hand-set. Scenarios should carry the band, not a point.
- **shares the copy-time formula with `multi-probe`** (no dependency taken - the formula
  is the clean seam); **assumes `isru`'s feedstock** without simulating it.

### Run the tests

```
uv run --extra dev pytest -q
```

9 tests: the derivation, the anchor reproducing closure-sim's 20 kg/day, NASA's 274
kg/day, the >10x band, the 582-day clock and its collapse to ~42 days at the NASA rate,
and linear scaling in manipulators and closure.

## autonomy

## autonomy - how much thinking a probe needs (not just how much it can afford)

A probe light-hours from Earth cannot phone home for instructions; it has to run its own
perception and control. `probe-sim` already worked out how much compute a probe can
*power* at a given distance (it falls as 1/d^2 with the sunlight). What was missing was
the other half: how much compute it actually *needs*. Without that, `mission` and
`multi-probe` just assumed a 0.70 manufacturing / 0.30 compute power split. This module
supplies the demand, and where demand meets the falling supply is the **autonomy wall**.

### What it models

`autonomy.py`, pure functions:

- **`required_compute_band()`** - the demand as a sourced **band, not a point**: honeybee
  brain (~1e13 ops/s), a self-driving car (~1.4e14 ops/s / 140 TOPS), and a mouse brain
  (~1e15 ops/s). The engineered self-driving figure lands between the two biological
  estimates - three independent lines converging on 1e13-1e15.
- **`compute_fraction_needed(...)`** - the **derived** compute power fraction that
  replaces the hand-set 0.30: it falls out of sourced demand and available power (140
  TOPS at 1e10 FLOPS/W on a 100 kW bus is 0.14, not 0.30).
- **`autonomy_wall_au(supply_1AU, required)`** = `sqrt(supply_1AU / required)` - the
  distance where affordable compute drops below what the probe needs. Heavier "brains"
  hit the wall sooner. Verified to equal `probe-sim`'s supply-side
  `max_distance_for_compute` - the loop is closed.

All numbers sourced in [`REFERENCES.md`](REFERENCES.md). Pure, deterministic, no pimas,
no RNG (CLAUDE.md 7).

### What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No neural-net, SLAM, or planner simulation - just accounting over sourced per-system
compute costs, exactly as `power-budget` does for watts->FLOPS. "FLOPS to run a whole
factory" is left as a tagged `[GAP]`, bounded to the anchor band rather than invented.

### What it found

- **Autonomy has its own wall, and it can be closer in than the power wall.** A probe
  that needs mouse-brain-scale compute runs out of affordable thinking far sooner than
  one that needs only honeybee-scale - the required compute, not just the available
  power, sets how far a probe can operate alone.
- **The 0.70/0.30 split was a free parameter, and now it is not.** The compute share is
  derived from demand and power, so it moves with distance and hardware efficiency
  instead of being assumed.

### Interfaces

- **<- `probe-sim`:** reuses `max_distance_for_compute` and `SolarArray`; supplies the
  sourced `required_flops` they treated as free.
- **reuses `power-budget`:** watts<->FLOPS conversion.
- **-> `mission` / `multi-probe`:** the derived compute fraction retires their 0.70/0.30
  choice; the autonomy wall is a new operating limit.

### Run the tests

```
uv run --extra dev pytest -q
```

8 tests: the three-line demand band, the power/capacity inverse, the derived compute
fraction (0.14, not 0.30) and its infeasibility guard, the 1/d^2 supply, the wall vs
demand ordering, and the loop-closure check against `probe-sim`.

## comms

## comms - how fast a probe can phone home

A self-replicating probe is only as useful as the findings it can send back. And the
further it goes, the slower it can talk: a deep-space link's data rate falls as the
**inverse square of distance**, the same law that dims its sunlight. This module turns
distance into an achievable downlink rate, and from there into a new wall the fleet
runs into.

### What it models

`link.py`, a handful of pure functions:

- **`data_rate_at(distance)` - the two-regime rate.** `R(d) = min(k/d^2, R_max)`. Far
  out the link is **power-limited** and falls as 1/d^2 (Shannon meeting Friis, confirmed
  directly by JPL's DSOC laser-comms demo). Near Earth it is **rate-limited**: the modem
  tops out at a fixed ceiling `R_max` no matter how strong the signal.
- **`calibrate_k(rate, distance)` - fit the one constant** `k = R * d^2` to a real
  mission anchor. The two DSOC anchors (25 Mbps at 1.506 AU, 8.3 Mbps at 2.582 AU) fit
  to k ~ 56 and agree to 2.5% - the built-in confirmation that the law holds.
- **`return_backlog(...)` - the data-return wall.** When a probe generates science
  faster than its link can return it, an un-sent backlog grows without bound.
- **`aggregate_return_rate_mbps(...)` - the fleet consequence.** Once every link is
  saturated, total knowledge return is the *sum of per-probe link rates*, not probe
  count. Building more probes than the 1/d^2 links can drain buys diminishing returns.

`k` and `R_max` default to the DSOC optical calibration but are parameters: RF vs
optical is the same law with a different `k` (10-100x), not a second module. Distance
is the **Earth-spacecraft range** (not heliocentric). All figures sourced in
[`REFERENCES.md`](REFERENCES.md). Deterministic, plain data, no RNG (CLAUDE.md §7).

### What it does NOT model (over-nesting guardrails, CLAUDE.md §3)

No per-photon link budget (pointing jitter, PPM slot statistics, DSN gain-vs-elevation);
no DSN scheduling/contention; no modulation/coding internals; no uplink or relay
topologies. The Friis/Shannon derivation lives in REFERENCES to justify the 1/d^2 shape;
the runtime is one division and a clamp.

### What it found

- **The link is the bottleneck, not the antenna count.** A probe at 5 AU returns only
  ~2.2 Mbps on the DSOC calibration; a probe generating 100 Mbit/s of science there
  builds an unbounded backlog. Aggregate fleet knowledge saturates at the sum of the
  distance-limited link rates.
- **Two regimes with a sharp crossover** at `d = sqrt(k/R_max) ~ 0.46 AU`: inside it
  the hardware limits you; outside it, physics does.

### Interfaces

- **-> `power-budget`:** comms is a fourth power draw (transmit power ~5% of bus power,
  derived from Voyager/New Horizons). power-budget allocates watts; comms turns them
  into bits/s.
- **parallel to `probe-sim`:** `data_rate_at(distance)` is a third 1/d^2 curve on the
  distance axis, alongside solar power and compute headroom - same shape, clean seam,
  different (Earth-range) basis.
- **composes with `swarm` (does not fuse):** swarm's `lightspeed` coordination is
  *latency* (news no sooner than dist/c); comms is *throughput* (how fast it then
  trickles in). A future coupling - swarm's news carrying a finite bit budget - is a
  later slice.

### Run the tests

```
uv run --extra dev pytest -q
```

12 tests: the two-anchor calibration agreeing to 2.5%, the 1/d^2 ratio check, both
regimes and their crossover, the near/far edges, and the data-return wall (unbounded
backlog + fleet saturation at sum-of-rates).

## isru

## isru - making feedstock from what's already there

The whole economic case for self-replication is that you don't ship mass across the
solar system - you dig it up and refine it where you land. But refining costs energy,
and some things simply cannot be made from local dirt at all. This module derives both:
the **energy** to turn regolith into usable oxygen and metal, and the **closure ceiling**
- the hard upper bound on how much of a copy can be built locally, set by which chemical
elements the body actually has.

Before this module, `closure-sim` took a hand-set ~5 kWh/kg for in-situ iron and a
hand-set `producible_locally` boolean per subsystem. `isru` grounds both.

### What it models

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

### What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No reactor, electrochemistry, or geochemistry simulation - specific energies are sourced
values with uncertainty bands, and the closure ceiling is pure mass accounting over a
sourced composition. Two internal stages (excavate -> refine) collapse into one energy
figure per material rather than a process sub-simulation.

### What it found

- **Oxygen, not metal, is the energy sink.** LOX costs ~6-7x per kg what iron does - the
  majority of regolith is oxygen, and prying it loose dominates the energy chain.
- **The Moon caps closure below 1.0 no matter how good your factory is.** With no bulk
  carbon, hydrogen, or nitrogen, every C/H/N-bearing part is a permanent import - the
  physical reason a lunar seed can never be 100% self-closing.

### Interfaces

- **-> `closure-sim`:** supplies per-material build energy (retiring the 5.0 iron
  figure) and grounds `producible_locally` / caps the closure ratio.
- **-> `propellant`** (proposed): the water-ice LOX route (~11.3 kWh/kg) as oxidiser
  energy, kept distinct from the regolith route.
- **-> `power-source` / `power-budget`:** these energies size the electrical load.

### Run the tests

```
uv run --extra dev pytest -q
```

16 tests: the LOX band and its step breakdown, the Taylor & Carrier envelope check, the
metal figures undercutting closure-sim's 5.0, oxygen-vs-metal dominance, and the closure
ceiling (full local => 1.0; absent-element parts capping it below 1.0; monotonic in
available elements; all-absent => 0.0).

## power_source

## power-source - solar, fission, or a scarce isotope

A self-replicating probe has to power itself, and the lightest way to do that flips as
it travels. Near the Sun a solar array wins hands down; far out, sunlight is too thin and
nuclear power takes over. This module finds the crossover, picks between a fission reactor
and a radioisotope generator by power level, and then confronts the awkward fact that one
of those options runs on an isotope the entire United States makes only a kilogram or two
of per year.

### What it models

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

### What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No reactor neutronics, no Stirling-cycle model, no array-degradation curve (that is
`reliability`'s job). Specific powers are sourced flight figures; the radiator is
delegated to `thermal`.

### What it found

- **The solar/nuclear line sits at ~4-5 AU and does not care how much power you need** -
  a clean, level-independent result that matches which real missions fly solar vs
  nuclear.
- **Radioisotope power is the hardest vitamin in the whole project.** It cannot be made
  in place at all, and the global production rate (~1 kg/yr) means an RTG-powered fleet
  is throttled by plutonium, not by anything a factory can build.

### Interfaces

- **-> `power-budget`:** available power at a distance.
- **-> `closure-sim`:** source mass (BOM) and the Pu-238 import for RTG designs.
- **calls `thermal`:** reactor radiator sizing.
- **reuses `probe-sim`:** the 1/d^2 solar law.

### Run the tests

```
uv run --extra dev pytest -q
```

8 tests: the 1/d^2 solar fall-off, the 4-5 AU crossover and its power-level independence,
`choose_source` matching real missions, the power-level crossover, the Pu-238 wall
(5.4 years of US supply per RTG), and the reactor radiator delegating to `thermal`.

## propellant

## propellant - the fuel you can (or cannot) make in place

A probe can smelt its own girders and still be helpless: if it has to wait for a tanker
of propellant from Earth, it is not self-replicating in any meaningful sense. This module
adds the closure axis the structural models miss - **propellant closure** - and lays bare
the trade at its centre.

### What it models

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

### What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No thruster, plume, or electrochemistry simulation; no tankage/boil-off model. Reaction
mass is Tsiolkovsky, production energy is a sourced specific energy, closure is a routing
rule. The seam with `isru` is deliberate: isru turns regolith into parts, propellant
turns water-ice into reaction mass - shared water-energy literature, separate modules.

### What it found

- **High-Isp electric propulsion is a Faustian bargain.** Xenon EP slashes the propellant
  mass a hop needs, but every kilogram is a permanent tether to Earth - and the global
  xenon supply physically caps how large such a fleet can grow.
- **Propellant closure is a separate axis from structural closure.** To be truly self-
  sufficient a probe must fly a water-derived chemical or water-electric route on a
  water-bearing body; the moment it chooses noble-gas EP, propellant closure is zero no
  matter how well its structure closes.

### Interfaces

- **<- `transfer`:** consumes the Delta-v it derives.
- **reuses `launch-economics`:** the rocket equation and g0.
- **shares Kornuta's water-ice energy with `isru`** (same figure, distinct seam).
- **-> `closure-sim` / `mission`:** imported-propellant mass is a new Earth-import term;
  the xenon wall caps electric-propulsion fleet size.

### Run the tests

```
uv run --extra dev pytest -q
```

11 tests: the 4.41 kWh/kg HHV floor, the reaction-mass round-trips against
launch-economics and transfer, the closure axis (water vs dry body vs noble gas), the
NASA xenon anchor (10 t > 10% of supply), and the mass-versus-tether trade.

## reliability

## reliability - things wear out, fail, and die off

Every other model in the project is optimistic in the same quiet way: nothing ages,
nothing breaks, nothing dies. A probe's array is as good on day 10,000 as on day one, and
a fleet only ever grows. `reliability` adds the real-world messiness CLAUDE.md 3 asks for
- degradation, mortality, and a genuine steady state - and it is the one module that uses
randomness, so it does so under the strictest discipline in the repo.

### What it models

- **`degradation.py` - deterministic wear.** `array_power_fraction(years)` compounds the
  flight-measured ~0.2-0.5 %/yr solar-array loss (worse near the Sun or in Jupiter's
  belts, via a multiplier), and `cumulative_gcr_dose_msv(days)` accumulates dose from the
  shared `shielding.radenv` rate. No RNG here.
- **`mortality.py` - stochastic failure, as a seeded fold.** `step(state, hazard)` is a
  pure fold over an explicit RNG state (`rng.py`, splitmix64): each living unit fails with
  a per-day hazard, draws taken in fixed order, RNG threaded through. Same seed reproduces
  the trajectory bit-for-bit. The hazard is a satellite-derived proxy `[ESTIMATE]`; the
  self-replication mutation rate is left as a tagged `[GAP]`.
- **`aurora.py` - the steady state.** `aurora_equilibrium(T_l, T_s) = 1 - T_l/T_s`
  (Carroll-Nellenback 2019, Eq. 32): the settled fraction where spread balances die-off.
  `T_l` is the launch/spread time, `T_s` the settlement lifetime, and a non-zero plateau
  needs `T_l < T_s`. This turns the fleet models' unbounded growth into a real equilibrium.

All numbers sourced in [`REFERENCES.md`](REFERENCES.md). No pimas.

### The two guarantees that make the RNG safe

- **Reproducible.** The generator is a pure function of an explicit integer seed - never a
  wall clock, never a global. Replaying a seed reproduces the fleet trajectory exactly.
- **hazard = 0 is a no-op.** With zero hazard no unit can die, so the population is
  identical to the project's existing failure-free models. The suite asserts this
  bit-exact across seeds - the mandatory regression guard, so adding mortality disturbs
  nothing that came before.

### What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No dose -> single-event-effect -> latchup chain, no per-component FMEA, no neutron
transport. Hazard is one sourced per-day rate, degradation one sourced annual rate, Aurora
a two-parameter ODE. This is the module most tempted into nested sub-simulations, and it
declines.

### What it found

- **The fleet has a ceiling, not a runaway.** Once settled sites die at a finite rate, the
  settled fraction plateaus at `1 - T_l/T_s` instead of filling everything - and if spread
  is slower than die-off, it collapses to zero.
- **Ageing quietly erodes the multi-decade case.** A ~0.3 %/yr array loss is ~5% gone over
  a 17-year build-out, before a single random failure - a derate the ageless models miss.

### Interfaces

- **consumes `shielding.radenv`:** the shared radiation environment.
- **-> `multi-probe` / `swarm`:** the Aurora plateau and the mortality fold.
- **-> `closure-sim` / `mission`:** power and electronics derating over time.

### Run the tests

```
uv run --extra dev pytest -q
```

12 tests: RNG determinism, the seeded fold reproducing bit-for-bit, the **hazard=0
bit-exact regression**, statistical unbiasedness vs `(1-h)^days`, the Aurora formula and
its ODE convergence (and collapse when `T_l >= T_s`), and the degradation/dose decay.

## shielding

## shielding - armour against radiation, and when more is worse

Electronics in deep space or in Jupiter's magnetosphere degrade under radiation, and the
defence is mass: shielding. This module turns a radiation dose budget into the shield
mass that meets it - and captures a fact that trips up naive models, that for one of the
two radiation regimes, piling on more shielding makes things *worse*.

### What it models

Built from published areal-density attenuation (no particle-transport code):

- **`radenv.py` - the shared radiation environment.** The GCR/Jovian dose numbers, in one
  place, consumed by both this module and `reliability` (per the proposal's cross-cutting
  note). Two bases kept strictly distinct: TID in rad(Si) for electronics, dose-
  equivalent in mSv for biology.
- **TID electronics shielding (monotonic).** `tid_attenuation_factor` and
  `areal_density_for_tid_budget` - shield until the chips' dose budget is met, using an
  exponential attenuation whose length is fit to Juno's flight anchor (1 cm Ti = ~800x).
- **GCR shielding (NON-monotonic).** `gcr_shielding_is_counterproductive` and
  `recommend_gcr_areal_density` enforce the dose-equivalent minimum near **~20 g/cm^2 Al**:
  beyond it, secondary neutrons make thicker shielding worse, so the module refuses to
  over-shield.
- **Mass and closure.** `shield_mass_kg` (areal density x area x 10) is a BOM line, but
  `closure_contribution_kg` marks locally-built regolith shielding as mass that **raises**
  closure - the opposite of imported vitamins. `regolith_thickness_for_areal_density_cm`
  answers whether cheap COTS parts behind thick local regolith can substitute for imported
  radiation-hardened parts.

All numbers sourced in [`REFERENCES.md`](REFERENCES.md). Pure, deterministic, no pimas,
no RNG (CLAUDE.md 7).

### What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No particle-transport / Monte-Carlo dose code - attenuation is a sourced exponential (TID)
plus the sourced GCR minimum. Material-dependent secondary yields are out of scope (the
regolith-vs-metal equivalence is a tagged `[ESTIMATE]` using areal density as a proxy).

### What it found

- **For GCR, "more shielding is safer" is false.** Dose-equivalent bottoms out near
  20 g/cm^2 and rises again - a model that shielded past it would produce confident
  nonsense, so the module hard-stops there.
- **Shielding is the one mass that helps closure.** Because it can be made from local
  regolith, it raises the locally-built fraction, and thick regolith can stand in for
  imported rad-hardness - letting a factory use cheap COTS electronics behind dirt.

### Interfaces

- **-> `closure-sim`:** shield mass (BOM), and the closure-raising contribution of local
  shielding.
- **shares `radenv` with `reliability`:** one radiation-environment primitive, two
  consumers.
- **<- `power-source` / `mission`:** the environment selects which dose numbers apply.

### Run the tests

```
uv run --extra dev pytest -q
```

9 tests: the areal-density/mass conversion, the Juno ~200 kg and ~800x anchors, TID
monotonicity, the GCR non-monotonic cap at 20 g/cm^2, the regolith-for-metal substitution
at equal areal density, and local shielding raising closure.

## thermal

## thermal - getting rid of the heat

Every watt a factory's power system delivers ends up as waste heat, and in the vacuum of
space the only way to get rid of it is to radiate it away. The project's own FINDINGS
call self-replication "a power-and-cooling problem, not a physics one" - but until this
module, the repo modelled the power and quietly ignored the cooling. `thermal` sizes the
radiator that rejects the heat and puts its mass on closure-sim's bill of materials, so
heat rejection stops being free.

### What it models

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

### What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No heat-pipe network, two-phase-loop, or CFD solver - radiators are sized algebraically
from Stefan-Boltzmann. Deep-space sink defaults to ~0 K; a planetary environment enters
as parameters, not a sub-simulation.

### What it found

- **Hot heat is cheap heat.** A radiator's mass per kilowatt falls as 1/T^4, so rejecting
  a smelter's 500+ K waste heat costs ~10x less radiator than the same watts from 300 K
  electronics. A single factory needs several radiators at different temperatures.
- **The physics reproduces flight hardware.** Sizing 35 kW at the ISS's 275 K coolant
  temperature gives 67.5 m^2 - within 4% of a real ISS radiator assembly's 70.3 m^2,
  which rejects exactly that per loop.

### Interfaces

- **-> `closure-sim`:** radiator mass is a new BOM line.
- **<- `power-source` / `power-budget`:** the heat load is the waste power they deliver;
  `power-source` calls `thermal` to size its radiator mass.
- **reuses `probe-sim`:** the 1/d^2 solar law for the parasitic-load term.

### Run the tests

```
uv run --extra dev pytest -q
```

9 tests: the Stefan-Boltzmann constant and T^4 flux scaling, the ISS 35 kW / 275 K /
70.3 m^2 anchor to 4%, the ~10x hot-radiator leverage, mass = area x specific mass, the
solar-load distance effect, and the too-close-to-the-Sun refusal.

## transfer

## transfer - how far, in Δv and years

A self-replicating probe does not teleport to its target. It spends propellant to
change orbit, and it spends *time* getting there - and both grow with distance. This
module turns "how far" into the two numbers every mission planner actually needs:
**how much Δv** a transfer costs, and **how long** it takes.

Before this module, `multi-probe` used a hand-set ~365-day transit time (its own
REFERENCES.md flagged that as future work). `transfer` replaces that guess with a
derived time from the orbital mechanics, and turns the expansion wall - how far a
fleet can practically spread - into an output rather than an assumption.

### What it models

Two transfer regimes, both closed-form (no optimizer, no ephemeris, no N-body):

- **`orbits.py` - impulsive (Hohmann).** The classical minimum-Δv two-burn transfer
  between two circular coplanar heliocentric orbits: departure burn, arrival burn, and
  the half-ellipse transfer time, all from GM_sun and the two orbital radii
  (`hohmann_transfer`). Plus the **synodic period** (`synodic_period_days`) - how often
  the launch window between two bodies repeats.
- **`low_thrust.py` - solar-electric (SEP).** A real ion/Hall probe thrusts
  continuously and spirals out. `sep_transfer` gives the rocket-equation propellant
  (reused from `launch-economics`), the available power at distance (reused from
  `probe-sim`'s 1/d^2 solar law), the resulting thrust and acceleration, and the trip
  time from **Edelbaum's** closed form. `edelbaum_delta_v_m_s` is the spiral Δv; for a
  coplanar hop it reduces exactly to `|V1 - V2|`.

Orbital radii and Isp are scenario *inputs* with representative sourced values in
[`REFERENCES.md`](REFERENCES.md); only defined/measured constants (GM_sun, the AU) are
hardcoded. Deterministic, plain data, zero pimas imports (CLAUDE.md §7).

### What it does NOT model (over-nesting guardrails, CLAUDE.md §3)

No trajectory optimizer, no coast-arc scheduling, no gravity-assist chaining
(interstellar slingshots stay in `swarm`); no N-body or patched-conic beyond a single
central body; no plane-change/eccentricity beyond the coplanar-circular idealization
(a plane change enters only as Edelbaum's angle parameter); constant thrust
acceleration on the SEP leg is a documented assumption, not a simulation.

### What it found

- **Earth->Mars costs 5.59 km/s and 259 days; Earth->Jupiter costs 14.4 km/s and 2.7
  years** - which is exactly why Jupiter missions use gravity assists rather than a
  direct Hohmann transfer.
- **A continuous SEP spiral is *less* Δv-efficient than a two-burn Hohmann** (Earth->
  Mars: 5.66 vs 5.59 km/s) - but its high Isp means it burns a small fraction of the
  reaction mass, trading propellant for time.
- **SEP power, and therefore thrust, falls as 1/d^2** - the same law that gates a solar
  probe's range - so a low-thrust leg stretches out sharply with distance.

### Interfaces

- **-> `multi-probe`:** replaces the hand-set transit time with a derived per-leg time.
- **-> `launch-economics`:** adds the time dimension to its Δv/cost budget (mind the
  basis: heliocentric two-burn here vs from-LEO departure there - see REFERENCES.md).
- **-> `mission`:** supplies arrival distance and elapsed transit time before build-out.
- **reuses `probe-sim`** (1/d^2 solar law, one solar constant) and **`launch-economics`**
  (Tsiolkovsky, g0) rather than redefining either.
- **feeds `propellant`** (proposed): its Δv is what a propellant-closure model turns
  into reaction-mass demand.

### Run the tests

```
uv run --extra dev pytest -q
```

21 tests: real transfers vs textbook values, the zero-Δv and equal-period edges,
monotonicity, the Edelbaum >= Hohmann inequality, the 1/d^2 power law, the Psyche
F/P cross-check, and the propellant round-trip against `launch-economics`.

