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
- **M. V. Shubov, "Guided Self-Replicating Factory for Colonization of Solar System"
  (arXiv 2110.15198, 2021)** - recent revival. Doubling time <1 year → large colony
  in ~two decades; near-term realistic closure ~70%; chips/solar/circuitry stay
  Earth-sourced.
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

**Paper figures (`src/closure_sim/paper_figures.py`, for `papers/electronics-wall/`).**
The three figures in the electronics-wall paper restate this module's deterministic output
and pure derivations; no new numbers. `fig_leverage.pdf` plots `1/(1-C)` (mass balance),
marked at `C=0.67 -> 3.0x` and `C=0.97 -> 33.3x`. `fig_embodied_energy.pdf` plots the
per-subsystem `energy_to_produce_kwh_per_kg` values in the table above, read from the
loaded factory. `fig_chip_crossover.pdf` sweeps `electronics_wall(...)` over available
power for the lunar seed (closure 97.08%): importing chips is resupply-limited at ~28.8 yr
(10,512 d), making them locally is energy-limited at ~17.4 yr (6,350 d) at 4 MW and never
completes near 1 MW. Regenerate via `uv run --extra dev python -m closure_sim.paper_figures`
(days converted at 365.25 d/yr).

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
- Pirson & Bol, "Assessing the embodied carbon footprint of IoT edge devices with a
  bottom-up life-cycle approach" (arXiv 2105.02082, 2021) - sensor/edge-device
  embodied footprint: https://arxiv.org/abs/2105.02082
- Why the chip supply chain is the deepest on Earth (400+ steps, 9N-pure materials,
  EUV monopoly): CSIS https://www.csis.org/analysis/mapping-semiconductor-supply-chain-critical-role-indo-pacific-region

## UQ distributions (issue #35)

Every entry in the per-part energy table now has a companion `Uniform(low, high)`
distribution in `src/closure_sim/distributions.py` (`PART_ENERGY_KWH_PER_KG_DIST`),
using the LCA min-max endpoints exactly as reported in the table above. The
sintered-regolith strength range - explicitly labelled here as "carry as a band,
never a point" (>100x span across techniques) - lands as `LogUniform(2.49, 355.0)`
so each order of magnitude is equally likely, matching how the source presents the
choice of technique rather than the linear numeric distance.

A first UQ finding surfaced by MC + Sobol over the per-part bands: for the ratio
leverage = chip_kWh_per_kg / metal_kWh_per_kg (the electronics-wall driver),
**metal energy dominates the Sobol total-order ranking**, not chip energy - the
small denominator amplifies proportionally-small changes into larger changes in
the ratio than the wide chip numerator does. This is exactly the "which input
actually drives this finding" attribution issue #35 asks the papers to report.

## Structural strength (the `structures` decision - `structures.py`)

`ROADMAP-PROPOSAL.md` weighed making `structures` its own module vs a parameter here. The
default was to demote it to a mass-penalty parameter unless the k=1.0 regression showed
the physics moved real closure numbers. It was demoted; `structures.py` is that parameter.

