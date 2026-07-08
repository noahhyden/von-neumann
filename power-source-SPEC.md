# power-source - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. Seventh module from
`ROADMAP-PROPOSAL.md` (after `transfer`, `comms`, `assembly`, `isru`, `propellant`,
`thermal`). Every load-bearing number was recomputed and confirmed (see "Validation").

`power-source` selects the minimum-mass power source (solar / RTG / fission) for a given
distance and power level, and returns its mass. It supplies the total available power
that `power-budget` currently assumes as an input, and it surfaces a new "vitamin"-style
wall: Pu-238 supply.

---

## Scope

**Models (pure, deterministic, plain-data - zero pimas imports, no RNG):** given
heliocentric distance d, required delivered electrical power P_req, and mission duration,
select the minimum-mass source among {solar array, RTG, fission reactor} and return its
mass plus the crossover boundaries. Applies 1/d^2 to solar and 0.79 %/yr decay to RTGs.

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3): reactor neutronics,
thermodynamic/Stirling cycle internals, solar-cell device physics, launch trajectory.
Specific powers enter as cited parameters. Radiator sizing is **delegated to `thermal`**,
not re-derived here.

---

## Sourced numbers (REFERENCES.md format)

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| 1361 | W/m^2 at 1 AU | Solar irradiance (scales 1/d^2) | Kopp & Lean 2011 (in repo bib) | https://doi.org/10.1029/2010GL045777 | measured |
| 100-120 | W/kg | ROSA system-level specific power (full wing) | Redwire ROSA flysheet | https://rdw.com/wp-content/uploads/2023/06/redwire-roll-out-solar-array-flysheet.pdf | sourced |
| 75.3 | W/kg | iROSA flight-unit BOL (conservative flight basis) | eoPortal ISS-ROSA | https://www.eoportal.org/satellite-missions/iss-rosa | sourced |
| 218 / 400 | W/kg | ROSA blanket / advanced flexible blanket (component, not wing) | ISS ROSA experiment paper | https://www.researchgate.net/publication/329511362 | [ESTIMATE] (future arrays) |
| 110-125 W; ~45 kg; 2.8 We/kg; 4.8 kg PuO2 | mixed | MMRTG (Curiosity/Perseverance) | NASA RPS FAQ | https://science.nasa.gov/planetary-science/programs/radioisotope-power-systems/faq/ | sourced |
| 300 W; 57 kg; 5.2 We/kg; 8.1 kg Pu-238 | mixed | GPHS-RTG (Voyager/Cassini/New Horizons) | Wikipedia GPHS-RTG; World Nuclear | https://en.wikipedia.org/wiki/GPHS-RTG | sourced |
| 157 W; 37.7 kg; 4.16 We/kg | mixed | MHW-RTG (Voyager) | Wikipedia MHW-RTG | https://en.wikipedia.org/wiki/MHW-RTG | sourced |
| 0.57 (metal) / ~0.5 (oxide) | W/g thermal | Pu-238 specific thermal power (basis matters) | Wikipedia Pu-238 | https://en.wikipedia.org/wiki/Plutonium-238 | sourced |
| 87.7 yr; 0.79 %/yr | half-life; decay | Pu-238 half-life; decay = ln2/87.7 (derived) | Wikipedia Pu-238 | (as above) | sourced + derived |
| 134 kg; 28 kg U-235; ~5.5 kWt | mixed | KRUSTY / 1 kWe Kilopower prototype | Wikipedia Kilopower; OSTI 1648084 | https://www.osti.gov/pages/biblio/1648084 | sourced |
| 2.5-6.5 (10 kWe: 6.67) | We/kg | Kilopower design specific-power range (incl. shield/conversion) | NTRS 20205008482 | https://ntrs.nasa.gov/citations/20205008482 | sourced |
| 40 kWe; goal <6000 kg (6.67); actual ~10000 kg (4.0) | mixed | NASA Fission Surface Power lunar reactor | NTRS 20220004670 | https://ntrs.nasa.gov/citations/20220004670 | sourced |
| ~0.4-0.5 now; 1.5 goal; up to 5 capacity | kg/yr | Pu-238 production (ORNL/INL) | DOE/ORNL | https://www.energy.gov/ne/articles/oak-ridge-national-laboratory-automates-key-process-plutonium-238-production | sourced |
| ~8-15 | yr | Design life (FSP ~8, Kilopower ~12-15) - varies by doc | NTRS FSP/Kilopower | (as above) | [ESTIMATE] |

