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

## Per-scenario inputs (not constants)

- **Compute efficiency (FLOPS/W)** - an input to `compute_capacity_flops`, not a
  hardcoded value, because it moves with hardware and precision. Representative
  present-day accelerators are ~1e11 FLOPS/W (e.g. an NVIDIA H100 at ~60 TFLOPS FP64 /
  ~700 W ≈ 8.6e10 FLOPS/W); the Landauer floor above is the hard physical ceiling.
  A scenario that fixes a value must cite the specific device. `[ESTIMATE]` until pinned.
- **Allocation fractions** (manufacturing / compute / housekeeping) - scenario design
  choices, not physical facts; a real scenario should justify them against a mission.
