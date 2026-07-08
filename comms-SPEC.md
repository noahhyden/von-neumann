# comms - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. Second module from
`ROADMAP-PROPOSAL.md` worked to an implementable spec (after `transfer-SPEC.md`). Every
load-bearing number below was recomputed and confirmed (see "Validation").

`comms` models the achievable downlink data rate of a probe versus distance, from a
two-regime link model. Its payoff is a genuinely new result: a **data-return wall** - a
probe generates bits far faster than a power-limited 1/d^2 link can return them, so
aggregate knowledge saturates at the sum of per-probe rates, not at probe count.

---

## Scope

**Models (pure, deterministic, plain-data functions - zero pimas imports, no RNG):**

1. **Power-limited regime:** `R(d) = k / d^2`, where `k` is a calibration constant fit to
   a real mission anchor and `d` is the Earth-spacecraft range. This falls out of Shannon
   meeting Friis in the power-limited (below-noise) regime: `C = B log2(1 + Pr/(N0 B))`
   with `Pr proportional 1/d^2`, and in the wideband limit `log2(1+x) -> x/ln2`, so
   `C -> Pr/(N0 ln2)` independent of bandwidth, hence `C proportional 1/d^2`.
2. **Rate-limited regime:** `R` clamped at a modem/protocol ceiling `R_max` (the DSOC
   267 Mbps plateau) - near Earth the link is not power-limited, the hardware is.
   `R(d) = min(k/d^2, R_max)`.
3. **Comms as a power draw:** transmit power as a fourth allocation alongside
   manufacturing/compute/housekeeping in `power-budget` (~5% of bus power on real
   missions).
4. **Data-return balance (the wall):** bits generated per probe vs bits/s returnable;
   the backlog grows without bound when generation rate > R(d).

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3):
- No full per-photon link budget (no pointing jitter, PPM slot statistics, atmospheric
  Cn^2, DSN array gain-vs-elevation). The Friis/Shannon derivation lives in REFERENCES to
  justify the 1/d^2 shape; the runtime is one division plus a clamp.
- No DSN scheduling/contention across many spacecraft (a real but separate concern).
- No modulation/coding internals below a single required-Eb/N0 parameter.
- No uplink/commanding, no relay topologies.

---

## Sourced numbers (REFERENCES.md format)

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| Pr = Pt Gt Gr (lambda/4 pi d)^2 | - | Friis transmission (link budget) | radio-engineering standard | https://www.sciencedirect.com/topics/computer-science/friis-equation | exact (physics) |
| C = B log2(1 + S/N) | bit/s | Shannon-Hartley capacity | Shannon-Hartley theorem | https://www.sciencedirect.com/topics/engineering/shannon-capacity | exact (physics) |
| ln2 = -1.59 | dB Eb/N0 | Ultimate (infinite-bandwidth) Shannon power limit | Eb/N0 | https://en.wikipedia.org/wiki/Eb/N0 | exact |
| ~0.7 | dB Eb/N0 @ BER 1e-5 | Practical coded floor (turbo/LDPC, within ~1 dB of Shannon) | JPL CCSDS turbo codes | https://tmo.jpl.nasa.gov/progress_report/42-120/120D.pdf | sourced -> required-Eb/N0 [ESTIMATE] |
| 40 (nominal 160) | bit/s | Voyager 1 downlink now (nominal at launch) | IEEE Spectrum; NASA Voyager telecom | https://spectrum.ieee.org/voyager-1 | sourced |
| 22 / 8420 | W / MHz | Voyager 1 X-band transmit power / frequency | Voyager telecom (Ludwig & Taylor) | https://voyager.gsfc.nasa.gov/Library/DeepCommo_Chapter3--141029.pdf | sourced |
| ~163 | AU | Voyager 1 distance (order-of-magnitude anchor) | IEEE Spectrum | https://spectrum.ieee.org/voyager-1 | sourced |
| 1-2 | kbit/s | New Horizons at Pluto (~32.9 AU); 12 W, 2.1 m dish | Wikipedia / JHU-APL | https://en.wikipedia.org/wiki/New_Horizons | sourced |
| 0.5-6 | Mbit/s | MRO downlink (~0.5-2.7 AU); 100 W TWTA, 3 m antenna | NASA Mars MRO comms | https://mars.nasa.gov/mro/mission/communications/commxband/ | sourced |
| 267 / 25 / 8.3 | Mbit/s | DSOC optical at 0.35 / ~1.5 / ~2.6 AU (267 is the modem ceiling) | phys.org (JPL numbers) | https://phys.org/news/2024-04-nasa-deep-space-optical-communications.html | sourced |
| "rate reduction proportional to inverse square of distance" | - | DSOC 1/d^2 confirmation (primary source) | JPL DSOC first-phase | https://www.jpl.nasa.gov/news/nasas-laser-comms-demo-makes-deep-space-record-completes-first-phase/ | sourced (primary) |
| 4 / 1550 | W avg / nm | DSOC flight laser power / wavelength | NASA Science DSOC | https://science.nasa.gov/photojournal/dsocs-flight-laser-transceiver/ | sourced |
| 10-100 | x | Optical vs RF data-rate advantage (same 1/d^2 shape, larger k) | JPL DSOC | https://www.jpl.nasa.gov/news/nasas-laser-comms-demo-makes-deep-space-record-completes-first-phase/ | sourced |
| ~4.7-4.9 | % of bus power | Comms transmit fraction (Voyager 22/470; NH 12/245) - derived | derived from sourced W figures | (derivation) | derived |