- **Sintered lunar-regolith compressive strength: ~2.49-355 MPa, a >100x span by
  technique.** `SINTERED_REGOLITH_STRENGTH_MPA` (representative points): solar-3D/PBF
  ~4.2 MPa, microwave-sintered ~37 MPa (KLS-1), sintered ~98 MPa (air) / ~152 MPa
  (vacuum), dense traditional ~232 MPa, glass-ceramic (800 C) ~355 MPa. Sources: "Solar
  3D printing of lunar regolith", Acta Astronautica 152:800 (2018),
  https://www.sciencedirect.com/science/article/pii/S0094576518303874 ; microwave
  sintering of KLS-1, https://www.researchgate.net/publication/351670581 ; glass-ceramic
  from regolith simulant,
  https://www.sciencedirect.com/science/article/abs/pii/S0022309326000517 . Verdict:
  sourced; carried as a band, never a point (the >100x span is the whole reason strength
  can't be a single number).
- **Mass penalty** `k = required_strength / material_strength` (clamped >= 1): a weaker
  material needs a heavier part for the same load. **Derived, shown.**

### Why it stays a parameter, not a module (the decision)

- **k = 1.0 reproduces closure exactly** (regression test): with no penalty,
  `closure_with_structural_penalty` returns `compute_closure`'s ratio bit-for-bit.
- **A mass penalty raises closure, it does not lower it.** Heavier local structure is
  still *local* mass against fixed imports, so weak material costs *throughput and energy*
  (more mass to build), not closure. A realistic k (microwave regolith, ~1.08) moves
  closure <1 point.
- **Only a hard strength threshold moves closure** - a part that cannot meet a
  non-scalable requirement flips to an import (vitamin), which closure-sim already models
  via `producible_locally`. So the strength physics needs no new module: the mass penalty
  is a parameter, and the threshold is the existing boolean. That is the recorded verdict.

## What's deliberately simplified

- **Power is flat** (doesn't grow as the factory grows) - a v1 simplification that
  makes the "energy wall" visible. A later module will let power scale.
- **One number per part type** for manufacturing energy - real LCA depends on which
  metal, recycled vs virgin, which chip node, etc. The README spells out the
  recycled-metal and packaged-chip assumptions baked in.
- **Terrestrial energy figures** are used as stand-ins; an off-world factory running
  on its own electricity would re-base some of these. Doesn't change the conclusion
  (chips ≫ metal).

## Further reading and cross-checks (bibliography)

Sources that ground this module's ideas or cross-check its numbers, consolidated in the project bibliography (frontend/src/sources.ts) and shown on the site's Sources page. These add context; they are not new numbers in the code.

- **Metzger et al. 2013** - P. T. Metzger, A. Muscatello, R. P. Mueller & J. Mantovani (2013). Affordable, Rapid Bootstrapping of the Space Industry and Solar System Civilization (arXiv:1612.03238). Journal of Aerospace Engineering 26(1):18-29, DOI 10.1061/(ASCE)AS.1943-5525.0000236. https://arxiv.org/abs/1612.03238. The modern quantitative counterpart to NASA CP-2255: ~12 t of landed hardware bootstrapping to 156-40,000 t of industrial assets over ~20 years via robotics and additive manufacturing, starting sub-replicating (teleoperated, importing vitamins) and spiralling toward autonomy, with electronics staying Earth-sourced. Grounds the seed-mass, doubling-time, and partial-closure-then-grow dynamics.
- **Jones et al. 2011 (RepRap)** - R. Jones, P. Haufe, E. Sells, P. Iravani, V. Olliver, C. Palmer & A. Bowyer (2011). RepRap - the Replicating Rapid Prototyper. Robotica 29(1):177-191, DOI 10.1017/S026357471000069X. https://www.cambridge.org/core/journals/robotica/article/reprap-the-replicating-rapid-prototyper/5979FD7B0C066CBCE43EEAD869E871AA. The best real-world data point on partial self-replication: an open-source 3D printer that prints a large fraction of its own parts but not motors, electronics, or rods, with measured reproductive spread. A terrestrial echo of the electronics wall - a machine can close on structure but must import the high-tech vitamins.
- **Boyd 2012** - S. B. Boyd (2012). Life-Cycle Assessment of Semiconductors. Springer (from the 2009 Stanford PhD dissertation), DOI 10.1007/978-1-4419-9988-7. https://escholarship.org/uc/item/8bv2s63d. The most complete transparent process-level LCA of CMOS logic, DRAM, and flash across seven technology generations - the strongest independent anchor for the finished-chip embodied-energy figure behind the 8,000 kWh/kg headline, and how it moves with node and yield.
- **Gutowski et al. 2009** - T. G. Gutowski, M. S. Branham, J. B. Dahmus, A. J. Jones & D. P. Sekulic (2009). Thermodynamic Analysis of Resources Used in Manufacturing Processes. Environmental Science & Technology 43(5):1584-1590, DOI 10.1021/es8016655. https://doi.org/10.1021/es8016655. Across 20 processes, electricity used per kg of material rises by orders of magnitude from conventional metal shaping (casting, machining) to vapor-phase semiconductor processes - the exergy-based, physics-grounded basis for the central claim that chips cost roughly 1,000x more energy per kg than smelted metal.
- **Murphy et al. 2003** - C. F. Murphy, G. A. Kenig, D. T. Allen, J.-P. Laurent & D. E. Dyer (2003). Development of Parametric Material, Energy, and Emission Inventories for Wafer Fabrication in the Semiconductor Industry. Environmental Science & Technology 37(23):5373-5382, DOI 10.1021/es034434g. https://doi.org/10.1021/es034434g. A bottom-up per-wafer energy and materials inventory for the fab itself - grounds the blank-wafer basis end of the chip energy range (about 1,800 kWh/kg for a bare wafer vs. thousands for a packaged part), and documents why the measurement basis you pick swings the number.
- **Ashby 2012** - M. F. Ashby (2012). Materials and the Environment: Eco-informed Material Choice (2nd ed.). Butterworth-Heinemann / Elsevier, ISBN 978-0-12-385971-6. https://shop.elsevier.com/books/materials-and-the-environment/ashby/978-0-12-385971-6. Standard-reference embodied-energy and carbon datasheets for common materials - grounds the cheap-to-make structural end of the per-part table (metals at single-digit to tens of kWh/kg) and is an independent cross-check on the ICE coefficients already cited.
- **Guerrero-Gonzalez & Zabel 2023** - F. J. Guerrero-Gonzalez & P. Zabel (2023). System analysis of an ISRU production plant: Extraction of metals and oxygen from lunar regolith. Acta Astronautica 203:187-201, DOI 10.1016/j.actaastro.2022.11.050. https://ui.adsabs.harvard.edu/abs/2023AcAau.203..187G/abstract. Detailed off-world energy and hardware budgets for molten regolith electrolysis and FFC-Cambridge processing (e.g. a ~6,776 kg plant making 25 t/yr ferrosilicon plus oxygen). Directly addresses the open caveat that the project uses terrestrial smelting energy as a stand-in - this gives the actual in-situ kWh/kg for making structural metal on the Moon.
- **von Neumann & Burks 1966** - J. von Neumann; ed. A. W. Burks (1966). Theory of Self-Reproducing Automata. University of Illinois Press, Urbana. https://archive.org/details/theoryofselfrepr00vonn_0. The origin of the idea: von Neumann's universal constructor proved a machine can build a copy of itself if it carries both a construction description and a way to copy that description - the information-closure half of the matter / energy / information framing every seed-factory claim rests on.
- **Chirikjian 2004 (NIAC)** - G. S. Chirikjian (2004). An Architecture for Self-Replicating Lunar Factories. NASA Institute for Advanced Concepts (NIAC) Phase I Final Report, study 880. https://www.niac.usra.edu/files/studies/final_report/880Chirikjian.pdf. A concrete subsystem architecture for exactly the object closure-sim models: a lunar factory that mines regolith, refines materials, and assembles copies of itself, decomposed into robots, refining, parts fabrication, and assembly. Grounds the what-must-a-real-factory-be-made-of breakdown and the teleoperation-to-autonomy path.
- **Moses & Chirikjian 2020** - M. S. Moses & G. S. Chirikjian (2020). Robotic Self-Replication. Annual Review of Control, Robotics, and Autonomous Systems 3:1-24, DOI 10.1146/annurev-control-071819-010010. https://www.annualreviews.org/content/journals/10.1146/annurev-control-071819-010010. The modern survey tying the strands together: the principles required to make self-replicating robots from raw materials, the role of 3D printing, and the key distinction between closure of parts and closure of the fabrication processes that make them.
- **Sagan & Newman 1983** - C. Sagan & W. I. Newman (1983). The Solipsist Approach to Extraterrestrial Intelligence. Quarterly Journal of the Royal Astronomical Society 24:113-121. https://ui.adsabs.harvard.edu/abs/1983QJRAS..24..113S/abstract. The canonical rebuttal to Tipler: self-replicating probes are inherently dangerous and hard to control (an unchecked replicator would consume the galaxy's mass), so a civilization would avoid or destroy them. Grounds the control / containment concerns and the sensitivity of outcomes to replication rate.
- **Zykov et al. 2005** - V. Zykov, E. Mytilinaios, B. Adams & H. Lipson (2005). Robotics: Self-Reproducing Machines. Nature 435(7039):163-164, DOI 10.1038/435163a. https://www.nature.com/articles/435163a. A physical demonstration that mechanical self-reproduction is real, not just theory: modular molecube robots that pick up identical cubes from feeding stations and assemble a working copy. Grounds the plausibility of physical (not just computational) self-replication and the identical-modules-plus-feedstock model of closure.
- **Kuehr & Williams 2003** - R. Kuehr & E. Williams (eds.) (2003). Computers and the Environment: Understanding and Managing their Impacts. Kluwer / Springer, Eco-Efficiency in Industry and Science vol. 14, DOI 10.1007/978-94-010-0033-8. https://doi.org/10.1007/978-94-010-0033-8. Established the material-intensity-of-computing case (a desktop PC takes on the order of 240 kg of fossil fuel, 22 kg of chemicals, and 1,500 kg of water to make) - the broader-context companion to Williams' 1.7 Kilogram Microchip, reinforcing why electronics are the hard-to-close vitamins.
- **Elvis 2014** - M. Elvis (2014). How Many Ore-Bearing Asteroids? (arXiv:1312.4450). Planetary and Space Science 91:20-26. https://arxiv.org/abs/1312.4450. The scarcity of minable feedstock: only about 1 in 2000 accessible near-Earth asteroids is platinum-group ore-bearing and ~1 in 1100 is water-ore-bearing. Grounds the resource-availability assumption behind a probe or seed factory that must harvest local material rather than assume any asteroid will do.
- **DeMeo & Carry 2014** - F. E. DeMeo & B. Carry (2014). Solar System evolution from compositional mapping of the asteroid belt. Nature 505:629-634, DOI 10.1038/nature12908. https://doi.org/10.1038/nature12908. The composition of the asteroid feedstock by taxonomic class and how it is distributed by mass and heliocentric distance. Grounds what a resource-harvesting module can expect to find where - which raw materials are actually available at a given mining destination.
- **Lunar Sourcebook** - G. H. Heiken, D. T. Vaniman & B. M. French (eds.) (1991). Lunar Sourcebook: A User's Guide to the Moon. Cambridge University Press (full text hosted by LPI/USRA). https://www.lpi.usra.edu/publications/books/lunar_sourcebook/. The definitive reference on lunar regolith and rock composition, mineralogy, and physical properties - the feedstock inventory for a factory that lands on the Moon and builds from local material. Grounds which elements (O, Si, Al, Fe, Ti, Mg) are locally available and in what abundance.
- **Hoffman et al. 2022 (MOXIE)** - J. A. Hoffman, M. H. Hecht, D. Rapp et al. (2022). Mars Oxygen ISRU Experiment (MOXIE) - Preparing for human Mars exploration. Science Advances 8(35), eabp8636, DOI 10.1126/sciadv.abp8636. https://www.science.org/doi/10.1126/sciadv.abp8636. The first demonstrated in-situ resource utilization on another planet: solid-oxide electrolysis of Martian CO2 producing ~6 g O2/hr on Perseverance. Grounds the Mars-destination ISRU case - a probe can make consumables from the local atmosphere rather than importing them.
