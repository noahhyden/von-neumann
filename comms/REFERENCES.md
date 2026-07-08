# Where the numbers come from

Every quantity in `comms` traces to a source below, or is derived from ones that do
(CLAUDE.md §1). Distance is the **Earth-spacecraft range** in AU (not heliocentric -
they differ by up to ~2 AU near Earth; pinned per CLAUDE.md §1). Rates in Mbit/s.

## The 1/d^2 law (physics, derived - not assumed)

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

## Primary-source confirmation of the shape

- **DSOC 1/d^2 confirmed by JPL:** "rate reduction proportional to inverse square of
  distance." NASA/JPL DSOC first-phase release,
  https://www.jpl.nasa.gov/news/nasas-laser-comms-demo-makes-deep-space-record-completes-first-phase/ .
  Verdict: sourced (primary). This is the same inverse-square gate `probe-sim` uses for
  power - now for data rate.

## Calibration anchors (DSOC optical, Earth-range AU)

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

## Order-of-magnitude anchors (span ~7 orders; RF has its own k)

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

## Comms as a power draw (derived)

- **Transmit power ~4.7-4.9% of bus power.** Derived: Voyager 22 W / ~470 W bus;
  New Horizons 12 W / ~245 W. Verdict: derived from the sourced W figures above; feeds
  `power-budget` as a fourth allocation (~5% of bus power).

## Verified targets (asserted in tests)

- `calibrate_k` returns 56.7 and 55.3 for the two DSOC anchors (agree to <3%).
- Power-limited branch reproduces both DSOC points to ~2% with k=56.
- At 0.35 AU the uncapped law gives ~457 Mbps but `data_rate_at` returns exactly the
  267 Mbps cap (the rate-limited crossover).
- `crossover_distance_au(56, 267) = 0.458 AU`, and the two regimes meet there.
- d -> infinity => R -> 0 (monotone); d -> 0 => R clamps at R_max (no blow-up).
- The data-return wall: generation above the link rate accumulates unbounded backlog;
  fleet aggregate return = sum of per-probe link rates, not probe count.

## Notes on basis and boundaries

- **Earth-range, not heliocentric.** `probe-sim`/`power-source` use heliocentric
  distance; `comms` uses Earth-spacecraft range. A scenario must not mix them.
- **Throughput, not latency.** This is bits/s once they can flow. `swarm`'s
  light-speed `coordination="lightspeed"` is the *latency* layer (news arrives no
  sooner than dist/c). They compose; they do not merge (comms-SPEC.md).
- No per-photon link budget, no DSN scheduling/contention, no modulation/coding
  internals - the runtime is one division plus a clamp (over-nesting guard, CLAUDE.md §3).

## Further reading (bibliography)

- **Shannon 1948** - C. E. Shannon. A Mathematical Theory of Communication. Bell System
  Technical Journal 27. The capacity theorem behind the power-limited derivation.
- **JPL DSOC 2024** - NASA/JPL Deep Space Optical Communications first-phase results
  (links above). The primary source for the 1/d^2 confirmation and the calibration
  anchors.
