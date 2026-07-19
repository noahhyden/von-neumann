# Where the numbers come from

Every quantity in `assembly` traces to a source below, or is derived from ones that do
(CLAUDE.md §1). Units: kg, hours, days. This module derives a number that `closure-sim`
and `multi-probe` currently take as a hand-set input, so the whole point is to replace
assumption with sourced derivation - and to be honest that the result is an `[ESTIMATE]`
band, not a point.

## Why the whole result is `[ESTIMATE]`

No self-replicating space factory has ever been built, so there is no measured space
build rate. Every input below is a **terrestrial** metal-AM or manufacturing figure used
as a proxy. That is a legitimate `[ESTIMATE]` (documented proxy), not a measured fact -
tagged here and at the use site. The honest output is a band spanning >10x, not a single
number.

## Deposition rates, kg/h (metal additive manufacturing)

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

## Overall Equipment Effectiveness (duty_cycle x yield)

- **World-class OEE = 0.85.** `WORLD_CLASS_OEE`. Seiichi Nakajima's TPM benchmark, built
  from availability >=0.90, performance >=0.95, quality >=0.999. Source:
  https://www.leanproduction.com/oee/ . Verdict: sourced, canonical.
- **World-class quality (first-pass yield) = 0.999.** `WORLD_CLASS_QUALITY`. The quality
  component of the 0.85 benchmark (same source). Used as the yield factor.
- **Typical manufacturing OEE ~0.60** (discrete-manufacturing average ~66.8%). Source:
  https://www.leanproduction.com/oee/ ; industry benchmark aggregates. Verdict: sourced.
  Used for the conservative low end of the band.

## NASA AASM upper anchor (whole-factory rate)

- **100-tonne seed factory copies itself in 1 year -> ~274 kg/day.** `AASM_SEED_MASS_KG
  = 100000`, `AASM_SELF_COPY_DAYS = 365`; 100000/365 = 273.97 kg/day (derived). Source:
  R. Freitas & W. Gilbreath (eds.), *Advanced Automation for Space Missions*, NASA
  Conference Publication 2255 (1982), the self-replicating lunar factory concept. NTRS
  https://ntrs.nasa.gov/citations/19820045716 ; full text
  https://nss.org/wp-content/uploads/1982-Self-Replicating-Lunar-Factory.pdf ; summary
  http://www.rfreitas.com/Astro/AASMJAS1982.htm . Verdict: sourced (primary NASA
  concept). This is the aggressive whole-factory upper bound - a documented design point,
  not an invented number.

## The derivation (shown, not assumed)

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

## Verified targets (asserted in tests)

- The derivation equals its product; anchor = 20.4 kg/day (within 3% of the 20 it
  retires); AASM implied rate = 273.97 kg/day; the band brackets the anchor and is >10x
  wide; copy_time reproduces 582 days for the lunar seed and 42.5 days at the NASA rate;
  build rate scales linearly in manipulators; copy time scales with closure.

## Interface wiring

- **-> closure-sim / multi-probe:** `machinery_build_rate_kg_per_day(...)` supplies the
  `local_build_rate_kg_per_day` input both currently hand-set to 20. The band means a
  scenario should carry the rate as a range, and the doubling clock inherits that range.
- **copy-time seam:** `copy_time_days` is `multi_probe.time_to_build_one_copy_days` in
  the machinery-bound regime, reproduced (not re-invented) so this module can show its
  rate setting the clock. No dependency on multi-probe is taken (assembly stays pure and
  independently runnable); the shared formula is the clean seam.
- **feedstock seam:** the deposition rate assumes feedstock is available; `isru` sizes
  the energy to make that feedstock. Kept separate (over-nesting guard, CLAUDE.md §3).

## Further reading (bibliography)

- **Freitas & Gilbreath 1982** - Advanced Automation for Space Missions, NASA CP-2255.
  The self-replicating lunar factory and its 100 t/yr self-copy - the field's founding
  quantitative concept and this module's upper anchor.
- **Nakajima 1988** - S. Nakajima, *Introduction to TPM: Total Productive Maintenance*.
  The origin of the 85% world-class OEE benchmark used for duty_cycle x yield.

## Invariants (issue #48, phase B)

`BuildRateBand` is a frozen dataclass with a `__post_init__` postcondition. Unlike
the fold-module assertions, this one runs in release too (no `if __debug__:`): a
band that violates it is a malformed value that callers must not silently see.

- **[inv:as-band]** `low_kg_per_day > 0` and `low_kg_per_day <= anchor_kg_per_day
  <= high_kg_per_day`. Uncertainty bands must be well-formed.

Tests: `tests/test_invariants.py`.
