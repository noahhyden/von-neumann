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

## Open gaps

- **`[GAP]` - per-module mass breakdown.** Borgue & Hein give the six modules and the
  70/30 replicated/imported split, but not a mass fraction per module at the fidelity
  a closure computation needs. `models.py` therefore does **not** assign per-module
  masses - that is deliberately left unfilled rather than invented. To be resolved by
  reading the paper's mass tables (Table 9 and surrounding) or a defensible proxy,
  and will be tagged `[ESTIMATE]` with its reasoning when added.
