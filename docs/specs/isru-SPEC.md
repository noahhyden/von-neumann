# isru - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. Fourth module from
`ROADMAP-PROPOSAL.md` worked to an implementable spec (after `transfer`, `comms`,
`assembly`). Every load-bearing number below was recomputed and confirmed (see
"Validation").

`isru` derives closure-sim's currently hand-set build energy (~5 kWh/kg) and its closure
*ceiling* from regolith physics: the mass-and-energy conversion from raw regolith to
usable feedstock (structural metal, oxygen). It replaces two *assumed* closure-sim inputs
with *derived, sourced* ones.

---

## Scope

**Models (pure, deterministic, plain-data - zero pimas imports, no RNG):** a mass-balance
plus energy-sum. Given (a) a body composition (oxide/metal/volatile wt%), (b) an ore
grade / beneficiation recovery, and (c) a chosen route, it computes:
- kg feedstock (metal, O2) per kg regolith excavated, and
- total kWh per kg feedstock = excavation + beneficiation + reduction/electrolysis
  (+ liquefaction for propellant-grade O2).

Two internal stages with a documented seam (excavate -> beneficiate/refine); one module,
not two (excavation energy is negligible - see Validation).

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3): reactor thermodynamics/CFD,
bubble dynamics, electrode chemistry, thermal management, batch scheduling, dust
mitigation, equipment wear. These enter as *parameters* (current efficiency, recovery
fraction, specific energy) cited to the literature. It does not model chip/electronics
feedstock (those stay vitamins in closure-sim) and it does not make *propellant* (that is
the proposed `propellant` module - different feedstock, water ice vs regolith).

---

## Sourced numbers (REFERENCES.md format)

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| ~45 | wt% | Oxygen bound in lunar regolith oxides (extractable ceiling) | PNAS 2025 | https://pmc.ncbi.nlm.nih.gov/articles/PMC11874342/ | sourced |
| SiO2 ~45; Al2O3 11-26; FeO 5-20; CaO 8-17; MgO 4-10; TiO2 0.5-8 | wt% | Lunar regolith oxide composition (highland-mare range) | oxide-abundance review | https://www.sciencedirect.com/science/article/pii/S009457652500284X | sourced |
| 24.3 +/- 5.8 | kWh/kg LOX | Full-chain lunar oxygen (10 wt% ilmenite, H2 reduction + electrolysis + liquefaction) | PNAS 2025 | https://pmc.ncbi.nlm.nih.gov/articles/PMC11874342/ | sourced |
| H2 reduction 13.4; electrolysis 9.2; liquefaction 1.17; excav/transport/benef <0.5 | kWh/kg LOX | Step breakdown of the 24.3 - refining dominates, excavation negligible | PNAS 2025 | https://pmc.ncbi.nlm.nih.gov/articles/PMC11874342/ | sourced |
| 8.26 | kWh/kg H2O | Water electrolysis step | PNAS 2025 | https://pmc.ncbi.nlm.nih.gov/articles/PMC11874342/ | sourced |
| 6.5e-6 / 0.022 / 0.86 | kWh/kg regolith | Excavation specific energy (PNAS / bucket-drum continuous / batch) | PNAS 2025; arXiv 2511.00492 | https://arxiv.org/pdf/2511.00492 | sourced |
| 1-2 (900 C); 3.4 (1000 C); 4.4 (1100 C); ~10.5 theoretical | wt% O2 | O2 yield per kg regolith (H2 reduction, ilmenite-limited) | Planet. & Space Sci. | https://www.sciencedirect.com/science/article/abs/pii/S0032063319301813 | sourced |
| 50.5% ilmenite recovery; ~50% reactor conversion | fraction | Beneficiation / conversion yields | PNAS 2025 | https://pmc.ncbi.nlm.nih.gov/articles/PMC11874342/ | sourced |
| ~55.8 | kWh/kg (metal+O2) | MRE ferrosilicon plant, system-level (produces structural metal) | MRE plant modeling; NTRS 20240013999 | https://ntrs.nasa.gov/citations/20240013999 | sourced |
| 4 (industrial); 2.8-3.35 (lab) | kWh/kg iron/steel | Molten oxide electrolysis metal (terrestrial proxy for in-situ metal) | Boston Metal / MIT | https://news.mit.edu/2024/mit-spinout-boston-metal-makes-steel-with-electricity-0522 | [ESTIMATE] (terrestrial proxy) |
| CI up to ~20; CM 3-14 (C-type) | wt% water | Asteroid volatile content | CM chondrite; asteroid econ arXiv 1810.03836 | https://arxiv.org/pdf/1810.03836 | sourced (composition) |
| ~91 Fe / 7 Ni / 0.6 Co (metal asteroid) | wt% | M-type asteroid metal content | M-type asteroid | https://en.wikipedia.org/wiki/M-type_asteroid | sourced (composition) |
| in-situ metal / asteroid extraction energy in microgravity | kWh/kg | Actual ISRU extraction energy off-Earth | no flight-validated value | - | **[GAP]** -> use MOE proxy, tag [ESTIMATE] |
| 5 (hand-set) | kWh/kg | closure-sim's current ASSUMED build energy - the number isru replaces | repo | (repo) | assumed (to be retired) |

