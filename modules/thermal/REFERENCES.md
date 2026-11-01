# Where the numbers come from

Every quantity in `thermal` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: W, W/m^2, K, m^2, kg. The core is one physical law (Stefan-
Boltzmann); the sourced inputs are emissivity, radiator areal density, and the ISS
flight anchor.

## Physics constant (defined/derived)

- **`STEFAN_BOLTZMANN_W_M2_K4 = 5.670374419e-8`** - Stefan-Boltzmann constant. Fixed by
  the SI defined constants (h, k_B, c); CODATA value. Source:
  https://physics.nist.gov/cgi-bin/cuu/Value?sigma . Verdict: exact (defined).
- **Stefan-Boltzmann law** `q = eps * sigma * T^4` (per emitting face) - standard
  radiative-transfer result. Derived, not hardcoded.

## Radiator inputs (sourced)

- **`DEFAULT_EMISSIVITY = 0.8`** - representative high-emissivity radiator coating.
  Flight radiators use high-emissivity white paints / OSRs (eps ~0.8-0.9). Source:
  Spacecraft thermal control, https://en.wikipedia.org/wiki/Spacecraft_thermal_control .
  Verdict: sourced (representative). A scenario may pin its own coating value.
- **`RADIATOR_SPECIFIC_MASS_KG_M2 = 3.0`** (band 3-12) - NASA lightweight-radiator target
  is <=3.0 kg/m^2 (achieved 3.08 kg/m^2 at 500-600 K); heavy deployable radiators with
  support structure run up to ~12 kg/m^2; fission-surface-power state of the art is
  5.24-10.95 kg/m^2. Sources: NASA STMD Advanced Lightweight Heat Rejection Radiators,
  https://www.nasa.gov/directorates/stmd/space-tech-research-grants/advanced-lightweight-heat-rejection-radiators-for-space-nuclear-power-systems/ ;
  ISNPS Tech Report 103, https://isnps.unm.edu/reports/ISNPS_Tech_Report_103.pdf .
  Verdict: sourced (target + SOA band). The 3.0 default is the aspirational target; a
  conservative scenario should use the higher band.

## ISS flight anchor (External Active Thermal Control System)

- **`ISS_HEAT_REJECTION_TOTAL_KW = 70`, `..._PER_LOOP_KW = 35`** - the EATCS provides
  35 kW of heat rejection per loop, 70 kW total across its two ammonia loops. Source:
  ISS EATCS overview (CBS/NASA), https://www.cbsnews.com/network/news/space/background/EATCS.pdf ;
  NASA ATCS overview, https://www.nasa.gov/wp-content/uploads/2021/02/473486main_iss_atcs_overview.pdf .
  Verdict: sourced.
- **`ISS_RADIATOR_TEMP_K = 275`** - the single-phase anhydrous-ammonia coolant runs ~2-6
  C (275-279 K). Source: as above. Verdict: sourced (coolant temperature; the radiating
  surface is somewhat cooler, so this is a slightly optimistic anchor - noted).
- **Radiator assembly geometry:** 8 panels of 3.33 x 2.64 m ->
  `ISS_RADIATOR_ASSEMBLY_AREA_M2 = 70.3 m^2`. Source: ISS EATCS (CBS/NASA, above).
  Verdict: sourced.

## The derivations (shown, validated in tests)

- **Flux at 275 K** (eps 0.8, two-sided, deep-space sink): `2 x 0.8 x sigma x 275^4 =
  519 W/m^2`.
- **ISS anchor:** 35 kW / 519 W/m^2 = **67.5 m^2**, within ~4% of the real 70.3 m^2
  assembly that rejects ~35 kW per loop. The one closed form reproduces flight hardware.
- **T^4 leverage:** `mass_per_kw ~ 1/T^4`, so a 533 K radiator is `(533/300)^4 = 9.96` x
  lighter per kW than a 300 K one - the proposal's "~10x lighter hot radiator".
