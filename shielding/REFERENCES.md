# Where the numbers come from

Every quantity in `shielding` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: g/cm^2 (areal density), cm, kg, rad(Si) (TID), mSv (dose-
equivalent). The shared radiation-environment numbers live in `radenv.py` and are
consumed by both this module and `reliability`.

## Two dose bases, kept distinct (pinned, CLAUDE.md 1)

- **TID for electronics** in rad(Si)/krad(Si) - total ionising dose that degrades chips.
- **Dose-equivalent for biology/risk** in mSv - GCR dose weighted by radiation quality.

These are different physical quantities on different scales and are never mixed.

## Radiation environment (radenv.py, sourced)

- **`GCR_DEEP_SPACE_DOSE_MSV_PER_DAY = 1.8`** - Mars Science Laboratory RAD measured
  ~1.8 mSv/day during cruise. Source: Zeitlin et al. (2013), *Science* 340:1080,
  "Measurements of Energetic Particle Radiation in Transit to Mars on the MSL", https://doi.org/10.1126/science.1235989 .
  Verdict: sourced (flight-measured).
- **`GCR_DOSE_MIN_AREAL_DENSITY_G_CM2 = 20`** - aluminium areal density at which GCR
  dose-EQUIVALENT is minimised; beyond it neutron/secondary build-up increases dose
  (thicker is worse). Source: "Optimal shielding thickness for galactic cosmic ray
  environments", Life Sciences in Space Research (2017), https://pubmed.ncbi.nlm.nih.gov/28212703/ ;
  NASA GCR shielding, https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/19980006777.pdf .
  Verdict: sourced (the module's most important qualitative fact).
- **`JUNO_ANTICIPATED_TID_RAD = 2.0e7`** (20 Mrad) and **`JUNO_VAULT_ATTENUATION_FACTOR =
  800`** - Juno's anticipated mission dose and the vault's ~800x reduction. Source:
  https://en.wikipedia.org/wiki/Juno_Radiation_Vault ; JPL,
  https://www.jpl.nasa.gov/news/juno-armored-up-to-go-to-jupiter/ . Verdict: sourced.
- **Material densities** (g/cm^3): titanium 4.51, aluminium 2.70, lunar regolith ~1.6
  (bulk). Sources: standard material data; Lunar Sourcebook (regolith bulk density
  ~1.5-1.9). Verdict: sourced.
- **Vault masses:** Juno **200 kg** (1 cm titanium walls, ~1 m^2/side), Europa Clipper
  **150 kg** (titanium/zinc/aluminium composite). Sources: Juno Radiation Vault (above);
  Europa Clipper, https://en.wikipedia.org/wiki/Europa_Clipper . Verdict: sourced.

## Derivations (shown, validated in tests)

- **Areal density -> mass:** 1 g/cm^2 over 1 m^2 (10^4 cm^2) = 10 kg. Juno's 1 cm Ti
  (4.51 g/cm^2) over ~4.4 m^2 of wall reproduces its ~200 kg vault; a full 6-face 1 m^2
  cube is ~270 kg (same order). Cross-check of the conversion against flight hardware.
- **TID attenuation length (`[ESTIMATE]`):** modelling TID as `exp(-sigma/lambda)`,
  Juno's 4.51 g/cm^2 giving 800x fixes `lambda = 4.51 / ln(800) = 0.675 g/cm^2`. A
  single-point exponential fit to the Jovian electron spectrum - tagged `[ESTIMATE]`, not
  a measured attenuation coefficient. A different environment needs its own lambda.
- **Regolith substitution (`[ESTIMATE]`):** areal density is the first-order driver of
  attenuation, so regolith at the same g/cm^2 substitutes for metal (1 cm Ti ~ 2.82 cm
  regolith). Ignores material-dependent secondary production - hence `[ESTIMATE]`; the
  substitution *verdict* (cheap COTS behind thick regolith vs imported rad-hardness) is
  derived from it.

## `[ESTIMATE]` seams (tagged at use)

- The Jovian TID attenuation length is a single-point fit (above).
- Regolith-vs-metal equivalence uses areal density as a proxy and ignores Z-dependent
  secondary yields; the GCR minimum is quoted for aluminium and used as a regolith proxy.

## GCR non-monotonicity (the anti-nonsense guard)

`gcr_shielding_is_counterproductive` and `recommend_gcr_areal_density` enforce the
20 g/cm^2 minimum: the module will not recommend thicker GCR shielding, because past the
minimum it raises dose. Without this guard a naive "more shielding is safer" model would
produce confident nonsense - the exact failure CLAUDE.md warns about.

## Interface wiring

- **-> closure-sim:** `shield_mass_kg` is a BOM line, but `closure_contribution_kg` marks
  locally-built regolith shielding as mass that RAISES closure (opposite of vitamins).
- **shares radenv with reliability:** `reliability` consumes the same GCR/Jovian dose
  numbers for degradation/mortality, so they are defined once here.
- **<- power-source / mission:** the environment (distance, Jovian vs interplanetary)
  selects which dose numbers apply.

## Further reading (bibliography)

- **Zeitlin et al. 2013** - MSL/RAD transit dose measurements; the 1.8 mSv/day deep-space
  GCR anchor.
- **Slaba et al. / "Optimal shielding thickness for GCR" 2017** - the ~20 g/cm^2 dose-
  equivalent minimum and the secondary-particle build-up beyond it.
- **Juno Radiation Vault / Europa Clipper** - the flight vault masses and attenuation
  anchors.
