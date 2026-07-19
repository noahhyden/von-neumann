# Where the numbers come from

Every quantity in `power-source` traces to a source below, or is derived from ones that
do (CLAUDE.md 1). Units: W, W/kg, kg, AU, years. Specific powers are the load-bearing
inputs; the crossovers are derived from them.

## Specific power, W/kg (basis: flight system-level, pinned per CLAUDE.md 1)

Solar specific power spans ~4x depending on basis (bare blanket vs wing vs full flight
system with gimbals and structure). We pin the **conservative flight system-level** value.

- **`SOLAR_SPECIFIC_POWER_1AU_W_PER_KG = 100`** - Redwire Roll-Out Solar Array (ROSA)
  flight system-level ~100-120 W/kg; wing-level and test articles reach 200-500 W/kg (the
  4x span). Sources: ROSA, https://en.wikipedia.org/wiki/Roll_Out_Solar_Array ; eoPortal
  ISS-ROSA, https://www.eoportal.org/satellite-missions/iss-rosa . Verdict: sourced;
  basis pinned to system-level (conservative). A scenario may raise it toward wing-level
  with justification.
- **`FISSION_SPECIFIC_POWER_W_PER_KG = 6.7`** - NASA Kilopower 10 kWe class, ~1500 kg ->
  6.7 W/kg (an 800 We unit is ~400 kg -> 2 W/kg; band ~2-7). Source: NASA Kilopower,
  https://ntrs.nasa.gov/api/citations/20140010823/downloads/20140010823.pdf ;
  https://en.wikipedia.org/wiki/Kilopower . Verdict: sourced.
- **`GPHS_RTG_SPECIFIC_POWER_W_PER_KG = 5.2`** - GPHS-RTG (Cassini, New Horizons):
  ~300 We BOL, ~57 kg -> 5.2 W/kg, 8.1 kg Pu-238, 4400 Wth. Source:
  https://en.wikipedia.org/wiki/GPHS-RTG ; NASA Cassini RTG,
  https://science.nasa.gov/mission/cassini/radioisotope-thermoelectric-generator/ .
  Verdict: sourced.
- **`MMRTG_SPECIFIC_POWER_W_PER_KG = 2.4`** - MMRTG (Curiosity, Perseverance): ~110 We,
  45 kg -> ~2.4 W/kg. Source: https://en.wikipedia.org/wiki/Multi-mission_radioisotope_thermoelectric_generator .
  Verdict: sourced.

## Crossovers (derived, shown)

- **Distance crossover** `d_cross = sqrt(sp_solar_1AU / sp_nuclear)` - set solar
  `sp_solar_1AU/d^2` equal to the distance-independent nuclear specific power. The power
  level P cancels (both source masses scale linearly with P), so the crossover is
  independent of how much power you need. Against fission: sqrt(100/6.7) = **3.86 AU**;
  against an RTG: sqrt(100/5.2) = **4.39 AU**. The 4-5 AU band matches reality: Juno runs
  solar at Jupiter's 5.2 AU (with very large arrays - the boundary exception), and deep-
  space missions beyond use radioisotope power. Verdict: derived; reality cross-check.
- **`RTG_FISSION_CROSSOVER_WE = 1000`** - below ~1 kWe an RTG is lighter (graceful
  scaling); above it fission wins (its fixed reactor/shield/radiator overhead amortises).
  Source: Kilopower program rationale (fission targets kWe-class and up; RTGs serve the
  hundreds-of-watts range flown to date). Verdict: sourced (order-of-magnitude threshold).

## The Pu-238 vitamin wall

- **`PU238_PER_GPHS_RTG_KG = 8.1`** - one GPHS-RTG's fuel load (above). Verdict: sourced.
- **`PU238_ANNUAL_PRODUCTION_KG = (0.5, 1.5)`** - US production: DOE delivered ~0.5 kg in
  2023 and is on track for its **1.5 kg/yr** goal by 2026 (production restarted after a
  27-year gap). Sources: DOE, https://www.energy.gov/ne/articles/us-department-energy-completes-major-shipment-plutonium-238-nasa-missions ;
  https://en.wikipedia.org/wiki/Plutonium-238 . Verdict: sourced.
- **Derived:** one GPHS-RTG's 8.1 kg is 5.4 years of the entire US supply at the 1.5
  kg/yr goal (16 years at today's ~0.5). A fleet of RTGs is throttled by an isotope no
  factory can produce in place - the sharpest vitamin in the project.

## Reactor radiator (delegates to thermal)

- **`FISSION_CONVERSION_EFFICIENCY = 0.30`** - Kilopower Stirling thermal-to-electric
  conversion ~30%. Source: NASA Kilopower (above). Waste heat = P_e (1-eff)/eff.
- **`FISSION_RADIATOR_TEMP_K = 500`** - representative Stirling cold-side / radiator
  temperature; a hot radiator is light (thermal's T^4 leverage). Source: Kilopower.
  Verdict: sourced (representative). The radiator area/mass come from
  `thermal.size_radiator` - the Stefan-Boltzmann model lives in one place.

## Interface wiring

- **-> power-budget:** emits available power at a distance (`solar_specific_power_at`
  times a chosen mass, or a nuclear source's constant power).
- **-> closure-sim:** the source mass is a BOM line; the Pu-238 requirement is a hard
  import (vitamin) for any RTG-powered design.
- **calls thermal:** `fission_reactor_radiator` sizes the reactor's radiator via
  `thermal.size_radiator` (does not re-implement Stefan-Boltzmann).
- **reuses probe-sim:** the 1/d^2 solar law (single source of truth for the solar
  constant).

## Further reading (bibliography)

- **NASA Kilopower / KRUSTY** - kWe-class space fission specific power and conversion
  efficiency behind the fission figures.
- **DOE Pu-238 program** - the 0.5 -> 1.5 kg/yr production ramp behind the vitamin wall.
- **World Nuclear Association, "Nuclear Reactors for Space"** -
  https://world-nuclear.org/information-library/non-power-nuclear-applications/transport/nuclear-reactors-for-space -
  cross-check on RTG/fission flight history and the power ranges each serves.

## Analytical companion (issue #50, Phase 2)

`docs/FINDINGS_CLASSIFICATION.md` #24 asserts the solar/nuclear crossover
distance is a technology-only constant. Derivation:

At distance d, the solar array's specific power is `sp_solar(d) = sp_solar_1AU / d^2`
(the `1/d^2` law). A nuclear source has distance-independent specific power
`sp_nuclear`. To deliver power P, the source masses are

    m_solar(P, d)   = P * d^2 / sp_solar_1AU
    m_nuclear(P)    = P / sp_nuclear

Equating gives

    d_cross^2 = sp_solar_1AU / sp_nuclear
    d_cross = sqrt(sp_solar_1AU / sp_nuclear)

**P cancels**: the crossover is a property of the two technologies, not the
mission's power level. At defaults (`sp_solar_1AU = 100 W/kg`,
`sp_nuclear = 6.7 W/kg` fission) this is ~3.86 AU, matching the sourced
"4-5 AU" band and reality (Juno at Jupiter's 5.2 AU is right at the boundary
with an oversized array).

Tests in `tests/test_analytical_companions.py` assert (i) the closed form
matches the code, (ii) crossover is invariant under P-rescaling (verifying
the cancellation), (iii) the mass-order flips at exactly `d_cross`.
