# Where the numbers come from

Every quantity in `probe-sim` traces to a source below, or is derived by explicit
math from ones that do. Units are explicit throughout.

## The probe concept

- **Borgue, O. & Hein, A. M. (2020), "Near-Term Self-replicating Probes - A Concept
  Design."** arXiv:[2005.12303](https://arxiv.org/abs/2005.12303); published in
  *Acta Astronautica* 187 (2021) 546–556, DOI
  [10.1016/j.actaastro.2021.03.004](https://doi.org/10.1016/j.actaastro.2021.03.004).
  - **Six modules** (`ProbeModule`): "power generation, resource harvesting,
    replication, propulsion, control, and telemetry, tracking, command and
    instrument module." Verbatim mapping - solid.
  - **`REPLICATED_MASS_FRACTION = 0.70`**: the probe "replicat[es] 70% of its mass";
    the non-replicated ~30% is microchips and complex electronics carried along
    (closure-sim's "vitamins" framing). Solid.
  - **< 100 kg, CubeSat-module scale**: small-satellite-scale, assembled from
    CubeSat form-factor units (3U/6U/18U). Solid (used as a bound, not a point mass).
  - **Solar-flux range gating**: "solar radiation decreases from 1,374 Watts/m²
    around Earth, to 50 Watts/m² near Jupiter … the overall mission is constrained
    to be performed inside the solar system." This is the mechanism `environment.py`
    models. Solid for *range*; the paper does **not** tie replication *rate* to flux,
    so we do not either.

## Solar environment

- **`SOLAR_CONSTANT_1AU_W_M2 = 1360.8` W/m²** - Total Solar Irradiance at 1 AU.
  Kopp, G. & Lean, J. L. (2011), "A new, lower value of total solar irradiance,"
  *Geophys. Res. Lett.* 38, L01706, DOI
  [10.1029/2010GL045777](https://doi.org/10.1029/2010GL045777). Value 1360.8 ± 0.5.
  - *Reasonable?* Yes - this is the accepted modern TSI. Borgue & Hein's 1374 is an
    older/AM0-style figure; the ~1% difference does not change any conclusion. We use
    the measured TSI and derive the rest.
  - **UQ distribution (issue #35): Normal(mean=1360.8, std=0.5) W/m²**, exported as
    `SOLAR_CONSTANT_1AU_W_M2_STD = 0.5` alongside the point value. The +/- 0.5 is
    Kopp & Lean's own reported uncertainty on the measurement, so the spread cites
    the same source as the mean (CLAUDE.md §1: a spread is a citable claim in its
    own right). Solid.
- **Inverse-square law**, `S(d) = S0 / d²` - first principles (flux through a sphere
  of radius d). Deriving from it: at Jupiter's 5.203 AU, `1360.8 / 5.203² = 50.3
  W/m²`, which matches Borgue & Hein's "~50 W/m² near Jupiter" - an independent check
  that the constant and law agree with the source.
- **`AU_DISTANCE`** (mean heliocentric distance, AU): earth 1.000, mars 1.524,
  jupiter 5.203 - NASA Planetary Fact Sheet,
  https://nssdc.gsfc.nasa.gov/planetary/factsheet/ . Solid.
- **Solar-cell efficiency** - a per-scenario input on `SolarArray`, not a hardcoded
  constant. Representative space multi-junction cells are ~28–32% (e.g. Spectrolab
  XTJ ~30% AM0); tests use 0.30 as a stand-in input. When a real scenario fixes a
  value it must cite the specific cell. `[ESTIMATE]` until a scenario pins one.
  - **UQ distribution (issue #35): Uniform(low=0.28, high=0.32).** The range is
    Landis & Bailey (2002) space-multi-junction performance, treated as a uniform
    over the reported band since the source gives an interval, not a shape. The
    UQ end-to-end script (`scripts/uq_probe_range.py`) uses this as its dominant
    input, and Sobol confirms it drives >0.95 of the variance in the max-reach
    finding. `[ESTIMATE]` remains until a specific cell is chosen for a scenario;
    the distribution then narrows to that cell's manufacturer datasheet range.

## Open gaps

- **`[GAP]` - per-module mass breakdown.** Borgue & Hein give the six modules and the
  70/30 replicated/imported split, but not a mass fraction per module at the fidelity
  a closure computation needs. `models.py` therefore does **not** assign per-module
  masses - that is deliberately left unfilled rather than invented. To be resolved by
  reading the paper's mass tables (Table 9 and surrounding) or a defensible proxy,
  and will be tagged `[ESTIMATE]` with its reasoning when added.

## Further reading and cross-checks (bibliography)

Sources that ground this module's ideas or cross-check its numbers, consolidated in the project bibliography (frontend/src/sources.ts) and shown on the site's Sources page. These add context; they are not new numbers in the code.

- **ASTM E490** - ASTM International (Subcommittee E21.04) (2019). Standard Solar Constant and Zero Air Mass Solar Spectral Irradiance Tables (E490-00a(2019)). ASTM International standard. https://www.astm.org/e0490-00ar19.html. The aerospace-community AM0 reference: the extraterrestrial solar constant (1366.1 W/m2) and the full solar spectrum at 1 AU. The standards-body cross-check on the 1-AU irradiance (complementing Kopp & Lean's measured 1360.8) and it fixes the spectrum a space solar cell actually converts.
- **Juno solar-power record (JPL)** - NASA Jet Propulsion Laboratory (2016). NASA's Juno Spacecraft Breaks Solar Power Distance Record. NASA / JPL news release. https://www.jpl.nasa.gov/news/nasas-juno-spacecraft-breaks-solar-power-distance-record/. The real deep-space anchor for the 1/d^2 range gate: Juno's ~50 m2 of cells make ~14 kW at 1 AU but only ~500 W at Jupiter (~5.2 AU). A flown validation that the inverse-square falloff and the outer-system power limit in probe-sim match a real solar-powered mission.
- **Landis & Bailey 2002** - G. A. Landis & S. G. Bailey (NASA Glenn Research Center) (2002). Photovoltaic Power for Future NASA Missions (AIAA-2002-0718). AIAA 40th Aerospace Sciences Meeting; NASA NTRS 20030006444. https://ntrs.nasa.gov/citations/20030006444. Space multi-junction cell performance vs distance and temperature: triple-junction GaInP/GaAs/Ge cells at ~27% AM0, and the low-intensity / low-temperature behaviour far from the Sun. Grounds probe-sim's solar-array efficiency input (currently an [ESTIMATE] at 0.30).
- **NASA MEM 3** - A. Moorhead et al. (NASA Meteoroid Environment Office) (2020). NASA Meteoroid Engineering Model (MEM) Version 3. NASA/TM-2020-220555; NTRS 20200000563. https://ntrs.nasa.gov/citations/20200000563. NASA's standard model of the sporadic meteoroid / micrometeoroid flux for Earth orbit, lunar orbit, and interplanetary space. Grounds the real-world-messiness hazard a long-lived probe or factory faces (impact-driven degradation and array wear) - a noise parameter, not the frictionless ideal.
