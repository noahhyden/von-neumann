# Where the numbers come from

Every quantity in `reliability` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: fraction/yr (degradation), mSv (dose), per-day (hazard),
dimensionless (Aurora fraction). This is the only module with RNG; the discipline around
it is documented as carefully as the numbers.

## RNG discipline (CLAUDE.md 7 - not a number, but load-bearing)

Randomness is a **pure seeded fold**: `rng.py` is splitmix64 (Vigna), a deterministic
64-bit generator whose state is an explicit `int` threaded through `mortality.step`. No
`random.random()`, no wall-clock seed, deterministic iteration order (one draw per living
unit, in order). Same seed -> identical trajectory, forever. Source: S. Vigna, splitmix64,
https://prng.di.unimi.it/splitmix64.c . This is what keeps replay and `speculate` exact.

## Deterministic degradation

- **`ARRAY_DEGRADATION_PER_YR = 0.003`** (band 0.002-0.010) - solar-array power loss per
  year. ISS P6 arrays degrade 0.2-0.5 %/yr (flight-measured); GEO GaAs cells 0.44-1.03
  %/yr. Sources: NASA "On-Orbit Performance Degradation of the ISS P6 Photovoltaic
  Arrays", NTRS 20030068268, https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20030068268.pdf ;
  "Solar array degradation on geostationary communications satellites", IJSPACESE 5(1),
  https://www.inderscience.com/info/inarticle.php?artid=90549 . Verdict: sourced (flight-
  measured). The 0.003 default is the ISS mid-range; `environment_multiplier` raises it
  near the Sun / in the Jovian belts (a documented parameter, not a sub-model).
- **GCR dose rate** - consumed from `shielding.radenv`
  (`GCR_DEEP_SPACE_DOSE_MSV_PER_DAY = 1.8`, MSL/RAD, Zeitlin et al. 2013). One radiation
  environment, shared - not re-defined here.

## Stochastic mortality (proxy / gap, tagged)

- **`SATELLITE_HAZARD_PER_DAY = 1.1e-5`** `[ESTIMATE]` - per-day failure hazard for a
  discrete unit. Self-replicating factories have no operational failure history, so this
  borrows a satellite-class on-orbit failure rate as a defensible analog (~0.4 %/yr).
  Verdict: `[ESTIMATE]` - a documented proxy, tagged at the use site, not a measured
  factory rate. Source: satellite on-orbit reliability statistics (order-of-magnitude).
- **Self-replication mutation rate** - a genuine `[GAP]`. Copies that build flawed copies
  have no measured rate; not modelled, only flagged. Do not invent one.
- **`expected_survival_fraction = (1 - hazard)^days`** - the analytic expectation the
  seeded fold fluctuates around (used to check the simulation is unbiased). Derived.

## The mandatory regression guard (CLAUDE.md 2)

With `hazard_per_day = 0`, a uniform draw in [0, 1) is never < 0, so no unit ever dies and
the population trajectory is **identical** to the project's current failure-free models.
The suite asserts this bit-exact across multiple seeds - the safety net that lets
mortality be added without disturbing any existing result.

## Aurora steady-state (verified against the paper)

- **`X_eq = 1 - T_l / T_s`** - equilibrium settled fraction, Carroll-Nellenback et al.
  (2019), "The Fermi Paradox and the Aurora Effect", *Astronomical Journal* 158:3, their
  **Eq. 32**. arXiv:1902.04450, https://arxiv.org/abs/1902.04450 ;
  https://iopscience.iop.org/article/10.3847/1538-3881/ab31a3 . Verdict: sourced +
  verified. The ODE is `dX/dt = (1/T_l) X (1-X) - (1/T_s) X`.
- **Symbols (verified, counterintuitive):** `T_l` = launch/spread time, `T_s` = settlement
  lifetime; a non-zero plateau requires `T_l < T_s` (spread must outrun death). An earlier
  automated read had the meanings and the inequality backwards; this was corrected against
  the primary source. Verdict: verified.

## Interface wiring

- **consumes shielding.radenv:** the shared GCR/Jovian dose numbers (single source).
- **-> multi-probe / swarm:** the Aurora equilibrium turns their unbounded growth into a
  steady state; the mortality fold adds attrition to fleet trajectories.
- **-> closure-sim / mission:** array degradation and dose derate delivered power and
  electronics life over the multi-decade build-out.

## Over-nesting boundary (CLAUDE.md 3)

No dose -> SEU -> latchup chain, no per-component FMEA, no neutron-transport - hazard is a
single sourced per-day rate, degradation a single sourced annual rate, Aurora a two-
parameter ODE. The temptation to nest dose into single-event-effect physics is
deliberately declined.

## Further reading (bibliography)

- **Carroll-Nellenback et al. 2019** - the Aurora steady-state and Eq. 32.
- **NASA ISS P6 array degradation (NTRS 20030068268)** - the flight-measured annual array
  loss behind the degradation rate.
- **Zeitlin et al. 2013** (via shielding.radenv) - the deep-space GCR dose rate.
