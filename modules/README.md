# `modules/`

One directory per model. Each is independently runnable with its own README, tests and `REFERENCES.md`.

## What is here

<!-- BEGIN GENERATED:inventory -->
`modules/` has **19** modules.

| Module | Package | Purpose |
|---|---|---|
| `assembly/` | `assembly` | Robotic build rate derived from published metal-AM deposition rates and OEE - retires closure-sim's hand-set ~20 kg/day and derives the fleet doubling clock (with the 12-274 kg/day uncertainty band) |
| `autonomy/` | `autonomy` | Onboard compute DEMAND (vs probe-sim's 1/d^2 supply) and the autonomy wall; the insect-brain-to-self-driving-car band that retires the 0.70 manuf/compute split |
| `closure-sim/` | `closure-sim` | Quantitative closure & self-replication analysis for in-situ space factories |
| `comms/` | `comms` | Deep-space downlink data rate vs distance (min(k/d^2, R_max)) and the data-return wall: probes generate bits faster than a 1/d^2 link returns them |
| `core/` | `vn-core` | Shared core primitives for the von-neumann repo. Currently: seeded mulberry32 RNG (byte-identical to the JS mirror), uncertainty quantification (distributions, seeded Monte Carlo, Sobol total-order sensitivity), and an ODE solver. Pure Python today; the layout leaves room for a future core/ rust/pyo3 speed drop-in without moving imports. |
| `isru/` | `isru` | In-situ feedstock processing: the electrical energy to make oxygen and metal from regolith (retires closure-sim's ~5 kWh/kg), and the closure ceiling set by what elements a body actually has |
| `launch-economics/` | `launch-economics` | The economics of not launching mass: launch cost, the rocket-equation Δv penalty, and the launch-mass leverage of a self-replicating seed |
| `mission/` | `mission` | The end-to-end von Neumann probe mission: launch a seed, arrive at a heliocentric distance, split solar power between building and thinking, and replicate - one pure fold over the four sibling modules |
| `multi-probe/` | `multi-probe` | A small, deterministic fleet of self-replicating probes - the intermediate step between the single probe and the swarm (seeded, speculate-exact) |
| `power-budget/` | `power-budget` | Power budgets for autonomous space factories: how a watt is split between making things and thinking, floored by the physics of computation |
| `power-source/` | `power-source` | Solar vs fission vs RTG: the distance crossover d = sqrt(sp_solar/sp_nuclear) ~4-5 AU, the power-level crossover, and the Pu-238 vitamin wall; calls thermal for reactor radiator mass |
| `probe-sim/` | `probe-sim` | A single self-replicating probe: solar-electric power vs heliocentric distance, and the range it gates (after Borgue & Hein 2020) |
| `propellant/` | `propellant` | Reaction-mass demand (Tsiolkovsky, fed by transfer's Delta-v), in-situ propellant production energy, and propellant closure vs the noble-gas import wall |
| `reliability/` | `reliability` | Degradation and mortality: deterministic array/dose decay, a SEEDED-fold per-day hazard model, and the Aurora steady-state X_eq = 1 - T_l/T_s (Carroll-Nellenback 2019) |
| `shielding/` | `shielding` | Radiation shielding mass from areal-density attenuation: monotonic TID electronics shielding, the non-monotonic GCR dose minimum, and local regolith that RAISES closure - plus the shared radenv primitive |
| `spine/` | `spine` | The cross-scale integrator - threads one closure-sim factory through the single-factory, fleet, and galaxy folds so their cadences are derived, not independently assumed |
| `swarm/` | `swarm` | A deterministic interstellar settlement front (ROADMAP §4, slice 1): probes spread star-to-star through a seeded field; how fast the reachable galaxy fills |
| `thermal/` | `thermal` | Heat rejection and radiator sizing (Stefan-Boltzmann): radiator area and mass into closure-sim's BOM, the T^4 leverage of hot radiators, and the parasitic solar-load distance story |
| `transfer/` | `transfer` | Interplanetary transfer: Hohmann/impulsive Δv and time, synodic launch windows, and low-thrust solar-electric (Edelbaum) trip time - retires multi-probe's hand-set transit time |
<!-- END GENERATED:inventory -->

Regenerate with `make modules-readme`; do not edit the table by hand.

## `core/` first: the shared primitives

`core/` is the shared-primitives package, imported as `vn_core`. Every one of the other 18 modules imports it. It holds:

- `rng` - seeded mulberry32, pinned for parity with the JS implementation.
- `uq` - distributions, Monte Carlo, Sobol sampling, polynomial chaos expansion (PCE).
- `ode` - `solve`, an RK45 Dormand-Prince integrator.
- `linalg` - `solve_lstsq`.

Before writing a numeric helper, a distribution, a sampler, an RNG or an integrator, check `vn_core` first. Re-implementing one of these is the most common way this repo grows a second, subtly different copy.

## Who owns a helper

A helper with exactly ONE consumer stays inside that consumer. At TWO or more consumers it moves to `core/`, so that neither consumer can claim it.

The reasoning: a helper placed where it was first needed records which module asked first, not what the code is. The second consumer then has to reach into the first one's internals (breaking module independence) or copy it (so the two drift apart and a fix lands in only one). Moving it to `core/` at the second consumer makes the dependency explicit and gives it one owner. Moving it earlier is speculation: with one consumer there is no evidence what the shared shape should be.

## Runs are declared, not typed

A run is a committed spec file under `<module>/runs/` (for example `modules/swarm/runs/validation.yaml`), executed with:

```
make run SPEC=modules/swarm/runs/validation.yaml
make runs        # list the declared runs
```

The spec schema is `runner/src/vn_runner/spec.py`. It forbids environment variables (`BANNED_ENV`), so a stale `export` in someone's shell cannot silently change a result.

Only `swarm` (18 specs) and `spine` (3 specs) have adopted this so far. New work should use it rather than a hand-typed command line.
