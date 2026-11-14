# subsystems - REFERENCES

Every number used by a `subsystems` submodule, with its source and a verdict.

This file is the ten former per-module `REFERENCES.md` files concatenated without edit when
those modules became submodules. Each section below is one former file, its headings demoted
one level. No entry was reworded, merged or dropped; the pre-merge history of any section is
in git under its old path, for example `modules/thermal/REFERENCES.md`.

## assembly

## Where the numbers come from

Every quantity in `assembly` traces to a source below, or is derived from ones that do
(CLAUDE.md §1). Units: kg, hours, days. This module derives a number that `closure-sim`
and `multi-probe` currently take as a hand-set input, so the whole point is to replace
assumption with sourced derivation - and to be honest that the result is an `[ESTIMATE]`
band, not a point.

### Why the whole result is `[ESTIMATE]`

No self-replicating space factory has ever been built, so there is no measured space
build rate. Every input below is a **terrestrial** metal-AM or manufacturing figure used
as a proxy. That is a legitimate `[ESTIMATE]` (documented proxy), not a measured fact -
tagged here and at the use site. The honest output is a band spanning >10x, not a single
number.

### Deposition rates, kg/h (metal additive manufacturing)

- **WAAM (wire-arc additive manufacturing): ~1-10 kg/h.** `WAAM_RATE_KG_PER_H = (1.0,
  10.0)`. Wire-arc DED melts wire with an electric arc at high deposition rate.
  Per-material: titanium ~0.4-1.2 kg/h; steel up to ~4 kg/h (multi-wire higher).
  Sources: ScienceDirect "Wire Arc Additive Manufacturing" overview,
  https://www.sciencedirect.com/topics/materials-science/wire-arc-additive-manufacturing ;
  Fronius WAAM, https://www.fronius.com/en-us/usa/welding-technology/info-centre/magazine/2019/waam .
  Verdict: sourced (industry + review); representative range.
- **LPBF (laser powder-bed fusion): ~0.2-1.4 kg/h (mass basis).** `LPBF_RATE_KG_PER_H =
  (0.2, 1.4)`. Higher precision, far lower throughput than WAAM; build rate ~5-40 cm^3/h
  single-laser, up to ~288 cm^3/h high-power/multi-laser. Source: review of laser-based
  powder-bed fusion, https://link.springer.com/article/10.1007/s00170-020-05361-3 ; EPRI
  LPBF brief, https://restservice.epri.com/publicdownload/000000003002019762/0/Product .
  Verdict: sourced. Basis pinned to **mass** (kg/h), not volume, to avoid the cm^3-vs-kg
  ambiguity (CLAUDE.md §1).

### Overall Equipment Effectiveness (duty_cycle x yield)

- **World-class OEE = 0.85.** `WORLD_CLASS_OEE`. Seiichi Nakajima's TPM benchmark, built
  from availability >=0.90, performance >=0.95, quality >=0.999. Source:
  https://www.leanproduction.com/oee/ . Verdict: sourced, canonical.
- **World-class quality (first-pass yield) = 0.999.** `WORLD_CLASS_QUALITY`. The quality
  component of the 0.85 benchmark (same source). Used as the yield factor.
- **Typical manufacturing OEE ~0.60** (discrete-manufacturing average ~66.8%). Source:
  https://www.leanproduction.com/oee/ ; industry benchmark aggregates. Verdict: sourced.
  Used for the conservative low end of the band.

### NASA AASM upper anchor (whole-factory rate)

- **100-tonne seed factory copies itself in 1 year -> ~274 kg/day.** `AASM_SEED_MASS_KG
  = 100000`, `AASM_SELF_COPY_DAYS = 365`; 100000/365 = 273.97 kg/day (derived). Source:
  R. Freitas & W. Gilbreath (eds.), *Advanced Automation for Space Missions*, NASA
  Conference Publication 2255 (1982), the self-replicating lunar factory concept. NTRS
  https://ntrs.nasa.gov/citations/19820045716 ; full text
  https://nss.org/wp-content/uploads/1982-Self-Replicating-Lunar-Factory.pdf ; summary
  http://www.rfreitas.com/Astro/AASMJAS1982.htm . Verdict: sourced (primary NASA
  concept). This is the aggressive whole-factory upper bound - a documented design point,
  not an invented number.

### The derivation (shown, not assumed)

