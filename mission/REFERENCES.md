# Where the numbers come from

`mission` introduces **no new physical quantities** - it composes four sibling
modules, and every physical number it uses is sourced in *their* REFERENCES.md files.
What lives here are (a) pointers to those sources and (b) the handful of **scenario
choices** this module makes to wire one concrete end-to-end run, each flagged as a
choice rather than a fact (CLAUDE.md §1).

## Numbers inherited from sibling modules (sourced there)

| Quantity | Value | Source (module) |
|----------|-------|-----------------|
| Factory bill of materials (masses, energies) | `lunar_regolith_seed.yaml` | closure-sim/REFERENCES.md |
| Closure ratio of that factory | ~0.9708 (derived) | closure-sim (`compute_closure`) |
| Seed mass | 12,000 kg | closure-sim scenario (`replication.seed_mass_kg`) |
| Solar constant at 1 AU | 1360.8 W/m² | probe-sim/REFERENCES.md (Kopp & Lean 2011) |
| Inverse-square irradiance, array power | S₀/d² · A · η | probe-sim/environment.py |
| Landauer floor, brain anchor, FLOPS/W conversion | k·T·ln2, 20 W / 1e18 FLOPS | power-budget/REFERENCES.md |
| Rocket equation, standard gravity | m₀/m_f = exp(Δv/vₑ), g₀ = 9.80665 | launch-economics/REFERENCES.md |
| Vitamin mass from closure | (1−C)·built_mass | launch-economics/from_closure.py |

## Scenario choices this module makes (flagged, not facts)

- **Array efficiency = 0.30** - `[ESTIMATE]`, per probe-sim/REFERENCES.md (solar-cell
  efficiency the tests use). Affects delivered power linearly.
- **Array area ≈ 9,798 m²** - *derived, not chosen at a vibe*: sized so the array
  delivers the closure scenario's ~4 MW at 1 AU with η = 0.30, i.e.
  `area = 4e6 W / (1360.8 W/m² · 0.30) ≈ 9,798 m²`. This keeps the mission consistent
  with `lunar_regolith_seed.yaml`'s `available_power_kw = 4000` while making that power
  distance-dependent (the closure scenario treated it as a fixed given).
- **Compute efficiency = 1e11 FLOPS/W (~100 GFLOP/W)** - `[ESTIMATE]`, per
  power-budget/REFERENCES.md (a scenario input until pinned to specific hardware).
  Affects the compute-headroom leg only, not whether the factory replicates.
- **Power split 70 / 20 / 10 (manufacturing / compute / housekeeping)** - a design
  **choice**, fractions of delivered power, not physics. Compute default 0.20 matches
  probe-sim's autonomy default. `PowerBudget` enforces that the fractions never
  over-allocate.
- **Δv = 9,400 m/s (Earth surface → LEO)** - representative sourced Δv-table value
  (incl. gravity + drag losses); see launch-economics/REFERENCES.md. Used only for the
  illustrative propellant-fraction figure, not for the $ cost.
- **Isp = 311 s (LOX/RP-1, Merlin 1D vacuum)** - sourced input, launch-economics/REFERENCES.md.
- **$/kg = 3,000 (Falcon 9 reusable to LEO)** - sourced list-price ballpark,
  launch-economics/REFERENCES.md.
- **Target installed mass = 1,000,000 kg** - a scenario **design choice**: grow a
  ~12 t seed into a ~1000 t installation (leverage ≈ 24.5 at this closure). Not a
  physical constant; documented as the "how big do we want the factory" knob.

## Open gap

- **`[GAP]` - probe-specific bill of materials.** There is no sourced per-module mass
  breakdown for the Borgue & Hein (2020) probe (the same `[GAP]` recorded in
  probe-sim/REFERENCES.md). The mission therefore uses closure-sim's lunar-regolith
  seed factory as a **stand-in** for the probe's factory: a real, sourced BOM, but not
  probe-specific. No masses are invented to close this gap; when the paper's Table 9
  (or a defensible proxy) is transcribed and tagged `[ESTIMATE]`, the mission can swap
  in a probe-specific `Factory` with no code change.

## Further reading and cross-checks (bibliography)

Sources that ground this module's ideas or cross-check its numbers, consolidated in the project bibliography (frontend/src/sources.ts) and shown on the site's Sources page. These add context; they are not new numbers in the code.

- **Metzger et al. 2013** - P. T. Metzger, A. Muscatello, R. P. Mueller & J. Mantovani (2013). Affordable, Rapid Bootstrapping of the Space Industry and Solar System Civilization (arXiv:1612.03238). Journal of Aerospace Engineering 26(1):18-29, DOI 10.1061/(ASCE)AS.1943-5525.0000236. https://arxiv.org/abs/1612.03238. The modern quantitative counterpart to NASA CP-2255: ~12 t of landed hardware bootstrapping to 156-40,000 t of industrial assets over ~20 years via robotics and additive manufacturing, starting sub-replicating (teleoperated, importing vitamins) and spiralling toward autonomy, with electronics staying Earth-sourced. Grounds the seed-mass, doubling-time, and partial-closure-then-grow dynamics.
- **Sutton & Biblarz 2016** - G. P. Sutton & O. Biblarz (2016). Rocket Propulsion Elements (9th ed.). Wiley, ISBN 978-1-118-75365-1. https://www.wiley.com/en-us/Rocket+Propulsion+Elements,+9th+Edition-p-9781118753651. The standard text behind the rocket equation and the chemical specific-impulse ranges the scenarios use (LOX/RP-1 ~280-340 s, LOX/LH2 ~450 s). Pins the previously bundled Sutton & Biblarz mention to a specific edition.
- **Curtis 2020** - H. D. Curtis (2020). Orbital Mechanics for Engineering Students (4th ed.). Butterworth-Heinemann (Elsevier), ISBN 978-0-12-824025-0. https://shop.elsevier.com/books/orbital-mechanics-for-engineering-students/curtis/978-0-12-824025-0. Grounds the rocket-equation derivation and the representative delta-v budgets (surface-to-LEO ~9.3-10 km/s, LEO-to-TLI ~3.1 km/s, LEO-to-Mars ~3.6 km/s) that drive the mass-ratio computation.
- **ASTM E490** - ASTM International (Subcommittee E21.04) (2019). Standard Solar Constant and Zero Air Mass Solar Spectral Irradiance Tables (E490-00a(2019)). ASTM International standard. https://www.astm.org/e0490-00ar19.html. The aerospace-community AM0 reference: the extraterrestrial solar constant (1366.1 W/m2) and the full solar spectrum at 1 AU. The standards-body cross-check on the 1-AU irradiance (complementing Kopp & Lean's measured 1360.8) and it fixes the spectrum a space solar cell actually converts.
