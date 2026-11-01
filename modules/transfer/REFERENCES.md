# Where the numbers come from

Every quantity in `transfer` traces to a source below, or is derived by explicit math
from ones that do (CLAUDE.md §1). Units: metres, seconds internally; the public API
takes AU and returns days. Orbital radii and Isp are transfer *inputs* (they depend on
the scenario), documented here so a scenario cites one place; only defined/measured
constants are hardcoded.

## Physics constants (hardcoded - defined/measured only)

- **`GM_SUN_M3_S2 = 1.32712440018e20` m^3/s^2** - heliocentric gravitational parameter,
  IAU 2015 nominal solar mass parameter (GM_sun^N). *Defined nominal value.* Source:
  IAU 2015 Resolution B3, https://www.iau.org/static/resolutions/IAU2015_English.pdf .
  Verdict: exact (adopted nominal). This is the one constant the whole Hohmann/Edelbaum
  computation rests on.
- **`AU_M = 1.495978707e11` m** - astronomical unit, IAU 2012 exact definition. Source:
  IAU 2012 Resolution B2 / IAU 2015, https://www.iau.org/static/resolutions/IAU2015_English.pdf .
  Verdict: exact (defined).
- **`SECONDS_PER_DAY = 86400` s** - exact (86400 SI seconds per day).
- **`g0 = 9.80665` m/s^2** - standard gravity, reused from `launch-economics`
  (not redefined here). Turns Isp into exhaust velocity in the SEP thrust and rocket
  equation. Exact by definition (BIPM/SI).

## Reference orbital elements (inputs, not constants)

Heliocentric semi-major axes, AU:
- **Earth 1.0000, Mars 1.5237, Jupiter 5.2034** - NASA Planetary Fact Sheet,
  https://nssdc.gsfc.nasa.gov/planetary/factsheet/ . Verdict: measured, canonical.
- **Ceres / main-belt reference 2.77** - NASA/JPL Small-Body Database,
  https://ssd.jpl.nasa.gov/ . Verdict: measured.

Sidereal orbital periods, days (synodic-cadence inputs):
- **Earth 365.256, Mars 686.980** - NASA Planetary Fact Sheet (as above). Verdict:
  measured.

## Specific impulse (inputs, reused from launch-economics)

- **Chemical Isp ~300-452 s** (LOX/RP-1 ~300-340; LOX/LH2 ~450). Source: already in
  `launch-economics/REFERENCES.md` (Sutton & Biblarz). Used as the chemical baseline in
  the SEP-vs-chemical propellant cross-check.
- **Electric-propulsion Isp ~1500-4190 s** (ion/Hall; NEXT-C 4190 s flown on DART).
  Source: `launch-economics/REFERENCES.md`; NASA NEXT-C, NTRS 20210018563. Used as the
  SEP Isp band.

## Formulas (derived, not hardcoded)

- **Hohmann two-burn Δv and time** - vis-viva; standard result (Curtis, *Orbital
  Mechanics for Engineering Students*, already in the bibliography). `dv1 = v1
  (sqrt(2 r2/(r1+r2)) - 1)`, `dv2 = v2 (1 - sqrt(2 r1/(r1+r2)))`, `t = pi
  sqrt((r1+r2)^3 / (8 GM_sun))`. Derived in `orbits.py`, verified numerically below.
- **Synodic period** `T_syn = 1 / |1/T1 - 1/T2|` - standard result. Derived.
- **Tsiolkovsky mass ratio** `m0/mf = exp(Δv/v_e)` - reused from `launch-economics`
  (`rocket_equation_mass_ratio`), not re-derived here (single source of truth).
- **Edelbaum low-thrust Δv** `Δv = sqrt(V1^2 - 2 V1 V2 cos((pi/2) dtheta) + V2^2)` -
  Edelbaum (1961), *Propulsion Powered by a Photon or Ion Beam...*, ARS Journal
  31(8):1079, https://doi.org/10.2514/8.5723 . For a coplanar (dtheta = 0) circle-to-
  circle transfer this reduces exactly to `Δv = |V1 - V2|`. Verdict: sourced closed
  form.
- **SEP jet-power thrust** `F = 2 eta P / (g0 Isp) = 2 eta P / v_e` - the standard
  jet-power-to-thrust relation `P_jet = F v_e / 2`. Cross-checked against a flown
  system below.
- **SEP available power** `P(d) = P0 * S(d)/S(1 AU) = P0 / d^2` - reuses `probe-sim`'s
  `solar_irradiance_w_m2` (solar constant 1360.8 W/m^2, Kopp & Lean 2011) so the solar
  constant lives in exactly one place. The ratio is the pure inverse-square factor.

