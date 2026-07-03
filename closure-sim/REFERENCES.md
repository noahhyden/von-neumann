# Where the numbers come from

The point of this tool isn't precise prediction - it's to show how the *pieces fit
together*. But the inputs are picked to match real research, not invented. Here's
the grounding for each assumption, with sources, and an honest note on how solid
each one is.

## The big idea (self-replicating factories & "closure")

- **NASA CP-2255, "Advanced Automation for Space Missions" (1980)**, Ch. 5 - the
  original self-replicating lunar factory study (Freitas, von Tiesenhausen et al.).
  - Coined the **"vitamins"** framing: build 90–95% of the factory locally and ship
    the last 5–10% (mostly electronics) from Earth.
  - Estimated **90–96% mass closure** is achievable; chasing 100% isn't worth it.
  - Used a **1-year doubling time** and showed exponential growth.
  - Power: **~1.7 MW** (solar) for its 100-tonne seed (design range 0.47–11.5 MW).
  - https://www.rfreitas.com/Astro/GrowingLunarFactory1981.htm ·
    https://ntrs.nasa.gov/citations/19830007081
- **Freitas & Merkle, "Kinematic Self-Replicating Machines" (2004)** - the modern
  synthesis. Defines matter / energy / information closure and the key dynamic this
  tool models: below full closure you're stuck waiting on resupply; only near 100%
  closure does growth become self-sustaining and exponential.
  - http://www.molecularassembler.com/KSRM.htm
- **"Guided Self-Replicating Factory" (arXiv 2110.15198, 2021)** - recent revival.
  Doubling time <1 year → large colony in ~two decades; near-term realistic closure
  ~70%; chips/solar/circuitry stay Earth-sourced.
  - https://arxiv.org/abs/2110.15198

**Honesty note:** there is *no* validated modern end-to-end seed-factory design. The
1980 NASA study is still the canonical reference. Treat every number here as
"right order of magnitude," not a forecast.

## The seed factory (mass, power, build rate)

| Assumption (this tool) | Real-world grounding | How solid |
|---|---|---|
| Seed mass 7–12 t | NASA strawman was **100 t**; modern thinking favors smaller seeds | A modeling choice. Lighter than canonical - labeled as "modern/optimistic." |
| Power ~2–4 MW | NASA nominal **1.7 MW** (range 0.47–11.5 MW), solar | Matches the canon. **But** a multi-MW plant outmasses the seed - so power is treated as separate infrastructure, not part of the seed. |
| Build rate 15–20 kg/day | NASA implies **~27 kg/day** at equivalent productivity | Reasonable, slightly conservative. |
| Doubling ~1 year | NASA & the 2021 paper both use **~1 year** | Best-supported number here. |

NASA Fission Surface Power (the real near-term lunar reactor) is 40 kW under 6 t:
https://www.nasa.gov/centers-and-facilities/glenn/nasas-fission-surface-power-project-energizes-lunar-exploration/

## Energy to manufacture each part (kWh per kg)

These are the **electricity the factory spends on-site** to make 1 kg of a part.
The headline fact - chips cost thousands of kWh/kg, smelted metal costs single
digits - is what makes the electronics wall real.

| Part type (this tool) | Value used | Real range (sources below) | Verdict |
|---|---|---|---|
| Smelted/cast metal structure | 5 | 1.7–9.7 (recycled→primary steel) | OK for in-situ electric smelting |
| Thermal radiators | 3 | 1.7–5.6 (recycled metal) | OK |
| Refining-plant structure | 7 | 6–24 (steel→stainless) | Low-conservative |
| Actuators / motors | 15 | ~14–20 | Good |
| Robotic manipulators | 18 | similar to motors | Reasonable |
| Precision bearings / alloys | 35 | 20–46 (alloy/superalloy) | Good |
| Machined sensor housings | 60 | tens (small precision metal) | OK for metal only |
| **Solar arrays (silicon)** | **50** | **40–120** | Raised from a too-low 8; silicon purification dominates |
| **Power electronics / ICs** | **2,500** | **1,000–3,000** | Good |
| **Electronic sensors** | **4,000** | **2,000–8,000** | Raised from a too-low 600 |
| **Compute / logic chips** | **8,000** | **3,000–15,000** (finished, packaged) | Raised from a too-low 2,000 |

**The chip number deserves a caveat.** Embodied energy of silicon swings *enormously*
with how you measure it: ~1,800 kWh/kg for a blank wafer, ~3,000–15,000 kWh/kg for a
finished packaged chip, and 100,000+ kWh/kg if you count only the active silicon die.
We use a finished-packaged-chip basis (8,000). On any basis, chips are the most
energy-expensive thing in the factory by a wide margin.

Sources:
- Williams, Ayres & Heller, **"The 1.7 Kilogram Microchip"**, *Env. Sci. Technol.*
  2002 - inputs to make a 2 g chip outweigh it ~600×. https://pubs.acs.org/doi/10.1021/es025643o
- Nagapurkar & Das (Oak Ridge NL), IC manufacturing energy, *Sust. Mat. & Tech.*
  2022 - **9–38 MJ/cm² of wafer**. https://www.osti.gov/servlets/purl/1884036
- Metals/solar embodied energy: Inventory of Carbon & Energy (ICE) coefficients
  https://www.wgtn.ac.nz/architecture/centres/cbpr/resources/pdfs/ee-coefficients.pdf ;
  Peng et al. 2013 PV life-cycle review
  https://krichlab.ca/wp-content/uploads/2014/06/Peng2013_Review-LCA-EPBTGHG-SolarPV.pdf ;
  Marspedia embodied energy https://marspedia.org/Embodied_energy
- Power-electronics LCA (Si IGBT vs SiC): https://www.sciencedirect.com/science/article/pii/S2772370423000184
- Sensor/edge-device embodied footprint: https://arxiv.org/abs/2105.02082
- Why the chip supply chain is the deepest on Earth (400+ steps, 9N-pure materials,
  EUV monopoly): CSIS https://www.csis.org/analysis/mapping-semiconductor-supply-chain-critical-role-indo-pacific-region

## What's deliberately simplified

- **Power is flat** (doesn't grow as the factory grows) - a v1 simplification that
  makes the "energy wall" visible. A later module will let power scale.
- **One number per part type** for manufacturing energy - real LCA depends on which
  metal, recycled vs virgin, which chip node, etc. The README spells out the
  recycled-metal and packaged-chip assumptions baked in.
- **Terrestrial energy figures** are used as stand-ins; an off-world factory running
  on its own electricity would re-base some of these. Doesn't change the conclusion
  (chips ≫ metal).
