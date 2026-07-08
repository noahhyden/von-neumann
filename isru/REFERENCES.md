# Where the numbers come from

Every quantity in `isru` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: kWh/kg for specific energy, wt% for composition. This module
derives numbers `closure-sim` currently takes as hand-set inputs, so the point is to
replace assumption with sourced physics and to be explicit about the `[ESTIMATE]` seams.

## Oxygen: full-chain specific energy (well-sourced, lunar tier)

- **`OXYGEN_FULL_CHAIN_KWH_PER_KG = 24.3`, `..._UNCERTAINTY = 5.8`** - 24.3 +/- 5.8 kWh
  per kg of liquid oxygen, end-to-end from dry regolith by hydrogen reduction of
  ilmenite (10 wt% ilmenite feed). Source: Modeling energy requirements for oxygen
  production on the Moon, *PNAS* (2025), https://www.pnas.org/doi/10.1073/pnas.2306146122
  (open text: https://pmc.ncbi.nlm.nih.gov/articles/PMC11874342/ ). Verdict: sourced
  (primary, full chain - not a single reactor). This is the strongest number in the
  module: an entire production chain with a stated uncertainty band.
- **`OXYGEN_ENERGY_SHARES`** - hydrogen reduction ~55%, electrolysis ~38%, liquefaction
  ~4.8% (remaining <5% unlisted). Same PNAS source. Verdict: sourced. Confirms the
  reduction + electrolysis steps dominate.
- **Cross-check:** Taylor & Carrier (1993) put LOX production across technologies at
  **18-35 kWh/kg**; the PNAS central+band (18.5-30.1) sits inside that independent
  envelope. (Cited within the PNAS paper.)
- **`WATER_ICE_LOX_KWH_PER_KG = 11.3`** - Kornuta et al.'s water-ice electrolysis route,
  a *different* feedstock (~11.3 kWh/kg LOX), cited by the PNAS paper. Verdict: sourced.
  This is the seam to `propellant` (water-derived oxidiser); it must not be conflated
  with the regolith route (pin the basis, CLAUDE.md 1).

## Metal: molten oxide electrolysis of iron (derives closure-sim's 5.0)

- **`METAL_MOE_THEORETICAL_MIN_KWH_PER_KG = 2.6`** - thermodynamic minimum to decompose
  hematite (Fe2O3) to liquid iron + O2 at ~1600 C (~2600 kWh/tonne). Source: molten
  oxide electrolyte iron studies, https://link.springer.com/article/10.1007/s10800-017-1143-5 ;
  Stanford PH240 steel-decarbonization note, http://large.stanford.edu/courses/2024/ph240/kua1/ .
  Verdict: sourced (thermodynamic floor).
- **`METAL_MOE_PRACTICAL_KWH_PER_KG = 3.7`** - optimized industrial process (~3700
  kWh/tonne). Same sources. Verdict: sourced. `[ESTIMATE]` when applied off-Earth
  (terrestrial process as proxy for a space smelter).
- **`METAL_MOE_GLOBAL_SCALE_KWH_PER_KG = 4.0`** - global-scale steel-via-MOE estimate
  (1.84e19 J for 1.279e12 kg => ~4.0 kWh/kg). Source: IEA / Boston Metal MOE
  decarbonization presentation,
  https://iea.blob.core.windows.net/assets/imports/events/288/S5.4_20191010BostonMetalIEADecarbonization2019.pdf .
  Verdict: sourced.
- **`CLOSURE_SIM_IRON_KWH_PER_KG = 5.0`** - the value `closure-sim`'s
  `lunar_regolith_seed.yaml` hand-sets for "in-situ iron from regolith". The derived MOE
  figures (2.6-4.0) sit *below* it, so 5.0 was a reasonable, slightly conservative guess
  - now grounded. This is the number the module retires.

## Closure ceiling: lunar regolith composition

- **`LUNAR_REGOLITH_ELEMENT_WT_PCT`** - representative lunar mare-soil bulk elemental
  abundance, wt%: O 44, Si 21, Fe 13, Ca 10, Al 7, Mg 6, Ti 3, Na 0.3, Mn 0.2, Cr 0.2,
  K 0.1. Source: Lunar Sourcebook (Heiken, Vaniman & French, 1991), Apollo sample
  averages, widely reproduced (e.g. NASA lunar ISRU references). Verdict: sourced
  (canonical). Values vary mare vs highland; these are a representative mare average.
- **Volatiles (H, C, N) deliberately absent from the table:** present only as tens of
  ppm from solar-wind implantation (polar water ice aside), far below any bulk-extraction
  threshold. Their absence is the physical basis of the closure ceiling. Source: Lunar
  Sourcebook (solar-wind volatile abundances). Verdict: sourced.
- **`DEFAULT_USABLE_THRESHOLD_WT_PCT = 0.1`** - a representative bulk-extraction floor
  (elements below this cannot be a bulk local source). A documented modelling choice,
  adjustable per scenario, not a measured constant - pinned per CLAUDE.md 1.

## The derivations (shown, not assumed)

- Gaseous-vs-liquid oxygen: dropping the 4.8% liquefaction share gives 24.3 x 0.952 =
  23.1 kWh/kg gaseous - a basis a scenario may prefer.
- Closure ceiling: `ceiling = sum(mass of parts whose required elements are all present)
  / total mass`. It is the hard upper bound on closure-sim's C: `C <= ceiling`. On the
  Moon, any C/H/N-bearing part (polymers, much of the electronics) counts against it.

## `[ESTIMATE]` / `[GAP]` seams (tagged at use)

- In-situ metals beyond iron, and **all asteroid extraction**, use terrestrial
  molten-oxide-electrolysis as a proxy - `[ESTIMATE]`. Build the lunar-oxygen and lunar-
  iron tiers solid first; treat asteroid support as a tagged second tier.
- The 0.1 wt% usable threshold is a modelling choice, not a measured cut-off.

## Interface wiring

- **-> closure-sim:** `metal_energy_kwh_per_kg` supplies the per-material
  `energy_to_produce_kwh_per_kg` (retiring the 5.0 iron figure); `closure_ceiling`
  grounds the `producible_locally` boolean and caps the achievable closure ratio.
- **-> propellant (proposed):** `WATER_ICE_LOX_KWH_PER_KG` is the oxidiser-energy input
  for the water route; kept distinct from the regolith route.
- **-> power-source / power-budget:** these specific energies size the electrical load
  the power system must meet.

## Further reading (bibliography)

- **Schrenk et al. 2025** - Modeling energy requirements for oxygen production on the
  Moon, PNAS (2025), doi 10.1073/pnas.2306146122. The full-chain 24.3 +/- 5.8 kWh/kg LOX
  figure and its step-by-step energy breakdown.
- **Heiken, Vaniman & French 1991** - Lunar Sourcebook: A User's Guide to the Moon.
  Cambridge University Press. The canonical lunar regolith elemental composition and the
  ppm-level volatile abundances behind the closure ceiling.
- **Sadoway / Boston Metal (MOE)** - molten oxide electrolysis of iron: thermodynamic
  and practical specific energies grounding the ~2.6-4.0 kWh/kg metal figures.