## Cross-checks against flown missions (validation anchors)

- **Psyche Hall thruster: ~60 mN/kW.** `F/P = 2 eta/(g0 Isp)` at Isp 1820 s, eta 0.5
  gives 56 mN/kW - within ~7% of the quoted ~60 mN/kW. Source: eoPortal Psyche,
  https://www.eoportal.org/satellite-missions/psyche . Verdict: derivation matches
  flight hardware.
- **Dawn SEP mission: 11.5 km/s total Δv, 0.5-2.55 kW over 1-3 AU.** Confirms the
  1/d^2 SEP power envelope and the km/s-scale mission Δv. Source: NASA NTRS
  20210008613, https://ntrs.nasa.gov/citations/20210008613 . Verdict: envelope check.

## Verified derived targets (recomputed from the constants above; asserted in tests)

- **Earth circular speed** = 29.785 km/s (matches the known ~29.78 km/s).
- **Earth->Mars Hohmann:** dv1 = 2945 m/s, dv2 = 2649 m/s, dv_total = 5.594 km/s;
  t = 258.9 d. Matches textbook (~2.93 km/s dv1, ~259 d). Tolerance ±0.1-0.5%.
- **Earth->Ceres (2.77 AU):** dv_total = 11.18 km/s, t = 472.6 d.
- **Earth->Jupiter:** dv_total = 14.44 km/s, t = 997.6 d (~2.7 yr) - the reason Jupiter
  missions use gravity assists.
- **Same orbit:** dv_total = 0 exactly; t = 182.6 d (half the 1 AU period).
- **Earth-Mars synodic period** = 779.9 d (~2.14 yr).
- **Edelbaum coplanar Earth->Mars** Δv = |V1 - V2| = 5.656 km/s - slightly *above* the
  impulsive Hohmann 5.594 km/s, as expected (a continuous spiral is less efficient than
  a two-burn transfer). The suite asserts `edelbaum_dv >= hohmann_dv_total` for all
  coplanar circle-to-circle cases.
- **SEP power law:** at 2.77 AU, P = 0.130 P0; at 5.2 AU, P = 0.037 P0 (1/d^2).

## Notes on measurement basis (CLAUDE.md §1)

- All Δv here is **heliocentric** (Sun-centred circular-orbit change), NOT the from-LEO
  departure Δv in `launch-economics`' budget table. They are different quantities; a
  scenario must state which it uses. `transfer`'s heliocentric values cross-check the
  heliocentric legs, not the LEO-departure budgets.
- The SEP trip time uses **constant thrust acceleration** at the initial wet mass - a
  documented modelling assumption (the one in Scope), making the estimate a conservative
  upper bound. Real thrusters shed mass and arrive a little sooner. We do not integrate
  the mass loss (that would be a trajectory simulator this module avoids, CLAUDE.md §3).

## Further reading and cross-checks (bibliography)

These ground the module's ideas or cross-check its numbers; they are consolidated in
the project bibliography (`frontend/src/sources.ts`) and not new numbers in the code.

- **Edelbaum 1961** - T. N. Edelbaum (1961). Propulsion Powered by a Photon or Ion
  Beam: Orbit transfer with low-thrust. ARS Journal 31(8):1079-1089. DOI
  10.2514/8.5723. https://doi.org/10.2514/8.5723 . The closed form behind the low-thrust
  spiral Δv and its coplanar reduction to |V1 - V2|.
- **Curtis 2020** - H. D. Curtis. Orbital Mechanics for Engineering Students (4th ed.).
  Butterworth-Heinemann, ISBN 978-0-12-824025-0. The vis-viva derivation behind the
  Hohmann Δv and half-ellipse transfer time.
- **IAU 2015 Resolution B3** - IAU (2015). Nominal solar and planetary conversion
  constants. https://www.iau.org/static/resolutions/IAU2015_English.pdf . The nominal
  GM_sun and the AU definition.

## Invariants (issue #48, phase B)

`HohmannResult` is a frozen dataclass with a `__post_init__` postcondition. Runs
in release (never gated).

- **[inv:tr-hohmann]** `dv_total_m_s >= 0` and `dv_total_m_s == |dv1| + |dv2|`
  (within `1e-9` relative); `transfer_time_days > 0`. `dv1` and `dv2` signs carry
  meaning (departure vs. circularization burn) and are not constrained.

Tests: `tests/test_invariants.py`.