- **Distance / solar load:** `net = 2 eps sigma T^4 - alpha S(d)`, with S(d) the solar
  irradiance reused from `probe-sim` (solar constant lives in one place). The parasitic
  term falls as 1/d^2, so radiators improve with distance; near the Sun a cold radiator
  can hot-soak (net <= 0) and the function refuses.

## Analytical companion (issue #50, #14/#15)

`docs/FINDINGS_CLASSIFICATION.md` classes both thermal headlines as A. The
point values are checked in `tests/test_thermal.py`; the companion in
`tests/test_analytical_companions.py` states the closed forms and proves the
structural fact the point tests do not - in the leverage *ratio* the emissivity,
the Stefan-Boltzmann constant, the areal density, the side count, and the heat
load all cancel.

Stefan-Boltzmann flux and mass-per-kilowatt (mu = areal density, kg/m^2):

    q(T)           = sides * eps * sigma * (T^4 - T_s^4)          [W/m^2]
    mass_per_kw(T) = 1000 * mu / q(T)  ~  1/T^4    (for T >> T_s)

**T^4 leverage (#14).** The cold-over-hot ratio drops every common factor:

    L(T_h, T_c) = mass_per_kw(T_c) / mass_per_kw(T_h)
                = q(T_h) / q(T_c)
                = (T_h^4 - T_s^4) / (T_c^4 - T_s^4)
                -> (T_h / T_c)^4              as T_s -> 0

so the advantage of running hot depends *only* on the two temperatures and the
sink - not on coating, material, geometry, or load. `L(533, 300) = 9.96`, the
"~10x lighter hot radiator". A warm sink *widens* the lead (subtracting the same
`T_s^4` from a larger numerator and smaller denominator raises the ratio), and
`L -> infinity` as `T_c -> T_s+` (a radiator barely above its sink rejects almost
nothing per kg).

**ISS anchor (#15).** Inverting `q` at the flight point (35 kW, 275 K, eps 0.8,
two-sided, deep-space sink): `A = 35000 / 518.9 = 67.5 m^2`, within ~4% of the
real 70.3 m^2 assembly. The one closed form reproduces flight hardware.

The test asserts: `mass_per_kw` matches the closed form to 1e-12 across a
(T, eps, mu, sides) grid; the leverage ratio is invariant to eps, mu, sides,
and load (the cancellation); the warm-sink sign and the `T_c -> T_s` divergence;
`T_s -> 0` recovers `(T_h/T_c)^4`; and the ISS closed form matches both the sim
and the 70.3 m^2 hardware to <5%.

## Basis / over-nesting notes (CLAUDE.md 1, 3)

- Per-source radiator temperature is mandatory: a ~300 K electronics radiator and a hot
  smelting radiator differ ~10x per kW, so heat must be binned by process temperature,
  not lumped at one T.
- Deep-space sink taken as ~0 K by default; a planetary-IR/albedo environment enters via
  `sink_temp_k` and the solar-load term. No heat-pipe, two-phase-loop, or CFD solver -
  these are algebraic sizings.

## Interface wiring

- **-> closure-sim:** `radiator_mass_kg` is a new BOM line - heat rejection is no longer
  free; the factory must build (or import) its radiators.
- **<- power-source / power-budget:** the heat load equals the waste power these deliver;
  `power-source` calls `thermal` to size its reactor/array radiator mass.
- **reuses probe-sim:** the 1/d^2 solar law for the parasitic-load term (single source
  of truth for the solar constant).

## Further reading (bibliography)

- **NASA STMD lightweight radiators** - the <=3 kg/m^2 target and the carbon-carbon /
  heat-pipe designs behind it.
- **ISS EATCS documentation (NASA/CBS)** - the 70 kW / 275 K / 70.3 m^2-assembly flight
  anchor that validates the Stefan-Boltzmann sizing.

## Invariants (issue #48, phase B)

`RadiatorResult` is a frozen dataclass with a `__post_init__` postcondition.
Runs in release (never gated).

- **[inv:th-radiator]** `flux_w_m2 > 0` (a radiator always radiates), `area_m2 >= 0`
  and `mass_kg >= 0` (a zero-heat call gives `area = mass = 0`; negative is a bug).

Tests: `tests/test_invariants.py`.
