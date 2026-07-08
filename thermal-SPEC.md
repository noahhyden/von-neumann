# thermal - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. Sixth module from
`ROADMAP-PROPOSAL.md` (after `transfer`, `comms`, `assembly`, `isru`, `propellant`).
Every load-bearing number was recomputed and confirmed, and a **basis error in the
original research was caught and corrected** during that check (see "The sink-temperature
correction" - this is why build-ready specs verify rather than copy).

`thermal` converts a waste-heat load into a radiator area and mass, so heat rejection
stops being free and enters closure-sim's BOM. It closes the project's own gap (FINDINGS:
autonomy far from Earth is "a power-and-cooling problem, not a physics one" - yet no
cooling model exists).

---

## Scope

**Models (pure, deterministic, plain-data - zero pimas imports, no RNG):**
steady-state radiative heat rejection. Core law: net rejection per unit area
`q_net = eps * sigma * (T_rad^4 - T_sink^4)`; required area `A = Q_waste / q_net`;
radiator mass `m = A * areal_density`. Inputs: waste-heat load Q_waste (W), radiator
operating temperature T_rad (K), emissivity, heliocentric distance d (sets T_sink for a
sun-shaded radiator), areal density (kg/m^2).

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3): transient thermal soak / duty
cycling, internal heat-transport plumbing (heat pipes, pumped loops) beyond a
specific-mass allowance, radiator view-factor geometry / self-shadowing, coating
degradation, two-sided vs one-sided panels (folded into the cited areal density). A pure
`simulate(Q_waste, T_rad, eps, d, areal_density) -> {area, mass, q_net}` fold.

---

## Sourced numbers (REFERENCES.md format)

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| 5.670374419e-8 | W/m^2/K^4 | Stefan-Boltzmann constant | CODATA 2022 (NIST) | https://physics.nist.gov/cgi-bin/cuu/Value?sigma= | exact |
| 0.8-0.85 | - | Spacecraft radiator total emissivity | radiator sizing literature | https://www.nss.org/settlement/nasa/spaceresvol2/thermalmanagement.html | measured |
| ~275 (fluid 2-6 C) | K | ISS EATCS ammonia radiator operating temperature | NASA ISS ATCS overview | https://www.nasa.gov/wp-content/uploads/2021/02/473486main_iss_atcs_overview.pdf | measured |
| 500-600 | K | Target band for space fission-power radiators | NASA ESI | https://www.nasa.gov/directorates/spacetech/strg/early-stage-innovations-esi/esi2021/ | measured/target |
| 3.08 (target <=3.0) | kg/m^2 | Ti-water heat-pipe radiator areal density (load-bearing) | AIAA 2024-4937 | https://arc.aiaa.org/doi/10.2514/6.2024-4937 | measured |
| 5.24-10.95 | kg/m^2 | Legacy fission-power radiator areal density range | ResearchGate 382637384 | https://www.researchgate.net/publication/382637384 | measured |
| ~0.90 (0.80-0.97) | fraction | Compute waste-heat fraction (nearly all IT power -> heat) | Verne Global | https://www.verneglobal.com/blog/data-center-waste-heat | measured |
| ~7-8% process efficiency | fraction | LPBF (rest is waste heat) | NCBI PMC8466511 | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8466511/ | measured -> [ESTIMATE] for a generic factory |
| 70 kW; panel 3.33x2.64 m | kW, m | ISS EATCS total heat rejection + geometry (flight anchor) | Wikipedia EATCS | https://en.wikipedia.org/wiki/External_Active_Thermal_Control_System | measured |
| 1361 | W/m^2 at 1 AU | Solar constant (for sink-temperature scaling) | Kopp & Lean 2011 (in repo bib) | https://doi.org/10.1029/2010GL045777 | measured |

---

## The T^4 mass advantage (confirmed)

Radiator specific mass (at 3 kg/m^2 areal density) collapses with operating temperature
because q_net scales as T^4:

| T_rad (K) | q (W/m^2, T_sink~0) | kg/kW rejected |
|---|---|---|
| 275 (ISS-like) | 276 | 10.9 |
| 300 (compute) | 390 | 7.7 |
| 400 | 1234 | 2.4 |
| 550 (fission target) | 4410 | 0.68 |
| 800 (smelting) | 19742 | 0.15 |

Consequence the module MUST honor: compute and most electronics reject at ~300-330 K
(heavy, ~8-11 kg/kW), while smelting/refining rejects at 800+ K (nearly free). A single
platform-wide radiator temperature would be physically wrong and hide the real design
tension - **T_rad must differ per heat source.** ISS flight anchor: at 275 K, 70 kW needs
~254 m^2 (order 100s of m^2, matching real ISS scale).