Measurement-basis landmine (CLAUDE.md 1): solar W/kg spans 4x (flight wing ~75 vs blanket
~400); d_cross scales as its square root, so a 4x solar error is a 2x distance error.
Default to conservative flight system-level; expose the optimistic blanket value as a
labeled scenario.

---

## The two crossovers (confirmed)

**By distance:** solar mass `= P*d^2/sp_solar`, nuclear mass `= P/sp_nuclear`. Setting
equal, **P cancels**:
```
d_cross = sqrt(sp_solar_1AU / sp_nuclear)
```
Verified: 100 W/kg solar vs 5.2 We/kg GPHS-RTG -> 4.39 AU; vs 6.7 We/kg fission -> 3.86
AU; vs 2.8 We/kg MMRTG -> 5.98 AU. Central ~4-5 AU, matching reality (Juno runs solar at
the 5.2 AU record; everything beyond switches to RTG). P-cancellation confirmed: at
d_cross, m_solar == m_nuclear for P = 100 W (19.2 kg), 1 kW (192 kg), and 40 kWe (7692 kg).

**By power level:** RTGs have no mass floor but low, Pu-238-capped specific power
(2.8-5.2 We/kg); fission has a hard ~130 kg floor (KRUSTY) but specific power rises with
scale (2.5 -> 6.7 We/kg from 1 to 40 kWe). Below ~1 kWe an RTG wins; above, fission.

**The Pu-238 vitamin wall:** decay 0.79 %/yr (= ln2/87.7); one GPHS-RTG's 8.1 kg is
5.4-20 years of world production (at 1.5 / 0.4 kg/yr) - a hard fleet-scale throttle,
exactly like closure-sim's electronics vitamins.

---

## Proposed API

```python
def select_source(distance_au: float, power_req_W: float, duration_yr: float,
                  *, sp_solar_1AU_W_kg: float, sources: Sequence[SourceSpec]) -> SourceChoice:
    """Minimum-mass source + mass; applies 1/d^2 (solar) and 0.79%/yr decay (RTG)."""

def crossover_distance(sp_solar_1AU: float, sp_nuclear: float) -> float:
    """d_cross = sqrt(sp_solar / sp_nuclear)."""

def pu238_required(power_W: float) -> float:
    """Pu-238 mass (kg) for an RTG delivering power_W -> a vitamin-style constraint."""
```
Pure functions of plain data; deterministic; no globals, clock, or RNG.

---

## Validation plan (verified targets)

- d -> 0: solar mass -> 0, solar always wins. Assert.
- d -> large: solar mass -> infinity, nuclear wins. Assert.
- `crossover_distance` matches the closed form and is finite, positive, monotonic in
  sp_solar and 1/sp_nuclear. Assert 100/5.2 -> 4.39 AU.
- P-cancellation: at d_cross, m_solar == m_nuclear for any P_req (assert across 100 W,
  1 kW, 40 kWe).
- Power-level boundary: at ~100 W selection = RTG; at 40 kWe beyond the belt = fission.
  Assert the boundary is finite.
- Decay: an RTG delivers >= P_req after 0.79 %/yr decay over the full duration; assert
  end-of-life power meets the requirement (or the source is rejected).
- Pu-238 wall: `pu238_required` for a GPHS-class RTG returns ~8 kg; assert it exceeds a
  year of production (the throttle exists).

---

## Interface wiring

- **-> power-budget:** emits the total available delivered power (after 1/d^2 and RTG
  decay) that power-budget then splits - the natural upstream producer of the number
  power-budget currently assumes.
- **-> closure-sim:** emits power-plant mass as a BOM line item (solar array kg or
  RTG/reactor kg), making the power plant a real closure entry.
- **reuses probe-sim:** imports the same 1/d^2 solar law and 1361 W/m^2 constant (single
  source of truth; do not duplicate).
- **calls thermal:** reactors dump large waste heat (FSP 40 kWe implies ~100s kWt);
  power-source calls `thermal`'s radiator sizing to add radiator mass to a reactor's
  total. This coupling is what makes fission's real mass exceed its bare-reactor W/kg.
- **Pu-238 -> closure-sim / launch-economics:** expose Pu-238 kg per unit as a
  vitamin-style constraint that throttles RTG-based replication rate.

---

## Why it earns a module

It answers a different question than power-budget (which given P decides the split): this
answers, given d and P, what P is even available and at what mass. Clean seam, two elegant
crossovers, natural interfaces to three existing modules plus a vitamin-wall tie-in. Guard
against neutronics/Stirling nesting (specific power stays a cited parameter; the reactor
is a mass/power/heat black box) and keep the radiator coupling a call into `thermal`,
never inlined.
</content>