Distance basis is the **Earth-spacecraft range**, NOT heliocentric distance (they differ
by up to ~2 AU near Earth). Pin this per CLAUDE.md 1 - `probe-sim`/`power-source` use
heliocentric; `comms` uses Earth-range.

---

## The math and calibration

Two regimes: `R(d) = min(k / d^2, R_max)`. The calibration constant `k = R * d^2` is fit
to a real mission anchor per band (RF vs optical are different k, same shape).

**Verified DSOC optical calibration** (Earth-range in AU):
- 25 Mbps at 1.506 AU -> k = 56.7 Mbps*AU^2
- 8.3 Mbps at 2.582 AU -> k = 55.3 Mbps*AU^2

The two anchor points agree to ~2.5%, confirming the 1/d^2 law (rate ratio 25/8.3 = 3.01
vs distance-ratio-squared (240/140)^2 = 2.94). Adopt **k_optical ~ 56 Mbps*AU^2** with
`R_max = 267 Mbps`. RF gets its own k from a Voyager/MRO fit.

---

## Proposed API

```python
def data_rate_at(distance_au: float, *, k_mbps_au2: float, r_max_mbps: float) -> float:
    """Downlink rate (Mbps) at Earth-range distance: min(k/d^2, r_max)."""

def calibrate_k(rate_mbps: float, distance_au: float) -> float:
    """Fit the power-limited constant k from a real mission anchor (k = R * d^2)."""

def return_backlog(generated_bits_per_s: float, distance_au: float, duration_s: float,
                   *, k_mbps_au2: float, r_max_mbps: float) -> BacklogResult:
    """Bits generated vs returned over a duration; positive backlog = the data-return wall."""
```
Pure functions of plain floats; no globals, clock, or RNG.

---

## Validation plan (verified targets)

Power-limited regime and calibration:
- DSOC 25 vs 8.3 Mbps reproduces 1/d^2 to ~2.5% (the built-in anchor). Assert
  `calibrate_k` returns 55-57 Mbps*AU^2 for both DSOC points.
- Voyager-class inputs (22 W X-band, 163 AU, 70 m dish) land in the tens-of-bit/s order
  of magnitude. Assert order-of-magnitude, not exact (RF k differs).

Rate-limited regime (the reason the clamp exists, verified):
- At 0.35 AU the uncapped law predicts ~456 Mbps but the real cap is 267 Mbps -> assert
  `data_rate_at(0.35) == r_max`, not 456. This is the power-limited/rate-limited crossover.
- Crossover distance: `d_cross = sqrt(k / R_max)`; assert the two regimes meet there
  (for k=56, R_max=267: d_cross ~ 0.46 AU).

Edges:
- d -> infinity => R -> 0 (power-limited branch). Assert monotone decreasing beyond
  d_cross.
- d -> 0 => R clamps at R_max, does not blow up. Assert.

The data-return wall:
- When generated bits/s > R(d), backlog grows without bound; assert `return_backlog`
  reports a positive, growing backlog and that aggregate return across N probes saturates
  at sum(R(d_i)), independent of N once each link is saturated.

---

## Interface wiring

- **-> power-budget:** comms is a fourth power draw (transmit power ~5% of bus power,
  verified from Voyager/NH). power-budget allocates; comms converts allocated watts to a
  link and thus to bits/s.
- **parallel to probe-sim:** `data_rate_at(distance)` mirrors `probe-sim`'s
  `solar_irradiance_w_m2` / `compute_headroom_at` - a third 1/d^2 curve on the same
  distance axis (power, compute, now data rate). Same shape, clean seam.
- **compose with swarm (do NOT fuse):** swarm's `coordination="lightspeed"` is *latency*
  (a settled star is believed settled only at `settled_year + dist/c`). comms is
  *throughput* (how many bits/s arrive once they can). They compose: swarm says info
  cannot arrive before dist/c; comms says it then trickles at R(d). A future coupling
  (swarm's news carries a finite bit budget) is a later slice, not this module.
- **band selection:** RF vs optical are the same 1/d^2 law with different k (10-100x) and
  a hard pointing/availability caveat for optical - a selectable parameter, not two
  modules.

---

## Why this is a strong second build

Unusually well-anchored: real-mission data spans ~7 orders of magnitude with a
primary-source 1/d^2 confirmation (JPL), a built-in two-point calibration that agrees to
2.5%, and a verified modem-ceiling crossover. It reuses `probe-sim`'s 1/d^2 pattern, adds
one clean draw to `power-budget`, composes cleanly with `swarm`'s latency layer, and its
runtime is one division plus a clamp - no link-budget engine. It opens a genuinely new
wall (data return) with the anchors to ground it.
</content>
