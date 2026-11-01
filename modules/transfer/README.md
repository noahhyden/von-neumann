# transfer - how far, in Δv and years

A self-replicating probe does not teleport to its target. It spends propellant to
change orbit, and it spends *time* getting there - and both grow with distance. This
module turns "how far" into the two numbers every mission planner actually needs:
**how much Δv** a transfer costs, and **how long** it takes.

Before this module, `multi-probe` used a hand-set ~365-day transit time (its own
REFERENCES.md flagged that as future work). `transfer` replaces that guess with a
derived time from the orbital mechanics, and turns the expansion wall - how far a
fleet can practically spread - into an output rather than an assumption.

## What it models

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

## What it does NOT model (over-nesting guardrails, CLAUDE.md §3)

No trajectory optimizer, no coast-arc scheduling, no gravity-assist chaining
(interstellar slingshots stay in `swarm`); no N-body or patched-conic beyond a single
central body; no plane-change/eccentricity beyond the coplanar-circular idealization
(a plane change enters only as Edelbaum's angle parameter); constant thrust
acceleration on the SEP leg is a documented assumption, not a simulation.

## What it found

- **Earth->Mars costs 5.59 km/s and 259 days; Earth->Jupiter costs 14.4 km/s and 2.7
  years** - which is exactly why Jupiter missions use gravity assists rather than a
  direct Hohmann transfer.
- **A continuous SEP spiral is *less* Δv-efficient than a two-burn Hohmann** (Earth->
  Mars: 5.66 vs 5.59 km/s) - but its high Isp means it burns a small fraction of the
  reaction mass, trading propellant for time.
- **SEP power, and therefore thrust, falls as 1/d^2** - the same law that gates a solar
  probe's range - so a low-thrust leg stretches out sharply with distance.

## Interfaces

- **-> `multi-probe`:** replaces the hand-set transit time with a derived per-leg time.
- **-> `launch-economics`:** adds the time dimension to its Δv/cost budget (mind the
  basis: heliocentric two-burn here vs from-LEO departure there - see REFERENCES.md).
- **-> `mission`:** supplies arrival distance and elapsed transit time before build-out.
- **reuses `probe-sim`** (1/d^2 solar law, one solar constant) and **`launch-economics`**
  (Tsiolkovsky, g0) rather than redefining either.
- **feeds `propellant`** (proposed): its Δv is what a propellant-closure model turns
  into reaction-mass demand.

## Run the tests

```
uv run --extra dev pytest -q
```

21 tests: real transfers vs textbook values, the zero-Δv and equal-period edges,
monotonicity, the Edelbaum >= Hohmann inequality, the 1/d^2 power law, the Psyche
F/P cross-check, and the propellant round-trip against `launch-economics`.
