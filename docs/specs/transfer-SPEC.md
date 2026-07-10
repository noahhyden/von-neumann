# transfer - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. This is the first module from
`ROADMAP-PROPOSAL.md` worked up to an implementable spec: scope, sourced numbers in
`REFERENCES.md` format, the math, the API, a validation plan with verified targets, and
the interface wiring. Every derived target below was recomputed and confirmed (see
"Validation"), not copied from a summary.

`transfer` is the highest-confidence candidate: the physics is textbook-exact and every
input constant is canonically citable. It retires `multi-probe`'s hand-set transit time
and makes the ~13.6 AU expansion wall a derived output.

---

## Scope

**Models (pure, deterministic, plain-data functions - zero pimas imports, no RNG):**

1. **High-thrust (Hohmann/impulsive):** two-burn Delta-v and transfer time between two
   circular coplanar heliocentric orbits, from GM_sun and the orbital radii. Plus the
   synodic period (launch-window cadence) between any two bodies.
2. **Low-thrust (solar-electric):** the rocket-equation propellant for a given Delta-v
   and Isp (reuses `launch-economics`), a distance-aware available-power model
   `P(d) = P0 * (1 AU / d)^2` (reuses `probe-sim`'s solar law), the resulting thrust
   `F = 2*eta*P / (g0*Isp)`, and trip time via **Edelbaum's** closed form:
   `Delta_V = sqrt(V1^2 - 2 V1 V2 cos((pi/2)*Delta_theta) + V2^2)`, `t = Delta_V / a`
   with `a = F / m`. For coplanar circle-to-circle heliocentric hops this reduces to
   `Delta_V = |V1 - V2|`.

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3):
- No full N-body or patched-conic beyond a single central body (no SOI hyperbolae, no
  ephemeris propagation).
- No trajectory optimization (no continuous-thrust optimizer, no coast-arc scheduling,
  no gravity-assist chaining - interstellar slingshots stay in `swarm`).
- No plane changes / eccentricity / phasing beyond the coplanar-circular idealization
  (enters only as a documented Delta-v margin parameter, if at all).
- Constant thrust acceleration for the Edelbaum leg (real thrusters lose mass, raising
  `a` over the burn) - documented as the one modelling assumption, not simulated.

---

## Sourced numbers (REFERENCES.md format)

All constants trace to sources already in the project bibliography
(`frontend/src/sources.ts`). Nothing here is invented.

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| 1.32712440018e20 | m^3/s^2 | GM_sun (heliocentric gravitational parameter, IAU nominal) | IAU 2015 Resolution B2 | https://www.iau.org/static/resolutions/IAU2015_English.pdf | exact (defined nominal) |
| 1.495978707e11 | m | Astronomical unit (IAU 2012 defn) | IAU 2015 | https://www.iau.org/static/resolutions/IAU2015_English.pdf | exact (defined) |
| 9.80665 | m/s^2 | Standard gravity g0 (for Isp -> exhaust velocity) | already in launch-economics/REFERENCES.md | (repo) | exact (defined) |
| 1.0000 | AU | Earth semi-major axis | NASA Planetary Fact Sheet | https://nssdc.gsfc.nasa.gov/planetary/factsheet/ | measured |
| 1.5237 | AU | Mars semi-major axis | NASA Planetary Fact Sheet | https://nssdc.gsfc.nasa.gov/planetary/factsheet/ | measured |
| 2.77 | AU | Ceres / main-belt reference orbit | NASA/JPL small-body database | https://ssd.jpl.nasa.gov/ | measured |
| 5.2034 | AU | Jupiter semi-major axis | NASA Planetary Fact Sheet | https://nssdc.gsfc.nasa.gov/planetary/factsheet/ | measured |
| 365.256 / 686.98 | days | Earth / Mars sidereal orbital periods (synodic input) | NASA Planetary Fact Sheet | https://nssdc.gsfc.nasa.gov/planetary/factsheet/ | measured |
| 300-452 | s | Chemical Isp band (LOX/RP-1 ~300-340; LOX/LH2 ~450) | already in launch-economics/REFERENCES.md | (repo) | sourced |
| 1500-4190 | s | Electric-propulsion Isp band (ion/Hall; NEXT-C 4190) | already in launch-economics/REFERENCES.md; NASA NEXT-C | https://ntrs.nasa.gov/citations/20210024276 | sourced |
| Delta_V = sqrt(V1^2 - 2 V1 V2 cos((pi/2)*Delta_theta) + V2^2) | - | Edelbaum low-thrust circle-to-circle Delta-v | Edelbaum (1961), ARS Journal 31(8):1079 | https://doi.org/10.2514/8.5723 | sourced (closed form) |
| Dawn 11.5 km/s total; 0.5-2.55 kW over 1-3 AU | mixed | Real SEP mission cross-check (1/d^2 power envelope) | NASA NTRS | https://ntrs.nasa.gov/citations/20210008613 | sourced |
| Psyche 4.5 kW, ~0.27 N, Isp 1820 s | mixed | Real Hall-thruster F/P cross-check (~60 mN/kW) | eoPortal | https://www.eoportal.org/satellite-missions/psyche | sourced |

Derived (shown, not assumed): Hohmann Delta-v and time from the formulas below; F/P sanity
check `F/P = 2*eta/(g0*Isp)` -> at Isp 1820 s, eta 0.5: 56 mN/kW, matching Psyche's
60 mN/kW. Constants for the SEP power law reuse `probe-sim`'s solar constant
(1360.8 W/m^2, Kopp & Lean 2011) - do not redefine it.

