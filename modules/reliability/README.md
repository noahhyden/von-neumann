# reliability - things wear out, fail, and die off

Every other model in the project is optimistic in the same quiet way: nothing ages,
nothing breaks, nothing dies. A probe's array is as good on day 10,000 as on day one, and
a fleet only ever grows. `reliability` adds the real-world messiness CLAUDE.md 3 asks for
- degradation, mortality, and a genuine steady state - and it is the one module that uses
randomness, so it does so under the strictest discipline in the repo.

## What it models

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

## The two guarantees that make the RNG safe

- **Reproducible.** The generator is a pure function of an explicit integer seed - never a
  wall clock, never a global. Replaying a seed reproduces the fleet trajectory exactly.
- **hazard = 0 is a no-op.** With zero hazard no unit can die, so the population is
  identical to the project's existing failure-free models. The suite asserts this
  bit-exact across seeds - the mandatory regression guard, so adding mortality disturbs
  nothing that came before.

## What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No dose -> single-event-effect -> latchup chain, no per-component FMEA, no neutron
transport. Hazard is one sourced per-day rate, degradation one sourced annual rate, Aurora
a two-parameter ODE. This is the module most tempted into nested sub-simulations, and it
declines.

## What it found

- **The fleet has a ceiling, not a runaway.** Once settled sites die at a finite rate, the
  settled fraction plateaus at `1 - T_l/T_s` instead of filling everything - and if spread
  is slower than die-off, it collapses to zero.
- **Ageing quietly erodes the multi-decade case.** A ~0.3 %/yr array loss is ~5% gone over
  a 17-year build-out, before a single random failure - a derate the ageless models miss.

## Interfaces

- **consumes `shielding.radenv`:** the shared radiation environment.
- **-> `multi-probe` / `swarm`:** the Aurora plateau and the mortality fold.
- **-> `closure-sim` / `mission`:** power and electronics derating over time.

## Run the tests

```
uv run --extra dev pytest -q
```

12 tests: RNG determinism, the seeded fold reproducing bit-for-bit, the **hazard=0
bit-exact regression**, statistical unbiasedness vs `(1-h)^days`, the Aurora formula and
its ODE convergence (and collapse when `T_l >= T_s`), and the degradation/dose decay.