```
build_rate = manipulators * deposition_rate * hours_per_day * duty_cycle * yield
```
- **anchor** (reproduces closure-sim's 20 kg/day): 1 x 1.0 kg/h x 24 h x 0.85 x 0.999 =
  **20.4 kg/day**. That closure-sim's hand-set 20 falls out of a single slow WAAM head at
  world-class OEE is the cross-check that the derivation is calibrated, not fudged.
- **low**: 1 x 0.2 kg/h (LPBF) x 24 h x 0.60 x 0.999 = **2.9 kg/day**.
- **high**: NASA AASM = **274 kg/day**.
- **copy time** (the doubling clock, reused from multi-probe, no new number):
  `copy_time = closure_ratio * seed_mass / build_rate`. Lunar seed (C=0.97, seed=12000
  kg, rate=20): 0.97 x 12000 / 20 = **582 days** (matches FINDINGS #9). At the NASA rate
  it falls to ~42.5 days - the >10x rate spread is a >10x clock spread.

### Verified targets (asserted in tests)

- The derivation equals its product; anchor = 20.4 kg/day (within 3% of the 20 it
  retires); AASM implied rate = 273.97 kg/day; the band brackets the anchor and is >10x
  wide; copy_time reproduces 582 days for the lunar seed and 42.5 days at the NASA rate;
  build rate scales linearly in manipulators; copy time scales with closure.

### Interface wiring

- **-> closure-sim / multi-probe:** `machinery_build_rate_kg_per_day(...)` supplies the
  `local_build_rate_kg_per_day` input both currently hand-set to 20. The band means a
  scenario should carry the rate as a range, and the doubling clock inherits that range.
- **copy-time seam:** `copy_time_days` is `multi_probe.time_to_build_one_copy_days` in
  the machinery-bound regime, reproduced (not re-invented) so this module can show its
  rate setting the clock. No dependency on multi-probe is taken (assembly stays pure and
  independently runnable); the shared formula is the clean seam.
- **feedstock seam:** the deposition rate assumes feedstock is available; `isru` sizes
  the energy to make that feedstock. Kept separate (over-nesting guard, CLAUDE.md §3).

### Further reading (bibliography)

- **Freitas & Gilbreath 1982** - Advanced Automation for Space Missions, NASA CP-2255.
  The self-replicating lunar factory and its 100 t/yr self-copy - the field's founding
  quantitative concept and this module's upper anchor.
- **Nakajima 1988** - S. Nakajima, *Introduction to TPM: Total Productive Maintenance*.
  The origin of the 85% world-class OEE benchmark used for duty_cycle x yield.

### Invariants (issue #48, phase B)

`BuildRateBand` is a frozen dataclass with a `__post_init__` postcondition. Unlike
the fold-module assertions, this one runs in release too (no `if __debug__:`): a
band that violates it is a malformed value that callers must not silently see.

- **[inv:as-band]** `low_kg_per_day > 0` and `low_kg_per_day <= anchor_kg_per_day
  <= high_kg_per_day`. Uncertainty bands must be well-formed.

Tests: `tests/test_invariants.py`.

### Distribution bands (distributions.py)

UQ spreads around the point values above, not new measurements.

- **`WAAM_RATE_DIST = Uniform(1, 10)` and `LPBF_RATE_DIST = Uniform(0.2, 1.4)` kg/h** - the
  sourced ranges above, used as given.
- **`WORLD_CLASS_OEE_DIST = Uniform(0.80, 0.90)`** - `[ESTIMATE]`: Nakajima's 0.85 is a
  benchmark floor, so values above it are possible; the +/-0.05 width has no citation
  recoverable from this repo.
- **`TYPICAL_OEE_DIST = Uniform(0.50, 0.70)`** - `[ESTIMATE]`: discrete manufacturing
  spreads roughly 0.50-0.70 around the ~0.60 (66.8% quoted) typical figure above; the
  band is carried over from the earlier code comment with no separate citation.
- **`WORLD_CLASS_QUALITY_DIST = Uniform(0.995, 0.9999)`** - `[ESTIMATE]`: brackets the 0.999
  first-pass-yield benchmark; band edges have no citation recoverable from this repo.
- **`AASM_SEED_MASS_DIST`, `AASM_SELF_COPY_DAYS_DIST` and `HOURS_PER_DAY_DIST`** - Fixed:
  the NASA CP-2255 design point and a definitional 24 h, as above.

## autonomy

## Where the numbers come from

Every quantity in `autonomy` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: FLOPS / operations per second, W, AU. This module supplies the
compute *demand* that `probe-sim` models the *supply* for; the demand is an honest
`[ESTIMATE]` band, not a point.

### Basis warning (pinned, CLAUDE.md 1)

The self-driving figure is **TOPS** (integer tera-operations per second); the brain
figures are **FLOPS** (floating-point operations per second). They are not the same unit.
This module compares them only as order-of-magnitude "operations per second" for
accounting, and flags the distinction rather than silently equating them. A scenario that
needs a precise FLOP/integer-op conversion must state it.

### Compute-demand anchors (three converging lines)

- **`HONEYBEE_BRAIN_FLOPS = 1e13`** - honeybee brain compute. Estimates span a spike-model
  floor of ~1e10 FLOPS to ~1e16 FLOPS with full non-neuronal physiology; 1e13 is a
  representative middle used as the lower autonomy anchor. Source: "The case for emulating
  insect brains...", arXiv:1812.09362, https://arxiv.org/pdf/1812.09362 . Verdict:
  `[ESTIMATE]` (wide range; representative point).
- **`SELF_DRIVING_OPS_PER_S = 1.4e14`** - onboard compute of a self-driving car, ~140
  TOPS. Context: full autonomous-vision workloads are 50-100 TOPS, L4 ~320 TOPS, NVIDIA
  Orin 254 TOPS, Mobileye EyeQ6 128 TOPS. 140 TOPS is a representative L4-class figure.
  Sources: Edge AI and Vision Alliance,
  https://www.edge-ai-vision.com/2021/04/autonomous-vehicles-drive-ai-chip-innovation/ ;
  GSA, https://www.gsaglobal.org/forums/edge-ai-computing-advancements-driving-autonomous-vehicle-potential/ .
  Verdict: sourced (engineered system of known capability - the strongest anchor).
- **`MOUSE_BRAIN_FLOPS = 1e15`** - mouse brain compute. Brain-compute estimates span
  ~1e13-1e17 FLOP/s; 1e15 is a representative middle used as the upper anchor. Source:
  Open Philanthropy brain-computation report,
  https://www.openphilanthropy.org/brain-computation-report . Verdict: `[ESTIMATE]`.

The point is convergence: an engineered autonomous system (self-driving car) sits between
two independent biological estimates (honeybee, mouse), so the demand band 1e13-1e15
ops/s is triangulated three ways, not asserted once.

### `[GAP]` (tagged, not invented)

- **"FLOPS to run a whole self-replicating factory" is a genuine `[GAP]`** - no measured
  value exists. But it is *boundable* to the same 1e13-1e15 band by analogy to the
  anchors above (a factory's control/perception is comparable to a self-driving car's),
  rather than fabricated. Flagged here and at any use site.

### The derivations (shown, validated in tests)

- **`required_compute_power_w = required_flops / efficiency`** - the inverse of
  `power_budget.compute_capacity_flops` (flops = power x efficiency); the FLOPS/W
  efficiency is a sourced scenario input documented in `power-budget/REFERENCES.md`.
- **`compute_fraction_needed = required_compute_w / total_power`** - the DERIVED
  replacement for the hand-set 0.70 manufacturing / 0.30 compute split in
  `mission`/`multi-probe`. The compute share now falls out of sourced demand and
  available power (140 TOPS at 1e10 FLOPS/W on a 100 kW bus -> 0.14, not 0.30).
- **`autonomy_wall_au = sqrt(supply_1AU / required)`** - supply falls as 1/d^2, demand is
  flat, so they cross at this distance. Verified to equal
  `probe_sim.max_distance_for_compute` fed the same array, split, and efficiency - the
  supply/demand loop is closed, not two disconnected models.

### Note on the brain scale vs power-budget

`power-budget` carries a *human*-brain scale marker (~1e18 FLOPS, Sandberg & Bostrom) for
"general intelligence per watt". This module uses *insect and small-mammal* brains as the
demand anchors for probe autonomy - a different, lower, and better-bounded quantity. No
contradiction: different brains for different questions.

### Interface wiring

- **<- probe-sim:** reuses `max_distance_for_compute` (supply) and `SolarArray`; this
  module supplies the sourced `required_flops` those took as a free input.
- **reuses power-budget:** the watts<->FLOPS conversion (single source of truth).
- **-> mission / multi-probe:** the derived compute fraction retires their 0.70/0.30
  free choice; the autonomy wall is a new distance limit alongside the power wall.

### Further reading (bibliography)

- **Open Philanthropy brain-computation report** - the brain-FLOP/s ranges behind the
  honeybee and mouse anchors.
- **Edge AI and Vision Alliance / GSA** - the TOPS-by-autonomy-level figures behind the
  self-driving-car central anchor.

### Analytical companion (issue #50, Phase 2)

`docs/FINDINGS_CLASSIFICATION.md` #30 asserts the autonomy wall
`d_wall = sqrt(supply_flops_at_1AU / required_flops)`. This is the compute
analogue of the power-source distance crossover (finding #24), from the
demand side. Derivation:

Solar-fed compute supply falls as `1/d^2`; autonomy demand is
distance-independent (set by the control problem, not the range):

    S(d) = S_1AU / d^2
    D    = required_flops

The wall is where supply drops below demand: `S(d_wall) = D`, hence

    d_wall = sqrt(S_1AU / D)

Two structural facts follow:
- **Absolute magnitude cancels** if S and D scale together
  (`d_wall(alpha*S, alpha*D) = d_wall(S, D)`).
- Only the **ratio** `S_1AU / D` controls the wall - not either quantity
  individually.

Tests in `tests/test_analytical_companions.py` verify (i) the closed form
matches, (ii) supply exactly equals demand at `d = d_wall`, (iii) the
absolute-magnitude cancellation via a joint-rescaling sweep, and (iv) the
`sqrt(2)` elasticity to doubling supply or demand.

### Distribution bands (distributions.py)

UQ spreads that reuse the ranges sourced above; no new numbers.

- **`HONEYBEE_BRAIN_FLOPS_DIST = LogUniform(1e10, 1e16)`** - the spike-model floor to
  full-physiology span (six orders of magnitude), with 1e13 its representative middle.
- **`MOUSE_BRAIN_FLOPS_DIST = LogUniform(1e13, 1e17)`** - the brain-compute range quoted above,
  with 1e15 its middle.
- **`SELF_DRIVING_OPS_PER_S_DIST = Uniform(5e13, 3.2e14)`** - vision-only 50 TOPS up to full
  L4 ~320 TOPS (the lower edge is the 50 TOPS vision-workload floor quoted above), with 140
  TOPS inside it. TOPS, not FLOPS: see the basis warning.

## comms

## Where the numbers come from

Every quantity in `comms` traces to a source below, or is derived from ones that do
(CLAUDE.md §1). Distance is the **Earth-spacecraft range** in AU (not heliocentric -
they differ by up to ~2 AU near Earth; pinned per CLAUDE.md §1). Rates in Mbit/s.

### The 1/d^2 law (physics, derived - not assumed)

The power-limited `R(d) = k/d^2` is not a fitted guess; it is Shannon meeting Friis:

- **Friis transmission** `Pr = Pt Gt Gr (lambda / 4 pi d)^2` - received power falls as
  `1/d^2`. Radio-engineering standard, https://www.sciencedirect.com/topics/computer-science/friis-equation .
  Verdict: exact (physics).
- **Shannon-Hartley capacity** `C = B log2(1 + S/N)`. Shannon-Hartley theorem,
  https://www.sciencedirect.com/topics/engineering/shannon-capacity . Verdict: exact.
- In the power-limited (below-noise) wideband limit `log2(1+x) -> x/ln2`, so
  `C -> Pr/(N0 ln2) proportional 1/d^2`, independent of bandwidth. Hence `R(d) = k/d^2`.
- **Ultimate Shannon power limit** `Eb/N0 = ln2 = -1.59 dB`; practical coded floor
  ~0.7 dB @ BER 1e-5 (turbo/LDPC, within ~1 dB of Shannon). JPL CCSDS turbo codes,
  https://tmo.jpl.nasa.gov/progress_report/42-120/120D.pdf . Verdict: sourced; the
  required-Eb/N0 gap is an `[ESTIMATE]` folded into the calibration constant k.

### Primary-source confirmation of the shape

- **DSOC 1/d^2 confirmed by JPL:** "rate reduction proportional to inverse square of
  distance." NASA/JPL DSOC first-phase release,
  https://www.jpl.nasa.gov/news/nasas-laser-comms-demo-makes-deep-space-record-completes-first-phase/ .
  Verdict: sourced (primary). This is the same inverse-square gate `probe-sim` uses for
  power - now for data rate.

### Calibration anchors (DSOC optical, Earth-range AU)

- **25 Mbps at 1.506 AU -> k = 56.7 Mbps*AU^2**
- **8.3 Mbps at 2.582 AU -> k = 55.3 Mbps*AU^2**
- The two independent fits agree to **~2.5%**, confirming the law (rate ratio
  25/8.3 = 3.01 vs distance-ratio-squared (2.582/1.506)^2 = 2.94). Source: phys.org
  reporting JPL DSOC numbers,
  https://phys.org/news/2024-04-nasa-deep-space-optical-communications.html . Adopted
  **`K_OPTICAL_MBPS_AU2 = 56.0`** (the ~midpoint). Verdict: sourced + cross-checked.
- **`R_MAX_DSOC_MBPS = 267` Mbps** - the DSOC modem/protocol ceiling (the rate-limited
  plateau near Earth). Same phys.org/JPL source. Verdict: sourced.
- **Crossover** `d_cross = sqrt(k/R_max) = sqrt(56/267) = 0.458 AU` - derived; where the
  clamp meets the power-limited branch.

### Order-of-magnitude anchors (span ~7 orders; RF has its own k)

- **Voyager 1: ~40 bit/s now (160 at launch), 22 W X-band (8420 MHz), ~163 AU, 70 m
  DSN dish.** IEEE Spectrum, https://spectrum.ieee.org/voyager-1 ; Voyager telecom
  (Ludwig & Taylor), https://voyager.gsfc.nasa.gov/Library/DeepCommo_Chapter3--141029.pdf .
- **New Horizons at Pluto (~32.9 AU): 1-2 kbit/s, 12 W, 2.1 m dish.** Wikipedia/JHU-APL,
  https://en.wikipedia.org/wiki/New_Horizons .
- **MRO (~0.5-2.7 AU): 0.5-6 Mbit/s, 100 W TWTA, 3 m antenna.** NASA MRO comms,
  https://mars.nasa.gov/mro/mission/communications/commxband/ .
- **DSOC flight laser: 4 W avg, 1550 nm.** NASA Science DSOC,
  https://science.nasa.gov/photojournal/dsocs-flight-laser-transceiver/ .
- **Optical vs RF advantage: 10-100x** (same 1/d^2 shape, larger k). JPL DSOC (above).
  In this module RF vs optical is a selectable `k`, not a second module.

### Comms as a power draw (derived)

- **Transmit power ~4.7-4.9% of bus power.** Derived: Voyager 22 W / ~470 W bus;
  New Horizons 12 W / ~245 W. Verdict: derived from the sourced W figures above; feeds
  `power-budget` as a fourth allocation (~5% of bus power).

### Verified targets (asserted in tests)

- `calibrate_k` returns 56.7 and 55.3 for the two DSOC anchors (agree to <3%).
- Power-limited branch reproduces both DSOC points to ~2% with k=56.
- At 0.35 AU the uncapped law gives ~457 Mbps but `data_rate_at` returns exactly the
  267 Mbps cap (the rate-limited crossover).
- `crossover_distance_au(56, 267) = 0.458 AU`, and the two regimes meet there.
- d -> infinity => R -> 0 (monotone); d -> 0 => R clamps at R_max (no blow-up).
- The data-return wall: generation above the link rate accumulates unbounded backlog;
  fleet aggregate return = sum of per-probe link rates, not probe count.

### Notes on basis and boundaries

- **Earth-range, not heliocentric.** `probe-sim`/`power-source` use heliocentric
  distance; `comms` uses Earth-spacecraft range. A scenario must not mix them.
- **Throughput, not latency.** This is bits/s once they can flow. `swarm`'s
  light-speed `coordination="lightspeed"` is the *latency* layer (news arrives no
  sooner than dist/c). They compose; they do not merge.
- No per-photon link budget, no DSN scheduling/contention, no modulation/coding
  internals - the runtime is one division plus a clamp (over-nesting guard, CLAUDE.md §3).

### Further reading (bibliography)

- **Shannon 1948** - C. E. Shannon. A Mathematical Theory of Communication. Bell System
  Technical Journal 27. The capacity theorem behind the power-limited derivation.
- **JPL DSOC 2024** - NASA/JPL Deep Space Optical Communications first-phase results
  (links above). The primary source for the 1/d^2 confirmation and the calibration
  anchors.

### Distribution bands (distributions.py)

UQ spreads around the point values above, not new measurements.

- **`K_OPTICAL_MBPS_AU2_DIST = Uniform(55.3, 56.7)` Mbps*AU^2** - the two DSOC anchor fits
  (k = 55.3 and k = 56.7) taken as the band edges; their ~2.5% disagreement (+/- ~1.25% about
  the 56.0 midpoint) is the honest error bar on k. Sourced (phys.org / JPL, above).
- **`R_MAX_DSOC_MBPS_DIST = Uniform(200, 267)` Mbps** - upper edge is the published 267 Mbps
  DSOC ceiling (sourced above). `[ESTIMATE]`: the 200 Mbps lower edge reflects the
  near-Earth plateau running lower with link margin; it was carried over from the earlier
  code comment and has no citation recoverable from this repo.
- **`BITS_PER_MBIT_DIST`** - Fixed, a definitional unit conversion.

## isru

## Where the numbers come from

Every quantity in `isru` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: kWh/kg for specific energy, wt% for composition. This module
derives numbers `closure-sim` currently takes as hand-set inputs, so the point is to
replace assumption with sourced physics and to be explicit about the `[ESTIMATE]` seams.

### Oxygen: full-chain specific energy (well-sourced, lunar tier)

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

### Metal: molten oxide electrolysis of iron (derives closure-sim's 5.0)

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

### Closure ceiling: lunar regolith composition

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

### The derivations (shown, not assumed)

- Gaseous-vs-liquid oxygen: dropping the 4.8% liquefaction share gives 24.3 x 0.952 =
  23.1 kWh/kg gaseous - a basis a scenario may prefer.
- Closure ceiling: `ceiling = sum(mass of parts whose required elements are all present)
  / total mass`. It is the hard upper bound on closure-sim's C: `C <= ceiling`. On the
  Moon, any C/H/N-bearing part (polymers, much of the electronics) counts against it.

### `[ESTIMATE]` / `[GAP]` seams (tagged at use)

- In-situ metals beyond iron, and **all asteroid extraction**, use terrestrial
  molten-oxide-electrolysis as a proxy - `[ESTIMATE]`. Build the lunar-oxygen and lunar-
  iron tiers solid first; treat asteroid support as a tagged second tier.
- The 0.1 wt% usable threshold is a modelling choice, not a measured cut-off.

### Interface wiring

- **-> closure-sim:** `metal_energy_kwh_per_kg` supplies the per-material
  `energy_to_produce_kwh_per_kg` (retiring the 5.0 iron figure); `closure_ceiling`
  grounds the `producible_locally` boolean and caps the achievable closure ratio.
- **-> propellant (proposed):** `WATER_ICE_LOX_KWH_PER_KG` is the oxidiser-energy input
  for the water route; kept distinct from the regolith route.
- **-> power-source / power-budget:** these specific energies size the electrical load
  the power system must meet.

### Further reading (bibliography)

- **Schrenk et al. 2025** - Modeling energy requirements for oxygen production on the
  Moon, PNAS (2025), doi 10.1073/pnas.2306146122. The full-chain 24.3 +/- 5.8 kWh/kg LOX
  figure and its step-by-step energy breakdown.
- **Heiken, Vaniman & French 1991** - Lunar Sourcebook: A User's Guide to the Moon.
  Cambridge University Press. The canonical lunar regolith elemental composition and the
  ppm-level volatile abundances behind the closure ceiling.
- **Sadoway / Boston Metal (MOE)** - molten oxide electrolysis of iron: thermodynamic
  and practical specific energies grounding the ~2.6-4.0 kWh/kg metal figures.

## power_source

## Where the numbers come from

Every quantity in `power-source` traces to a source below, or is derived from ones that
do (CLAUDE.md 1). Units: W, W/kg, kg, AU, years. Specific powers are the load-bearing
inputs; the crossovers are derived from them.

### Specific power, W/kg (basis: flight system-level, pinned per CLAUDE.md 1)

Solar specific power spans ~4x depending on basis (bare blanket vs wing vs full flight
system with gimbals and structure). We pin the **conservative flight system-level** value.

- **`SOLAR_SPECIFIC_POWER_1AU_W_PER_KG = 100`** - Redwire Roll-Out Solar Array (ROSA)
  flight system-level ~100-120 W/kg; wing-level and test articles reach 200-500 W/kg (the
  4x span). Sources: ROSA, https://en.wikipedia.org/wiki/Roll_Out_Solar_Array ; eoPortal
  ISS-ROSA, https://www.eoportal.org/satellite-missions/iss-rosa . Verdict: sourced;
  basis pinned to system-level (conservative). A scenario may raise it toward wing-level
  with justification.
- **`FISSION_SPECIFIC_POWER_W_PER_KG = 6.7`** - NASA Kilopower 10 kWe class, ~1500 kg ->
  6.7 W/kg (an 800 We unit is ~400 kg -> 2 W/kg; band ~2-7). Source: NASA Kilopower,
  https://ntrs.nasa.gov/api/citations/20140010823/downloads/20140010823.pdf ;
  https://en.wikipedia.org/wiki/Kilopower . Verdict: sourced.
- **`GPHS_RTG_SPECIFIC_POWER_W_PER_KG = 5.2`** - GPHS-RTG (Cassini, New Horizons):
  ~300 We BOL, ~57 kg -> 5.2 W/kg, 8.1 kg Pu-238, 4400 Wth. Source:
  https://en.wikipedia.org/wiki/GPHS-RTG ; NASA Cassini RTG,
  https://science.nasa.gov/mission/cassini/radioisotope-thermoelectric-generator/ .
  Verdict: sourced.
- **`MMRTG_SPECIFIC_POWER_W_PER_KG = 2.4`** - MMRTG (Curiosity, Perseverance): ~110 We,
  45 kg -> ~2.4 W/kg. Source: https://en.wikipedia.org/wiki/Multi-mission_radioisotope_thermoelectric_generator .
  Verdict: sourced.

### Crossovers (derived, shown)

- **Distance crossover** `d_cross = sqrt(sp_solar_1AU / sp_nuclear)` - set solar
  `sp_solar_1AU/d^2` equal to the distance-independent nuclear specific power. The power
  level P cancels (both source masses scale linearly with P), so the crossover is
  independent of how much power you need. Against fission: sqrt(100/6.7) = **3.86 AU**;
  against an RTG: sqrt(100/5.2) = **4.39 AU**. The 4-5 AU band matches reality: Juno runs
  solar at Jupiter's 5.2 AU (with very large arrays - the boundary exception), and deep-
  space missions beyond use radioisotope power. Verdict: derived; reality cross-check.
- **`RTG_FISSION_CROSSOVER_WE = 1000`** - below ~1 kWe an RTG is lighter (graceful
  scaling); above it fission wins (its fixed reactor/shield/radiator overhead amortises).
  Source: Kilopower program rationale (fission targets kWe-class and up; RTGs serve the
  hundreds-of-watts range flown to date). Verdict: sourced (order-of-magnitude threshold).

### The Pu-238 vitamin wall

- **`PU238_PER_GPHS_RTG_KG = 8.1`** - one GPHS-RTG's fuel load (above). Verdict: sourced.
- **`PU238_ANNUAL_PRODUCTION_KG = (0.5, 1.5)`** - US production: DOE delivered ~0.5 kg in
  2023 and is on track for its **1.5 kg/yr** goal by 2026 (production restarted after a
  27-year gap). Sources: DOE, https://www.energy.gov/ne/articles/us-department-energy-completes-major-shipment-plutonium-238-nasa-missions ;
  https://en.wikipedia.org/wiki/Plutonium-238 . Verdict: sourced.
- **Derived:** one GPHS-RTG's 8.1 kg is 5.4 years of the entire US supply at the 1.5
  kg/yr goal (16 years at today's ~0.5). A fleet of RTGs is throttled by an isotope no
  factory can produce in place - the sharpest vitamin in the project.

### Reactor radiator (delegates to thermal)

- **`FISSION_CONVERSION_EFFICIENCY = 0.30`** - Kilopower Stirling thermal-to-electric
  conversion ~30%. Source: NASA Kilopower (above). Waste heat = P_e (1-eff)/eff.
- **`FISSION_RADIATOR_TEMP_K = 500`** - representative Stirling cold-side / radiator
  temperature; a hot radiator is light (thermal's T^4 leverage). Source: Kilopower.
  Verdict: sourced (representative). The radiator area/mass come from
  `thermal.size_radiator` - the Stefan-Boltzmann model lives in one place.

### Interface wiring

- **-> power-budget:** emits available power at a distance (`solar_specific_power_at`
  times a chosen mass, or a nuclear source's constant power).
- **-> closure-sim:** the source mass is a BOM line; the Pu-238 requirement is a hard
  import (vitamin) for any RTG-powered design.
- **calls thermal:** `fission_reactor_radiator` sizes the reactor's radiator via
  `thermal.size_radiator` (does not re-implement Stefan-Boltzmann).
- **reuses probe-sim:** the 1/d^2 solar law (single source of truth for the solar
  constant).

### Further reading (bibliography)

- **NASA Kilopower / KRUSTY** - kWe-class space fission specific power and conversion
  efficiency behind the fission figures.
- **DOE Pu-238 program** - the 0.5 -> 1.5 kg/yr production ramp behind the vitamin wall.
- **World Nuclear Association, "Nuclear Reactors for Space"** -
  https://world-nuclear.org/information-library/non-power-nuclear-applications/transport/nuclear-reactors-for-space -
  cross-check on RTG/fission flight history and the power ranges each serves.

### Analytical companion (issue #50, Phase 2)

`docs/FINDINGS_CLASSIFICATION.md` #24 asserts the solar/nuclear crossover
distance is a technology-only constant. Derivation:

At distance d, the solar array's specific power is `sp_solar(d) = sp_solar_1AU / d^2`
(the `1/d^2` law). A nuclear source has distance-independent specific power
`sp_nuclear`. To deliver power P, the source masses are

    m_solar(P, d)   = P * d^2 / sp_solar_1AU
    m_nuclear(P)    = P / sp_nuclear

Equating gives

    d_cross^2 = sp_solar_1AU / sp_nuclear
    d_cross = sqrt(sp_solar_1AU / sp_nuclear)

**P cancels**: the crossover is a property of the two technologies, not the
mission's power level. At defaults (`sp_solar_1AU = 100 W/kg`,
`sp_nuclear = 6.7 W/kg` fission) this is ~3.86 AU, matching the sourced
"4-5 AU" band and reality (Juno at Jupiter's 5.2 AU is right at the boundary
with an oversized array).

Tests in `tests/test_analytical_companions.py` assert (i) the closed form
matches the code, (ii) crossover is invariant under P-rescaling (verifying
the cancellation), (iii) the mass-order flips at exactly `d_cross`.

### Distribution bands (distributions.py)

Companion bands for the point values above; each is a UQ spread, not a new measurement.

- **`SOLAR_SPECIFIC_POWER_1AU_DIST = Uniform(100, 400)` W/kg** - spans the ~4x basis span
  above, flight system-level (100) to wing-level. Verdict: derived from the sourced 4x
  span; a scenario that pins the basis should narrow it. Note the ROSA wing-level range
  quoted above is 200-500 W/kg, so the 400 upper edge is the 4x span applied to 100.
- **`FISSION_SPECIFIC_POWER_DIST = Uniform(2, 7)` W/kg** - Kilopower design points (800 We
  ~2 W/kg to 10 kWe ~6.7 W/kg), sourced above.
- **`RTG_SPECIFIC_POWER_DIST = Uniform(2.4, 5.2)` W/kg** - MMRTG 2.4 to GPHS-RTG 5.2, both sourced above.
- **`PU238_ANNUAL_PRODUCTION_DIST = Uniform(0.5, 1.5)` kg/yr** - the DOE (low, high) sourced above.
- **`RTG_FISSION_CROSSOVER_DIST = LogUniform(300, 3000)` We** - a factor-of-~3 either side of
  the ~1 kWe order-of-magnitude threshold. `[ESTIMATE]`: the factor 3 is a stated choice
  expressing "order of magnitude", not a sourced figure.
- **`FISSION_CONVERSION_EFFICIENCY_DIST = Uniform(0.25, 0.35)`** - ~30% Kilopower Stirling
  with a +/- 5% (absolute) design range. `[ESTIMATE]`: the +/- 5% range has no citation
  recoverable from this repo.
- **`FISSION_RADIATOR_TEMP_DIST = Uniform(450, 550)` K** - 500 K representative with a
  +/- 50 K design range. `[ESTIMATE]`: no citation recoverable from this repo.
- **`PU238_PER_GPHS_RTG_DIST = Uniform(8.0, 8.2)` kg** - 8.1 kg +/- 0.1 kg for a
  manufactured spec. `[ESTIMATE]`: the +/- 0.1 kg tightness has no citation recoverable
  from this repo.

## propellant

## Where the numbers come from

Every quantity in `propellant` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: m/s, kg, seconds, kWh, tonnes. Delta-v and Isp are inputs (from
`transfer` and `launch-economics`); this module adds production energy and the propellant-
closure axis.

### Reaction-mass demand (reused, not re-derived)

- **Tsiolkovsky rocket equation** `m0/mf = exp(Delta_v / v_e)` - reused from
  `launch-economics` (`rocket_equation_mass_ratio`, `exhaust_velocity_m_s`,
  `propellant_fraction`), not re-implemented. The Delta-v is supplied by `transfer`
  (`hohmann_transfer` / `edelbaum_delta_v_m_s` / `sep_transfer`). Verdict: derived from
  sourced siblings; a test round-trips `reaction_mass_kg` against both.
- **Isp bands** (route presets): LOX/LH2 chemical ~450 s; water electrothermal ~300 s;
  xenon Hall EP ~1800 s; xenon ion EP (NEXT-C) ~4190 s. Source: `launch-economics/
  REFERENCES.md` (Sutton & Biblarz; Goebel & Katz; NEXT-C). Verdict: sourced.

### Production energy (water route)

- **`HHV_HYDROGEN_KWH_PER_KG = 39.4`** - higher heating value of hydrogen, 142 MJ/kg =
  39.4 kWh/kg. The thermodynamic total (electrical + thermal) to dissociate water into
  H2 + O2 at standard conditions. Source: Electrolysis of water, Wikipedia,
  https://en.wikipedia.org/wiki/Electrolysis_of_water (HHV 39.4 kWh/kg; Gibbs dG =
  -237.1 kJ/mol behind the 1.23 V minimum). Verdict: sourced (thermodynamic).
- **`HYDROGEN_MASS_FRACTION_OF_WATER = 2.016/18.015 = 0.1119`** - from standard atomic
  masses (H 1.008, O 15.999). Derived.
- **`water_electrolysis_hhv_min_kwh_per_kg() = 39.4 x 0.1119 = 4.41 kWh/kg water`** -
  the thermodynamic floor to electrolyse 1 kg of water (matching the proposal's 4.41).
  Derived, shown. Verdict: derived from the two sourced values above.
- **`KORNUTA_FULL_CHAIN_KWH_PER_KG = 11.3`** - practical mining-to-liquefaction chain for
  water-ice propellant (Kornuta et al.), well above the electrolysis-only floor. Same
  figure `isru` cites for the water-ice LOX route (the shared literature value; the seam
  is kept clean - isru does regolith->parts, propellant does water-ice->reaction mass).
  Verdict: sourced. (Real electrolysers alone run ~50-55 kWh/kg H2 ~ 5.6-6.2 kWh/kg
  water; the full chain adds mining and liquefaction.)

### The noble-gas import wall

- **`XENON_WORLD_SUPPLY_T_PER_YR = (40, 60)`** - Earth's entire annual xenon production is
  ~40-60 tonnes/year (extracted from air; ~1 part in 11.5 million). Sources: Xenon,
  Wikipedia, https://en.wikipedia.org/wiki/Xenon (~60 t/yr); industry figures (~40 t/yr).
  Verdict: sourced (range).
- **NASA anchor:** "a xenon propellant load of 10 metric tons represents greater than 10%
  of the global annual production rate of xenon" and a single such buy disrupts the
  market. Source: Xenon Acquisition Strategies for High-Power Electric Propulsion NASA
  Missions, NTRS 20150023080, https://ntrs.nasa.gov/api/citations/20150023080/downloads/20150023080.pdf .
  Verdict: sourced (primary). `xenon_supply_fraction(10)` reproduces this (10/60 = 16.7%
  > 10%).

### Propellant closure (the new axis)

- **Definition (derived):** `propellant_closure` = fraction of a route's reaction mass
  obtainable locally. Water routes = 1.0 on a water-bearing body (both H and O local),
  0.0 on a dry body; noble-gas EP = 0.0 anywhere (xenon/krypton are not extractable
  off-world in bulk). This is a distinct axis from structural mass closure (isru/
  closure-sim): a probe can close its structure yet still be tethered to Earth by
  propellant.
- **The trade (derived, shown):** for a fixed Delta-v, high-Isp xenon EP drives
  propellant *mass* down (Tsiolkovsky) but leaves 100% of it imported; a water route
  carries more mass but imports none on a water body. `imported = (1 - closure) x mass`.

### `[ESTIMATE]` / basis notes

- Isp presets are representative points within sourced bands; a scenario should pick and
  cite its own. Water-EP Isp varies widely by thruster type.
- Xenon supply is a range; krypton (cheaper, ~8x more abundant) is an alternative not
  modelled here - the wall is specific to xenon, the highest-performance choice.

### Interface wiring

- **<- transfer:** consumes the Delta-v from `hohmann_transfer` / `edelbaum_delta_v_m_s`.
- **reuses launch-economics:** the rocket equation and g0 (single source of truth).
- **shares Kornuta's water-ice energy with isru** (same literature figure; distinct
  seam - do not merge the modules).
- **-> closure-sim / mission:** propellant closure and imported-propellant mass are a new
  import term alongside structural vitamins; the xenon wall caps EP-fleet size.

### Further reading (bibliography)

- **Kornuta et al. 2019** - Commercial lunar propellant architecture. New Space / full-
  chain water-ice-to-propellant energy (~11 kWh/kg), the practical anchor above.
- **NASA NTRS 20150023080** - Xenon Acquisition Strategies for High-Power Electric
  Propulsion. The 10 t = >10% of world supply anchor behind the import wall.

### Distribution bands (distributions.py)

UQ spreads around the point values above, not new measurements.

- **`KORNUTA_FULL_CHAIN_DIST = Uniform(9, 15)` kWh/kg** - `[ESTIMATE]`: the 11.3 kWh/kg
  point with a roughly -20% / +33% (about 30%) band for mining and liquefaction variability.
  The band is carried over from the earlier code comment with no citation recoverable
  from this repo; it matches the band used for the same figure in `isru`.
- **`XENON_WORLD_SUPPLY_DIST = Uniform(40, 60)` t/yr** - the sourced range above, used as given.
- **Isp bands** - LOX/LH2 `Uniform(440, 460)` s, water resistojet `Uniform(280, 320)` s,
  xenon Hall `Uniform(1500, 2000)` s, xenon ion `Uniform(4000, 4300)` s: `[ESTIMATE]` windows
  around the Isp points above (launch-economics sources); the window widths have no
  separate citation recoverable from this repo.
- **`HHV_HYDROGEN_DIST` and `HYDROGEN_MASS_FRACTION_OF_WATER_DIST`** - Fixed (thermodynamic
  and atomic-mass derived).

## reliability

## Where the numbers come from

Every quantity in `reliability` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: fraction/yr (degradation), mSv (dose), per-day (hazard),
dimensionless (Aurora fraction). This is the only module with RNG; the discipline around
it is documented as carefully as the numbers.

### RNG discipline (CLAUDE.md 7 - not a number, but load-bearing)

Randomness is a **pure seeded fold**: `rng.py` is splitmix64 (Vigna), a deterministic
64-bit generator whose state is an explicit `int` threaded through `mortality.step`. No
`random.random()`, no wall-clock seed, deterministic iteration order (one draw per living
unit, in order). Same seed -> identical trajectory, forever. Source: S. Vigna, splitmix64,
https://prng.di.unimi.it/splitmix64.c . This is what keeps replay and `speculate` exact.

### Deterministic degradation

- **`ARRAY_DEGRADATION_PER_YR = 0.003`** (band 0.002-0.010) - solar-array power loss per
  year. ISS P6 arrays degrade 0.2-0.5 %/yr (flight-measured); GEO GaAs cells 0.44-1.03
  %/yr. Sources: NASA "On-Orbit Performance Degradation of the ISS P6 Photovoltaic
  Arrays", NTRS 20030068268, https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20030068268.pdf ;
  "Solar array degradation on geostationary communications satellites", IJSPACESE 5(1),
  https://www.inderscience.com/info/inarticle.php?artid=90549 . Verdict: sourced (flight-
  measured). The 0.003 default is the ISS mid-range; `environment_multiplier` raises it
  near the Sun / in the Jovian belts (a documented parameter, not a sub-model).
- **GCR dose rate** - consumed from `shielding.radenv`
  (`GCR_DEEP_SPACE_DOSE_MSV_PER_DAY = 1.8`, MSL/RAD, Zeitlin et al. 2013). One radiation
  environment, shared - not re-defined here.

### Stochastic mortality (proxy / gap, tagged)

- **`SATELLITE_HAZARD_PER_DAY = 1.1e-5`** `[ESTIMATE]` - per-day failure hazard for a
  discrete unit. Self-replicating factories have no operational failure history, so this
  borrows a satellite-class on-orbit failure rate as a defensible analog (~0.4 %/yr).
  Verdict: `[ESTIMATE]` - a documented proxy, tagged at the use site, not a measured
  factory rate. Source: satellite on-orbit reliability statistics (order-of-magnitude).
- **`SATELLITE_HAZARD_PER_DAY_DIST` band 5e-6 to 2e-5 per day** `[ESTIMATE]` - the
  LogUniform range around the 1.1e-5 proxy, spanning satellite bus classes (about 0.2-0.7
  %/yr at 365 days per year). Verdict: `[ESTIMATE]` - the band was carried over from
  the earlier code comment with no citation recoverable from this repo; the 1.1e-5 centre
  inside it is the only anchored value. Needs a primary satellite-reliability source.
- **Self-replication mutation rate** - a genuine `[GAP]`. Copies that build flawed copies
  have no measured rate; not modelled, only flagged. Do not invent one.
- **`expected_survival_fraction = (1 - hazard)^days`** - the analytic expectation the
  seeded fold fluctuates around (used to check the simulation is unbiased). Derived.

### The mandatory regression guard (CLAUDE.md 2)

With `hazard_per_day = 0`, a uniform draw in [0, 1) is never < 0, so no unit ever dies and
the population trajectory is **identical** to the project's current failure-free models.
The suite asserts this bit-exact across multiple seeds - the safety net that lets
mortality be added without disturbing any existing result.

### Aurora steady-state (verified against the paper)

- **`X_eq = 1 - T_l / T_s`** - equilibrium settled fraction, Carroll-Nellenback et al.
  (2019), "The Fermi Paradox and the Aurora Effect", *Astronomical Journal* 158:3, their
  **Eq. 32**. arXiv:1902.04450, https://arxiv.org/abs/1902.04450 ;
  https://iopscience.iop.org/article/10.3847/1538-3881/ab31a3 . Verdict: sourced +
  verified. The ODE is `dX/dt = (1/T_l) X (1-X) - (1/T_s) X`.
- **Symbols (verified, counterintuitive):** `T_l` = launch/spread time, `T_s` = settlement
  lifetime; a non-zero plateau requires `T_l < T_s` (spread must outrun death). An earlier
  automated read had the meanings and the inequality backwards; this was corrected against
  the primary source. Verdict: verified.

### Interface wiring

- **consumes shielding.radenv:** the shared GCR/Jovian dose numbers (single source).
- **-> multi-probe / swarm:** the Aurora equilibrium turns their unbounded growth into a
  steady state; the mortality fold adds attrition to fleet trajectories.
- **-> closure-sim / mission:** array degradation and dose derate delivered power and
  electronics life over the multi-decade build-out.

### Over-nesting boundary (CLAUDE.md 3)

No dose -> SEU -> latchup chain, no per-component FMEA, no neutron-transport - hazard is a
single sourced per-day rate, degradation a single sourced annual rate, Aurora a two-
parameter ODE. The temptation to nest dose into single-event-effect physics is
deliberately declined.

### Further reading (bibliography)

- **Carroll-Nellenback et al. 2019** - the Aurora steady-state and Eq. 32.
- **NASA ISS P6 array degradation (NTRS 20030068268)** - the flight-measured annual array
  loss behind the degradation rate.
- **Zeitlin et al. 2013** (via shielding.radenv) - the deep-space GCR dose rate.

### Invariants (issue #48, phase A)

The fold `mortality.step` is guarded by `_verify_step_invariants(before, after)`,
called under `if __debug__:`. `python -O` strips both the call site and the
asserts, so ensemble runs pay zero cost. Positive + negative tests live in
`tests/test_invariants.py`.

- **[inv:rl-alive-monotone]** `after.alive <= before.alive`. Deaths never resurrect.
- **[inv:rl-alive-nonneg]** `after.alive >= 0`. Population is a count.
- **[inv:rl-day-monotone]** `after.day == before.day + 1`. Time advances exactly one day per step.
- **[inv:rl-rng-advances]** If `before.alive > 0`, `after.rng != before.rng`. Guards against a
  bug where `step` forgets to thread the RNG (a §7 hazard).

### Analytical companion: Aurora dynamics (issue #50, Phase 2)

`docs/FINDINGS_CLASSIFICATION.md` #11 restates the CN-2019 equilibrium
`X_eq = 1 - T_l/T_s`. Two derived properties beyond the equilibrium value:

**Approach time constant.** Linearizing the Aurora RHS around X_eq with
`delta = X - X_eq`:

    d delta / dt = delta * [(1 - 2*X_eq)/T_l - 1/T_s]

Substituting `X_eq = 1 - T_l/T_s` gives

    d delta / dt = delta * (1/T_s - 1/T_l)

so for T_l < T_s (existence condition), delta decays with time constant

    tau = T_l * T_s / (T_s - T_l)

**Collapse in the T_l >= T_s regime.** X = 0 is always a fixed point.
Linear coefficient of the RHS at X = 0 is `1/T_l - 1/T_s`. Stable when
T_l >= T_s; any initial X decays exponentially (or, at the critical
T_l = T_s, sub-exponentially, dominated by the -x^2/T_l term).

**Time symmetry.** X_eq depends only on the ratio T_l/T_s. Rescaling both
times by a common factor stretches the approach but leaves the plateau
identical - the Aurora dynamics are scale-invariant in time.

Tests in `tests/test_aurora_analytical.py` verify: the 1/e decay at
t = tau (linearization tolerance ~5%), scale invariance of X_eq under
common rescaling, linear scaling of tau, exponential collapse when
T_l > T_s, and sub-exponential decay at the critical T_l = T_s.

## shielding

## Where the numbers come from

Every quantity in `shielding` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: g/cm^2 (areal density), cm, kg, rad(Si) (TID), mSv (dose-
equivalent). The shared radiation-environment numbers live in `radenv.py` and are
consumed by both this module and `reliability`.

### Two dose bases, kept distinct (pinned, CLAUDE.md 1)

- **TID for electronics** in rad(Si)/krad(Si) - total ionising dose that degrades chips.
- **Dose-equivalent for biology/risk** in mSv - GCR dose weighted by radiation quality.

These are different physical quantities on different scales and are never mixed.

### Radiation environment (radenv.py, sourced)

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

### Derivations (shown, validated in tests)

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

### `[ESTIMATE]` seams (tagged at use)

- The Jovian TID attenuation length is a single-point fit (above).
- Regolith-vs-metal equivalence uses areal density as a proxy and ignores Z-dependent
  secondary yields; the GCR minimum is quoted for aluminium and used as a regolith proxy.

### GCR non-monotonicity (the anti-nonsense guard)

`gcr_shielding_is_counterproductive` and `recommend_gcr_areal_density` enforce the
20 g/cm^2 minimum: the module will not recommend thicker GCR shielding, because past the
minimum it raises dose. Without this guard a naive "more shielding is safer" model would
produce confident nonsense - the exact failure CLAUDE.md warns about.

### Interface wiring

- **-> closure-sim:** `shield_mass_kg` is a BOM line, but `closure_contribution_kg` marks
  locally-built regolith shielding as mass that RAISES closure (opposite of vitamins).
- **shares radenv with reliability:** `reliability` consumes the same GCR/Jovian dose
  numbers for degradation/mortality, so they are defined once here.
- **<- power-source / mission:** the environment (distance, Jovian vs interplanetary)
  selects which dose numbers apply.

### Further reading (bibliography)

- **Zeitlin et al. 2013** - MSL/RAD transit dose measurements; the 1.8 mSv/day deep-space
  GCR anchor.
- **Slaba et al. / "Optimal shielding thickness for GCR" 2017** - the ~20 g/cm^2 dose-
  equivalent minimum and the secondary-particle build-up beyond it.
- **Juno Radiation Vault / Europa Clipper** - the flight vault masses and attenuation
  anchors.

### Distribution bands (distributions.py)

UQ spreads around the point values above, not new measurements.

- **`GCR_DEEP_SPACE_DOSE_DIST = Uniform(1.5, 2.1)` mSv/day** - `[ESTIMATE]`: spread around the
  1.8 mSv/day MSL RAD value for cruise-condition variation; the 1.5-2.1 band was carried
  over from the earlier code comment with no citation recoverable from this repo.
- **`GCR_DOSE_MIN_AREAL_DENSITY_DIST = Uniform(15, 25)` g/cm^2** - `[ESTIMATE]`: window around the
  ~20 g/cm^2 HZETRN design-point minimum; the width has no citation recoverable from this repo.
- **`JUNO_VAULT_ATTENUATION_DIST = Uniform(500, 1000)`** - `[ESTIMATE]`: ~800x is the design
  target and real attenuation depends on interior geometry; the 500-1000x band was carried
  over from the earlier code comment with no citation recoverable from this repo.
- **`LUNAR_REGOLITH_DENSITY_DIST = Uniform(1.5, 1.8)` g/cm^3** - regolith bulk density varies
  with compaction; the Lunar Sourcebook range quoted above is ~1.5-1.9, so this is a
  sub-band of it.
- **Titanium, aluminium densities, Juno anticipated TID, and the Juno / Europa Clipper vault
  masses** - Fixed (tightly known or flight-measured, as above).

## thermal

## Where the numbers come from

Every quantity in `thermal` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: W, W/m^2, K, m^2, kg. The core is one physical law (Stefan-
Boltzmann); the sourced inputs are emissivity, radiator areal density, and the ISS
flight anchor.

### Physics constant (defined/derived)

- **`STEFAN_BOLTZMANN_W_M2_K4 = 5.670374419e-8`** - Stefan-Boltzmann constant. Fixed by
  the SI defined constants (h, k_B, c); CODATA value. Source:
  https://physics.nist.gov/cgi-bin/cuu/Value?sigma . Verdict: exact (defined).
- **Stefan-Boltzmann law** `q = eps * sigma * T^4` (per emitting face) - standard
  radiative-transfer result. Derived, not hardcoded.

### Radiator inputs (sourced)

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

### ISS flight anchor (External Active Thermal Control System)

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

### The derivations (shown, validated in tests)

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

### Analytical companion (issue #50, #14/#15)

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

### Basis / over-nesting notes (CLAUDE.md 1, 3)

- Per-source radiator temperature is mandatory: a ~300 K electronics radiator and a hot
  smelting radiator differ ~10x per kW, so heat must be binned by process temperature,
  not lumped at one T.
- Deep-space sink taken as ~0 K by default; a planetary-IR/albedo environment enters via
  `sink_temp_k` and the solar-load term. No heat-pipe, two-phase-loop, or CFD solver -
  these are algebraic sizings.

### Interface wiring

- **-> closure-sim:** `radiator_mass_kg` is a new BOM line - heat rejection is no longer
  free; the factory must build (or import) its radiators.
- **<- power-source / power-budget:** the heat load equals the waste power these deliver;
  `power-source` calls `thermal` to size its reactor/array radiator mass.
- **reuses probe-sim:** the 1/d^2 solar law for the parasitic-load term (single source
  of truth for the solar constant).

### Further reading (bibliography)

- **NASA STMD lightweight radiators** - the <=3 kg/m^2 target and the carbon-carbon /
  heat-pipe designs behind it.
- **ISS EATCS documentation (NASA/CBS)** - the 70 kW / 275 K / 70.3 m^2-assembly flight
  anchor that validates the Stefan-Boltzmann sizing.

### Invariants (issue #48, phase B)

`RadiatorResult` is a frozen dataclass with a `__post_init__` postcondition.
Runs in release (never gated).

- **[inv:th-radiator]** `flux_w_m2 > 0` (a radiator always radiates), `area_m2 >= 0`
  and `mass_kg >= 0` (a zero-heat call gives `area = mass = 0`; negative is a bug).

Tests: `tests/test_invariants.py`.

## transfer

## Where the numbers come from

Every quantity in `transfer` traces to a source below, or is derived by explicit math
from ones that do (CLAUDE.md §1). Units: metres, seconds internally; the public API
takes AU and returns days. Orbital radii and Isp are transfer *inputs* (they depend on
the scenario), documented here so a scenario cites one place; only defined/measured
constants are hardcoded.

### Physics constants (hardcoded - defined/measured only)

- **`GM_SUN_M3_S2 = 1.32712440018e20` m^3/s^2** - heliocentric gravitational parameter,
  IAU 2015 nominal solar mass parameter (GM_sun^N). *Defined nominal value.* Source:
  IAU 2015 Resolution B3, https://www.iau.org/static/resolutions/IAU2015_English.pdf .
  Verdict: exact (adopted nominal). This is the one constant the whole Hohmann/Edelbaum
  computation rests on.
- **`AU_M = 1.495978707e11` m** - astronomical unit, IAU 2012 exact definition. Source:
  IAU 2012 Resolution B2 / IAU 2015, https://www.iau.org/static/resolutions/IAU2015_English.pdf .
  Verdict: exact (defined).
- **`SECONDS_PER_DAY = 86400` s** - exact (86400 SI seconds per day).
- **`g0 = 9.80665` m/s^2** - standard gravity, reused from `launch-economics`
  (not redefined here). Turns Isp into exhaust velocity in the SEP thrust and rocket
  equation. Exact by definition (BIPM/SI).

### Reference orbital elements (inputs, not constants)

Heliocentric semi-major axes, AU:
- **Earth 1.0000, Mars 1.5237, Jupiter 5.2034** - NASA Planetary Fact Sheet,
  https://nssdc.gsfc.nasa.gov/planetary/factsheet/ . Verdict: measured, canonical.
- **Ceres / main-belt reference 2.77** - NASA/JPL Small-Body Database,
  https://ssd.jpl.nasa.gov/ . Verdict: measured.

Sidereal orbital periods, days (synodic-cadence inputs):
- **Earth 365.256, Mars 686.980** - NASA Planetary Fact Sheet (as above). Verdict:
  measured.

### Specific impulse (inputs, reused from launch-economics)

- **Chemical Isp ~300-452 s** (LOX/RP-1 ~300-340; LOX/LH2 ~450). Source: already in
  `launch-economics/REFERENCES.md` (Sutton & Biblarz). Used as the chemical baseline in
  the SEP-vs-chemical propellant cross-check.
- **Electric-propulsion Isp ~1500-4190 s** (ion/Hall; NEXT-C 4190 s flown on DART).
  Source: `launch-economics/REFERENCES.md`; NASA NEXT-C, NTRS 20210018563. Used as the
  SEP Isp band.

### Formulas (derived, not hardcoded)

- **Hohmann two-burn Δv and time** - vis-viva; standard result (Curtis, *Orbital
  Mechanics for Engineering Students*, already in the bibliography). `dv1 = v1
  (sqrt(2 r2/(r1+r2)) - 1)`, `dv2 = v2 (1 - sqrt(2 r1/(r1+r2)))`, `t = pi
  sqrt((r1+r2)^3 / (8 GM_sun))`. Derived in `orbits.py`, verified numerically below.
- **Synodic period** `T_syn = 1 / |1/T1 - 1/T2|` - standard result. Derived.
- **Tsiolkovsky mass ratio** `m0/mf = exp(Δv/v_e)` - reused from `launch-economics`
  (`rocket_equation_mass_ratio`), not re-derived here (single source of truth).
- **Edelbaum low-thrust Δv** `Δv = sqrt(V1^2 - 2 V1 V2 cos((pi/2) dtheta) + V2^2)` -
  Edelbaum (1961), *Propulsion Powered by a Photon or Ion Beam...*, ARS Journal
  31(8):1079, https://doi.org/10.2514/8.5723 . For a coplanar (dtheta = 0) circle-to-
  circle transfer this reduces exactly to `Δv = |V1 - V2|`. Verdict: sourced closed
  form.
- **SEP jet-power thrust** `F = 2 eta P / (g0 Isp) = 2 eta P / v_e` - the standard
  jet-power-to-thrust relation `P_jet = F v_e / 2`. Cross-checked against a flown
  system below.
- **SEP available power** `P(d) = P0 * S(d)/S(1 AU) = P0 / d^2` - reuses `probe-sim`'s
  `solar_irradiance_w_m2` (solar constant 1360.8 W/m^2, Kopp & Lean 2011) so the solar
  constant lives in exactly one place. The ratio is the pure inverse-square factor.

### Cross-checks against flown missions (validation anchors)

- **Psyche Hall thruster: ~60 mN/kW.** `F/P = 2 eta/(g0 Isp)` at Isp 1820 s, eta 0.5
  gives 56 mN/kW - within ~7% of the quoted ~60 mN/kW. Source: eoPortal Psyche,
  https://www.eoportal.org/satellite-missions/psyche . Verdict: derivation matches
  flight hardware.
- **Dawn SEP mission: 11.5 km/s total Δv, 0.5-2.55 kW over 1-3 AU.** Confirms the
  1/d^2 SEP power envelope and the km/s-scale mission Δv. Source: NASA NTRS
  20210008613, https://ntrs.nasa.gov/citations/20210008613 . Verdict: envelope check.

### Verified derived targets (recomputed from the constants above; asserted in tests)

- **Earth circular speed** = 29.785 km/s (matches the known ~29.78 km/s).
- **Earth->Mars Hohmann:** dv1 = 2945 m/s, dv2 = 2649 m/s, dv_total = 5.594 km/s;
  t = 258.9 d. Matches textbook (~2.93 km/s dv1, ~259 d). Tolerance ±0.1-0.5%.
- **Earth->Ceres (2.77 AU):** dv_total = 11.18 km/s, t = 472.6 d.
- **Earth->Jupiter:** dv_total = 14.44 km/s, t = 997.6 d (~2.7 yr) - the reason Jupiter
  missions use gravity assists.
- **Same orbit:** dv_total = 0 exactly; t = 182.6 d (half the 1 AU period).
- **Earth-Mars synodic period** = 779.9 d (~2.14 yr).
- **Edelbaum coplanar Earth->Mars** Δv = |V1 - V2| = 5.656 km/s - slightly *above* the
  impulsive Hohmann 5.594 km/s, as expected (a continuous spiral is less efficient than
  a two-burn transfer). The suite asserts `edelbaum_dv >= hohmann_dv_total` for all
  coplanar circle-to-circle cases.
- **SEP power law:** at 2.77 AU, P = 0.130 P0; at 5.2 AU, P = 0.037 P0 (1/d^2).

### Notes on measurement basis (CLAUDE.md §1)

- All Δv here is **heliocentric** (Sun-centred circular-orbit change), NOT the from-LEO
  departure Δv in `launch-economics`' budget table. They are different quantities; a
  scenario must state which it uses. `transfer`'s heliocentric values cross-check the
  heliocentric legs, not the LEO-departure budgets.
- The SEP trip time uses **constant thrust acceleration** at the initial wet mass - a
  documented modelling assumption (the one in Scope), making the estimate a conservative
  upper bound. Real thrusters shed mass and arrive a little sooner. We do not integrate
  the mass loss (that would be a trajectory simulator this module avoids, CLAUDE.md §3).

### Further reading and cross-checks (bibliography)

These ground the module's ideas or cross-check its numbers; they are consolidated in
the project bibliography (`frontend/src/sources.ts`) and not new numbers in the code.

- **Edelbaum 1961** - T. N. Edelbaum (1961). Propulsion Powered by a Photon or Ion
  Beam: Orbit transfer with low-thrust. ARS Journal 31(8):1079-1089. DOI
  10.2514/8.5723. https://doi.org/10.2514/8.5723 . The closed form behind the low-thrust
  spiral Δv and its coplanar reduction to |V1 - V2|.
- **Curtis 2020** - H. D. Curtis. Orbital Mechanics for Engineering Students (4th ed.).
  Butterworth-Heinemann, ISBN 978-0-12-824025-0. The vis-viva derivation behind the
  Hohmann Δv and half-ellipse transfer time.
- **IAU 2015 Resolution B3** - IAU (2015). Nominal solar and planetary conversion
  constants. https://www.iau.org/static/resolutions/IAU2015_English.pdf . The nominal
  GM_sun and the AU definition.

### Invariants (issue #48, phase B)

`HohmannResult` is a frozen dataclass with a `__post_init__` postcondition. Runs
in release (never gated).

- **[inv:tr-hohmann]** `dv_total_m_s >= 0` and `dv_total_m_s == |dv1| + |dv2|`
  (within `1e-9` relative); `transfer_time_days > 0`. `dv1` and `dv2` signs carry
  meaning (departure vs. circularization burn) and are not constrained.

Tests: `tests/test_invariants.py`.