---

## The sink-temperature correction (caught during verification)

The original research proposed `T_sink(d) = 279 * d^-0.5`. **That is the sun-FACING
blackbody equilibrium** (what a plate pointed at the Sun reaches), not what a radiator
sees. A radiator is deliberately **sun-SHADED** (edge-on / behind a shield). Using the
sun-facing sink makes a 300 K radiator nearly useless at 1 AU (q_net collapses to ~98
W/m^2 because the "sink" is 279 K, almost as hot as the radiator) - which is wrong.

Correct basis: model a **sun-shaded radiator** with `T_sink << T_rad` at all distances
(deep space plus planetary IR / conducted loads, e.g. ~60-150 K), so
`q_net ~ eps * sigma * T_rad^4` (a near-constant floor set by the radiator's own
temperature). Verified q_net at T_rad=300 K: 366 W/m^2 (T_sink 150 K) to 390 W/m^2
(T_sink 60 K) - within ~6% of the floor.

Only under this shaded basis is the "distance-independent radiator-to-array-area ratio"
claim true: `A_rad = Q/q_net`, with q_net ~ constant and `Q = (1-eff)*P_array ~ 1/d^2`
(same as the array's delivered power), so `A_rad/A_array` is nearly constant with
distance. The sun-facing model would falsely blow the ratio up near the Sun. **Document
the sun-shaded basis as a first-class modeling assumption** (CLAUDE.md 1).

---

## Proposed API

```python
def radiator(Q_waste_W: float, T_rad_K: float, emissivity: float,
             distance_au: float, areal_density_kg_m2: float,
             *, sink_model: SinkModel = SUN_SHADED) -> RadiatorResult:
    """Net flux (W/m^2), area (m^2), mass (kg). Sun-shaded sink: T_sink << T_rad."""
```
Pure function of plain floats; no globals, clock, or RNG. Accepts a per-heat-source
T_rad so a platform can sum a hot (smelting) and a cold (compute) radiator separately.

---

## Validation plan (verified targets)

- ISS anchor: 70 kW at T_rad=275 K, eps=0.85 -> ~254 m^2 (order-of-magnitude, matches
  real ISS scale). A 20 W compute load at 300 K -> ~0.05 m^2.
- T^4 advantage: raising T_rad from 300 to 550 K cuts area/mass by ~11x (7.7 -> 0.68
  kg/kW). Assert monotonic decrease with T_rad.
- **Edge: efficiency=1 -> Q_waste=0 -> area=0 and mass=0.** Assert exactly 0.
- **Edge: d -> infinity -> T_sink -> 0 -> q_net -> eps*sigma*T_rad^4 (finite floor);
  area does NOT blow up.** Assert q_net approaches the floor, area stays finite.
- Sink basis: under SUN_SHADED, q_net at 300 K stays within ~6% of the floor at all d
  (366-390 W/m^2); assert the ratio A_rad/A_array is ~distance-independent. A SUN_FACING
  option may exist for comparison but must be labeled and is not the default.
- Per-source temperature: a platform with 20 W compute (300 K) + 1 kW smelting (800 K)
  sizes two radiators; assert the hot one is ~50x lighter per kW than the cold one.

---

## Interface wiring

- **power-budget -> thermal:** power-budget owns the efficiencies and hands thermal the
  waste-heat load `Q_waste = sum_i (1 - eff_i) * P_i` (compute eff~0 so nearly all its
  power is heat; manufacturing per the LPBF figure).
- **probe-sim / swarm / power-source -> thermal:** supply heliocentric distance d (they
  already track 1/d^2 power); d sets the (small, shaded) sink term.
- **thermal -> closure-sim:** returns a radiator mass (area x areal density) that enters
  the BOM as a real subsystem, with material composition feeding the closure fraction -
  heat rejection is no longer free.
- **thermal <- power-source:** reactors dump large waste heat; power-source calls thermal
  to add radiator mass to a reactor's total (the coupling that makes fission's real mass
  higher than its bare-reactor W/kg).

---

## Why it earns a module (barely, correctly)

The rejection physics (T^4, sink term, distance scaling) is genuinely separate from power
*allocation*, and its output (mass) feeds a third module (closure-sim) - the "sibling
with a clean interface" the architecture prefers over fusion. Keep it a pure ~12-number
fold; if it ever needs more, that is the signal it is over-scoping. The verification
catch above (sun-facing vs sun-shaded sink) is exactly the kind of physics inversion that
silently passes a naive test, and is now pinned as a documented basis.
</content>