Measurement-basis note (CLAUDE.md 1): PNAS 24.3 is *delivered electrical* energy per kg
LOX at 10 wt% ilmenite; NASA's 26.4-420 envelope reflects different system boundaries/TRLs.
Pin the basis in REFERENCES.md - this is exactly the basis trap the rules warn about.

---

## The derivation (confirmed)

- Full oxygen chain sums to 24.27 kWh/kg LOX (matches PNAS 24.3): H2 reduction 55% +
  electrolysis 38% = 93% refining; excavation ~2%. Refining dominates by ~27x+.
- The invariant closure-sim depends on survives every route: in-situ metal is ~4 kWh/kg
  (MOE proxy) or ~55.8 kWh/kg (MRE system); chips are 8000 kWh/kg, so chips/metal is
  2000x (MOE) or 143x (MRE) - always >100x. **The electronics wall is preserved
  regardless of which metal route is chosen**, and closure-sim's hand-set 5 kWh/kg sits
  right beside the derived MOE 4 kWh/kg.
- O2 mass yield 1.5-4.4 wt% -> 23-67 kg regolith processed per kg O2.

---

## Proposed API

```python
def feedstock_yield(composition: BodyComposition, ore_grade: float,
                    route: Route) -> YieldResult:
    """kg feedstock (metal, O2) per kg regolith; + tailings (mass-balanced)."""

def feedstock_energy(route: Route, *, liquefy: bool = False) -> float:
    """kWh per kg feedstock = excavation + beneficiation + reduction/electrolysis (+ liquefaction)."""

def local_feedstock_fraction(composition: BodyComposition,
                             required_elements: Sequence[str]) -> Mapping[str, float]:
    """Per-element locally-sourceable fraction = recovery x conversion; 0 if body lacks it."""
```
Pure functions of plain data; no globals, clock, or RNG.

---

## Validation plan (verified targets)

- Nominal: 10 wt% ilmenite mare regolith, H2-reduction route -> `feedstock_energy` within
  PNAS 24.3 +/- 5.8 kWh/kg LOX; O2 yield within 1-5 wt%.
- Mass balance (conservation): `kg(feedstock) + kg(tailings) == kg(regolith)` exactly.
- Metal-vs-chip invariant: MOE metal route returns O(1-10) kWh/kg and MRE O(50); assert
  chips/metal > 100x for every route (the electronics wall must survive).
- closure-sim consistency: the derived metal build energy (~4-5 kWh/kg) reproduces
  closure-sim's hand-set ~5 within its band - assert isru's output can replace the
  constant without changing closure-sim results by more than the sourced uncertainty.
- Edges:
  - ore-grade -> 0: extractable fraction -> 0, feedstock/kg -> 0, kWh/kg feedstock ->
    infinity (flagged infeasible), NOT a silent finite number.
  - energy-limited: given a power cap from power-budget, feedstock throughput ==
    power / (kWh per kg); -> 0 as power -> 0.
  - element absent on body (`composition[el] == 0`): `local_feedstock_fraction[el] == 0`
    (that mass reverts to vitamin in closure-sim).

---

## Interface wiring

- **-> power-budget:** a single scalar `energy_kwh_per_kg_feedstock` per feedstock type -
  precisely the `energy_to_produce_kwh_per_kg` closure-sim currently hand-sets to 5.
  power-budget supplies it from the manufacturing power share.
- **-> closure-sim:** a `local_feedstock_fraction` per element (recovery x conversion)
  plus a "sourceable at all?" boolean that can *cap* each subsystem's `producible_locally`
  flag - if a needed element is absent, that mass reverts to vitamin.
- **feeds assembly / structures (proposed):** isru's feedstock types are the inputs
  `structures` tests for strength and `assembly` builds into parts. Firm seam: isru stops
  at feedstock; those modules take it from there.
- Data-only interface (dataclass/pydantic), no reach-in; closure-sim keeps its closure
  math, isru just feeds the two numbers it currently assumes.

---

## Two honesty guards

1. **Asteroid tier is [ESTIMATE], lunar tier is solid.** The lunar oxygen chain (PNAS
   24.3) is the trustworthy core to build first. In-situ *metal* and *asteroid* extraction
   energy have no flight-validated value; the terrestrial MOE 4 kWh/kg is a defensible
   proxy but microgravity/vacuum differ - ship it tagged [ESTIMATE]/[GAP], never as
   measured fact. Enforce the "solid first tier / tagged second tier" split.
2. **Closure changes asymmetrically.** isru does not redefine closure (a mass concept),
   but it sets the *ceiling* (composition) and adds the *energy tax* power-budget must
   carry. The honest contribution: "closure is enabled, at ~24 kWh/kg for oxygen and ~4
   for metal, both of which power-budget pays" - not "closure is now higher."

---

## Why this belongs in Tier 1

It retires one of closure-sim's core assumed inputs (build energy) with a peer-reviewed
full-chain figure, and it does so while *preserving* the project's flagship electronics-
wall finding (chips stay >100x any metal route). The math is a mass-balance plus an
energy-sum with a clean two-number seam to closure-sim and power-budget, an explicit
lunar-solid / asteroid-estimate split, and a documented boundary against a plant
simulator and against the `propellant` module.
</content>