---

## The math

Hohmann (per-burn Delta-v and half-ellipse time), `mu = GM_sun`:
```
v1 = sqrt(mu/r1);  v2 = sqrt(mu/r2)
dv1 = v1 * (sqrt(2*r2/(r1+r2)) - 1)
dv2 = v2 * (1 - sqrt(2*r1/(r1+r2)))
dv_total = |dv1| + |dv2|
t_transfer = pi * sqrt((r1+r2)^3 / (8*mu))
```
Synodic period (launch-window cadence): `T_syn = 1 / |1/T1 - 1/T2|`.

Low-thrust (SEP): `P(d) = P0 * (1 AU / d)^2`; `F = 2*eta*P(d) / (g0*Isp)`;
`a = F / m`; Edelbaum `Delta_V` as above; `t = Delta_V / a`. The impulsive Hohmann time
is the physical lower bound on trip time; the Edelbaum `t` is the many-revolution
low-thrust estimate.

---

## Proposed API

```python
def hohmann_transfer(r1_au: float, r2_au: float) -> HohmannResult:
    """Two-burn heliocentric Delta-v (m/s) and transfer time (days)."""

def synodic_period(period1_days: float, period2_days: float) -> float:
    """Launch-window cadence (days) between two circular orbits."""

def sep_transfer(dv_m_s: float, isp_s: float, dry_mass_kg: float,
                 power_W_at_1AU: float, distance_au: float,
                 efficiency: float) -> SepResult:
    """Rocket-equation propellant (kg), thrust (N), acceleration (m/s^2),
    and Edelbaum trip-time estimate (days) with impulsive lower bound."""
```
All return frozen dataclasses of plain floats. Pure functions; no globals, no clock, no
RNG. `sep_transfer` calls `launch_economics.rocket_equation_mass_ratio` rather than
re-deriving Tsiolkovsky.

---

## Validation plan (verified targets)

Each target below was recomputed from the sourced constants and confirmed; the test
suite asserts these to stated tolerances (behavior + edges, CLAUDE.md 2).

Real transfers (heliocentric two-burn):
- Earth->Mars: `dv_total = 5.59 km/s` (dv1 2945, dv2 2649 m/s), `t = 258.9 d` (0.71 yr).
  Matches textbook (~259 d; Wikipedia dv1 2.93 km/s). Tolerance +/- 1%.
- Earth->Ceres (2.77 AU): `dv_total = 11.18 km/s`, `t = 472.6 d`.
- Earth->Jupiter: `dv_total = 14.44 km/s`, `t = 997.6 d` (2.73 yr) - explains why Jupiter
  needs gravity assists.

Edges:
- Same orbit (r1 = r2): `dv_total = 0` exactly; `t = half orbital period` (182.6 d at
  1 AU). Assert dv is identically 0, not a small float.
- Monotonicity: farther target -> longer time and larger dv1 (outbound).

Synodic:
- Earth-Mars synodic period = 779.9 d (2.14 yr). Tolerance +/- 0.1%.

Low-thrust (Edelbaum / SEP):
- Coplanar Earth->Mars `Delta_V = |V1 - V2| = 5.66 km/s` - note this is slightly ABOVE
  the impulsive Hohmann 5.59 km/s (a continuous spiral is less efficient than a two-burn
  transfer). Assert `edelbaum_dv >= hohmann_dv_total` for coplanar circle-to-circle.
- SEP power law: available power at 2.77 AU = 0.130x its 1 AU value; at 5.2 AU = 0.037x.
  Assert the 1/d^2 scaling and that trip time grows as thrust falls with distance.
- Delta-v -> 0 => propellant -> 0 (exp(0)-1 = 0).
- High-Isp check: for a fixed hop, SEP propellant mass is ~1/6 to 1/10 of LOX/LH2 (via
  the rocket equation) - assert the ratio.

Cross-module consistency:
- `sep_transfer` propellant fraction round-trips against
  `launch_economics.rocket_equation_mass_ratio` for the same (dv, Isp).

---

## Interface wiring

- **-> multi-probe:** replaces the hand-set `transit_time` (~365 d `[ESTIMATE]`) and the
  dispersal-distance hand-waving with a derived per-leg time from `hohmann_transfer` /
  `sep_transfer`. This is the module's headline win - multi-probe's own REFERENCES.md
  flags this exact substitution as future work.
- **-> launch-economics:** adds the missing TIME dimension - pairs its abstract Delta-v
  budget with the years a transfer costs, so cost-of-mass can be weighed against
  cost-of-delay. launch-economics' Delta-v budget table becomes a cross-check for the
  derived heliocentric values (note the basis difference: heliocentric two-burn vs the
  from-LEO departure burn vs budget-table figures - document which is which, CLAUDE.md 1).
- **-> mission:** supplies the arrival distance `d` (already used for solar power) and the
  elapsed time before build-out begins.
- **reuses probe-sim:** imports the same 1360.8 W/m^2 solar constant and 1/d^2 law for the
  SEP power model; must not redefine the constant (single source of truth).
- **feeds propellant (proposed):** `transfer`'s Delta-v is the input that `propellant`
  turns into reaction-mass demand via the rocket equation.

---

## Why this is safe to build first

Highest groundability of any candidate: all constants are defined/measured and already in
the bibliography; the math is closed-form and was numerically verified above; the module
is a handful of pure functions with a clean seam to three existing modules; it retires a
real hand-set number; and every over-nesting temptation (a trajectory optimizer) has a
documented "not this module" boundary. It is the natural first step from proposal to code.
</content>
