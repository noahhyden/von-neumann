# Where the numbers come from

Every quantity in `power-budget` traces to a source below, or is derived by explicit
math from ones that do. Units: energy in joules, power in watts, temperature in kelvin.

## Physics constants

- **`BOLTZMANN_J_PER_K = 1.380649e-23` J/K** - the Boltzmann constant, *exact* by the
  2019 SI redefinition. BIPM SI brochure / CODATA. Solid (definitional).
- **Landauer limit**, `E = k_B · T · ln2` - Landauer, R. (1961), "Irreversibility and
  heat generation in the computing process," *IBM J. Res. Dev.* 5(3):183–191, DOI
  [10.1147/rd.53.0183](https://doi.org/10.1147/rd.53.0183). Derived, not hardcoded:
  at 300 K, `1.380649e-23 · 300 · ln2 = 2.871e-21 J/bit`, giving a ceiling of
  `1 / 2.871e-21 = 3.48e20` irreversible bit-operations per joule. Solid (first
  principles + measured constant). Experimentally approached: Bérut et al. (2012),
  *Nature* 483:187–189.
  - **Reference temperature = 300 K** (the default in `landauer_limit_j_per_bit` /
    `max_bit_operations_per_joule`) is a documented **choice** - ≈ room temperature, the
    conventional basis for quoting the Landauer floor. Any radiator temperature can be
    passed; the floor scales linearly with T.

## Scale anchors

- **`HUMAN_BRAIN_POWER_W = 20.0` W** - resting human brain power. Raichle, M. E. &
  Gusnard, D. A. (2002), "Appraising the brain's energy budget," *PNAS*
  99(16):10237–10239, DOI [10.1073/pnas.172399499](https://doi.org/10.1073/pnas.172399499)
  (the brain is ~20% of ~100 W resting metabolism). Solid.
- **`BRAIN_COMPUTE_FLOPS_ESTIMATE = 1e18` FLOPS** - `[ESTIMATE]`. Brain-equivalent
  compute is deeply uncertain; published estimates span ~1e15 to ~1e20 FLOPS. We take
  1e18 as an order-of-magnitude midpoint from Sandberg, A. & Bostrom, N. (2008),
  "Whole Brain Emulation: A Roadmap," FHI Technical Report 2008-3. **Uncertainty: ~±2
  orders of magnitude.** Used only as a scale marker for `brain_equivalents()`, never
  as a precise ratio.

## UQ distributions (issue #35)

`src/power_budget/distributions.py` gives each number above a citable companion:

- `BOLTZMANN_DIST = Fixed(1.380649e-23)`, `REFERENCE_TEMPERATURE_K_DIST = Fixed(300.0)` -
  definitional / documented choice, respectively; `Fixed` is correct, not a `[GAP]`.
- `HUMAN_BRAIN_POWER_DIST = Uniform(15, 25) W` - the ~20 W resting figure sits inside
  the broader task-dependent 15-25 W band recorded in the literature.
- `BRAIN_COMPUTE_FLOPS_DIST = LogUniform(1e15, 1e20)` - directly reads the "estimates
  span 1e15 to 1e20; uncertainty ~+/- 2 orders of magnitude" annotation on
  `BRAIN_COMPUTE_FLOPS_ESTIMATE`. Each order of magnitude equally likely, matching how
  the source presents the uncertainty.
- `COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST = LogUniform(1e10, 1e12)` - H100-class hardware
  centred around 1e11 FLOPS/W; the LogUniform band covers the Koomey-trend spread.
  Scenarios that pin a specific device should narrow this.

A first UQ finding: brain-equivalents of a 1e18 FLOPS compute budget spans **more than
three orders of magnitude** at 90% CI, dominated by the brain-FLOPS estimate rather
than the compute-side spread - so any "we hit a brain" claim without stating which
brain-FLOPS number was used is under-specified.

## Per-scenario inputs (not constants)

- **Compute efficiency (FLOPS/W)** - an input to `compute_capacity_flops`, not a
  hardcoded value, because it moves with hardware and precision. Representative
  present-day accelerators are ~1e11 FLOPS/W (e.g. an NVIDIA H100 at ~60 TFLOPS FP64 /
  ~700 W ≈ 8.6e10 FLOPS/W); the Landauer floor above is the hard physical ceiling.
  A scenario that fixes a value must cite the specific device. `[ESTIMATE]` until pinned.
- **Allocation fractions** (manufacturing / compute / housekeeping) - scenario design
  choices, not physical facts; a real scenario should justify them against a mission.

## Further reading and cross-checks (bibliography)

Sources that ground this module's ideas or cross-check its numbers, consolidated in the project bibliography (frontend/src/sources.ts) and shown on the site's Sources page. These add context; they are not new numbers in the code.

- **Lloyd 2000** - S. Lloyd (2000). Ultimate physical limits to computation. Nature 406:1047-1054, DOI 10.1038/35023282. https://doi.org/10.1038/35023282. Extends the Landauer floor into the full physical ceiling on computation: operations-per-second bounded by available energy, memory by degrees of freedom. Grounds the hard-physical-ceiling framing beyond the per-bit erasure cost.
- **Koomey et al. 2011** - J. G. Koomey, S. Berard, M. Sanchez & H. Wong (2011). Implications of Historical Trends in the Electrical Efficiency of Computing. IEEE Annals of the History of Computing 33(3):46-54, DOI 10.1109/MAHC.2010.28. https://doi.org/10.1109/MAHC.2010.28. Koomey's law: computations per joule doubled roughly every 1.6 years for six decades. Grounds the compute-efficiency (FLOPS/W) input as a historically-quantified moving figure and sizes the gap between present hardware and the Landauer ceiling.
- **Bennett 1982** - C. H. Bennett (1982). The Thermodynamics of Computation - a Review. International Journal of Theoretical Physics 21(12):905-940, DOI 10.1007/BF02084158. https://doi.org/10.1007/BF02084158. Establishes that only logically irreversible operations (bit erasure) must dissipate kT ln2, while reversible computation can in principle dodge the floor. Grounds why compute is floored at the Landauer limit for irreversible bit-operations specifically, not for computation in general.
- **Markov 2014** - I. L. Markov (2014). Limits on fundamental limits to computation (arXiv:1408.3821). Nature 512:147-154, DOI 10.1038/nature13570. https://doi.org/10.1038/nature13570. A critical survey separating firm limits (energy, thermodynamics) from soft ones and showing which have been engineered around. Grounds the honesty that the Landauer floor is a real bound while present hardware sits many orders of magnitude above it.
- **Attwell & Laughlin 2001** - D. Attwell & S. B. Laughlin (2001). An Energy Budget for Signaling in the Grey Matter of the Brain. J. Cerebral Blood Flow & Metabolism 21(10):1133-1145, DOI 10.1097/00004647-200110000-00001. https://doi.org/10.1097/00004647-200110000-00001. Breaks the brain's power draw down per signaling event, yielding a bottom-up energy-per-bit for neural computation. Complements the top-down ~20 W brain anchor with the mechanistic cost of one bit of neural signaling.
- **Shockley & Queisser 1961** - W. Shockley & H. J. Queisser (1961). Detailed Balance Limit of Efficiency of p-n Junction Solar Cells. Journal of Applied Physics 32(3):510-519, DOI 10.1063/1.1736034. https://doi.org/10.1063/1.1736034. The thermodynamic (detailed-balance) ceiling on single-junction photovoltaic conversion, about 30% at 1.1 eV. Grounds the solar-limited premise: only a bounded fraction of incident solar flux becomes electrical watts, setting the upper bound on the budget split among manufacturing, compute, and housekeeping.
- **Gilmore 2002** - D. G. Gilmore (ed.), The Aerospace Corporation (2002). Spacecraft Thermal Control Handbook, Volume I: Fundamental Technologies (2nd ed.). The Aerospace Press / AIAA, DOI 10.2514/4.989117. https://arc.aiaa.org/doi/book/10.2514/4.989117. Waste-heat rejection in vacuum is radiation-only, Q = e*sigma*A*(T^4 - T_env^4), so radiator area and temperature set what power a system can dissipate. Grounds the housekeeping / thermal side of the budget and the radiator temperature T that the Landauer floor scales with.
- **NASA SoA Small Spacecraft Power 2024** - NASA Ames Research Center (Small Spacecraft Systems Virtual Institute) (2024). State of the Art of Small Spacecraft Technology - Power chapter. NASA / Ames Research Center technical report (2024 edition). https://www.nasa.gov/wp-content/uploads/2025/02/3-soa-power-2024.pdf. Space solar-array specific power in W/kg (roll-out arrays about 75 W/kg; flexible arrays demonstrated toward hundreds of W/kg). Grounds the mass cost of the power source that feeds the whole budget - how many kilograms of array a solar-limited watt requires.
