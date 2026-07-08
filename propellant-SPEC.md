# propellant - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. Fifth module from
`ROADMAP-PROPOSAL.md` worked to an implementable spec (after `transfer`, `comms`,
`assembly`, `isru`). Every load-bearing number below was recomputed and confirmed (see
"Validation").

`propellant` models the seam between `transfer` (which emits a Delta-v) and `isru` (which
makes feedstock for parts, not reaction mass). It owns a genuinely new concept:
**propellant closure** - a distinct axis from parts-closure. Water/O2 routes reach
closure 1.0 on a water-bearing body; noble-gas electric propulsion is a hard import wall.

---

## Scope

**Models (pure, deterministic, plain-data - zero pimas imports, no RNG):**

1. **Propellant mass per hop** = `dry_mass * (exp(Delta_v / (Isp*g0)) - 1)` - the rocket
   equation (reuses `launch-economics`), with Delta_v from `transfer` and Isp by
   propulsion type.
2. **In-situ production energy** = `propellant_kg * specific_energy(route)`, route in
   {water-electrolysis-to-cryo (~10 kWh/kg full chain), MRE-oxygen (~24 kWh/kg O2),
   liquefaction adders}. A draw on `power-budget`.
3. **Propellant closure fraction** = locally-sourceable propellant / total propellant. A
   vector, distinct from parts-closure: water/O2 local; noble gases and iodine imported.

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3): thruster/plasma physics,
ionization, beam divergence, combustion chemistry, cryo boil-off dynamics, or
extraction-robotics. These enter only as parameters (Isp, specific energy, extraction
yield).

---

## Sourced numbers (REFERENCES.md format)

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| 4.41 | kWh/kg propellant | Water electrolysis energy (thermodynamic HHV min; derived) | Kornuta et al. 2019; derived from dH=285.8 kJ/mol | https://www.osti.gov/servlets/purl/1503160 | derived + cited |
| ~10.0 (2.8 MW / 2450 t/yr) | kWh/kg water | Full-chain lunar propellant plant (extraction+electrolysis+liq) | Kornuta et al. 2019 | https://www.sciencedirect.com/science/article/abs/pii/S2352309318300099 | cited + derived |
| 11.3 | kWh/kg LOX | Full-subsystem LOX (water route, ancillaries incl.) | NASA NTRS ICES-2024 | https://ntrs.nasa.gov/api/citations/20240005576 | cited |
| 13-15 (min 2.9) | kWh/kg LH2 | Cryogenic H2 liquefaction (terrestrial SoA; theory min) | ScienceDirect 2023 | https://www.sciencedirect.com/science/article/pii/S1364032123000606 | cited |
| LOX liquefaction energy | kWh/kg O2 | Lower than H2 (90 K vs 20 K) but no clean space-ISRU figure isolated | - | - | **[GAP]** (parameter) |
| 5.6 +/- 2.9 | wt% H2O | Lunar polar (Cabeus PSR) ice concentration - feedstock grade | LCROSS, NASA NSSDCA | https://nssdc.gsfc.nasa.gov/planetary/ice/ice_moon.html | cited |
| 3-22 (CI ~20) | wt% H2O | Carbonaceous chondrite water content - asteroid feedstock | Wikipedia; Lee 2023 MAPS | https://onlinelibrary.wiley.com/doi/10.1111/maps.14099 | cited |
| 280-452 | s Isp | Chemical (LOX/RP-1 ~280-340; LOX/LH2 ~450) | already in launch-economics/REFERENCES.md | (repo) | cited |
| 1500-4190 | s Isp | Electric-propulsion band | launch-economics; NASA NEXT-C | https://ntrs.nasa.gov/citations/20210024276 | cited |
| up to 2450 (flown ~2500) | s Isp | Iodine EP flown in orbit (ThrustMe NPT30-I2) | Rafalskyi et al. 2021, Nature | https://pmc.ncbi.nlm.nih.gov/articles/PMC8599014/ | cited (flown) |
| >310 (water electrothermal ~175) | s Isp | Water EP (Hydros-C; steam thrusters) | Acta Astro. 2024 | https://www.sciencedirect.com/science/article/pii/S0094576524001681 | cited |
| 5,000-12,000 | USD/kg | Xenon cost (import-wall driver) | SETS Electric Propulsion | https://sets.space/xenon-krypton-or-argon-propellants-for-hall-thruster-efficiency-properties-applications-and-cost/ | cited |
| 2,100-4,800 (Kr); 7-15 (Ar) | USD/kg | Krypton / argon cost | SETS | (as above) | cited |
| ~50-60 | t/yr | Global xenon production ceiling (import wall) | SETS | (as above) | cited |
| 8:1 (O2:H2 = 0.889:0.111) | mass ratio | Stoichiometric water split (derived) | conservation of mass | - | derived |
| in-situ iodine extractability on Moon/asteroid | - | Whether iodine is locally sourceable at documented yield | none | - | **[GAP]** |

---

## The derivation (confirmed)

- Water electrolysis floor: 285.8 kJ/mol / 0.018015 kg/mol = 15.86 MJ/kg = **4.41 kWh/kg**
  (HHV thermodynamic minimum); Kornuta's full-chain ~10 kWh/kg brackets it above.
- Water split: 1 kg H2O -> 0.889 kg O2 + 0.111 kg H2 (8:1).
- Propellant mass fraction `exp(Delta_v/(Isp*g0)) - 1`, confirmed for representative hops:

  | hop (Delta-v) | chem 320 s | LOX/LH2 450 s | EP 2000 s | EP 3000 s |
  |---|---|---|---|---|
  | Lunar surf->LLO (1870) | 0.815 | 0.528 | 0.100 | 0.066 |
  | LEO->Mars inj (3600) | 2.149 | 1.261 | 0.201 | 0.130 |
  | NEA rendezvous (5000) | 3.920 | 2.105 | 0.290 | 0.185 |
  | Small hop (300) | 0.100 | 0.070 | 0.015 | 0.010 |

  High-Isp EP needs ~1/6 to 1/10 the propellant mass of chemical for the same hop.

---

## Proposed API

```python
def propellant_mass(delta_v_m_s: float, isp_s: float, dry_mass_kg: float) -> float:
    """Reaction mass (kg) for a hop, via the rocket equation."""

def production_energy(propellant_kg: float, route: Route, *, liquefy: bool) -> float:
    """kWh to make the propellant in-situ (route-specific specific energy)."""

def propellant_closure(route: Route) -> ClosureResult:
    """Locally-sourceable fraction (water/O2 -> 1; xenon/iodine -> 0) + imported kg."""
```
Pure functions of plain data; deterministic algebra; no globals, clock, or RNG.

---

## Validation plan (verified targets)

- Delta-v -> 0 => propellant -> 0 (exp(0)-1 = 0). Assert exactly 0.
- High-Isp check: EP 3000 s propellant mass ~1/6 to 1/10 of LOX/LH2 for the same hop
  (Mars: 0.130 vs 1.261). Assert the ratio.
- Mass conservation on the water route: 1 kg water -> 0.889 kg O2 + 0.111 kg H2 (assert to
  1e-6).
- Energy floor: water-electrolysis specific energy never below 4.41 kWh/kg
  (thermodynamic min); assert the model rejects/flags sub-thermodynamic inputs.
- Closure edges: all-water/O2 route -> propellant_closure = 1.0; xenon-only ->
  propellant_closure = 0.0 and imported_kg = full propellant mass (the import wall).
- Cross-check: propellant fraction round-trips against
  `launch_economics.rocket_equation_mass_ratio` for the same (Delta-v, Isp).

---

## Interface wiring

- **consumes transfer:** `transfer`'s Delta-v per hop is the input that sets propellant
  need via the rocket equation.
- **reuses launch-economics:** calls `rocket_equation_mass_ratio` rather than re-deriving
  Tsiolkovsky.
- **-> power-budget:** `production_energy` is a power/energy draw.
- **-> closure-sim:** plant mass as closable hardware, plus `propellant_closure` as a
  distinct closure axis and `imported_propellant_kg` as a reaction-mass "vitamin".
- **seam with isru (do NOT merge):** isru = feedstock-for-parts via molten regolith
  electrolysis (~24 kWh/kg O2, no water); propellant = reaction-mass via water
  electrolysis to cryo (~10 kWh/kg, needs water ice). Different feedstock, different
  product, different question. Share a REFERENCES cross-link so the two oxygen energies
  (from-rock vs from-water) are never confused.

---

## The payoff (why it earns a directory)

The self-replicating-probe conclusion falls out cleanly: to close propellant, a probe
must use water-derived chemical or water electric propulsion; choosing high-Isp noble-gas
EP trades propellant *mass* for a permanent supply-chain tether to Earth (world xenon
production ~50-60 t/yr physically caps it). Iodine softens the wall (~20x cheaper,
storable solid) but is not in-situ-extractable at documented yields -> **[GAP]**. This is
the reaction-mass analog of the electronics "vitamin" wall, and nothing else in the repo
models it - a new closure axis worth its own module, kept deliberately thin (it
orchestrates transfer + launch-economics + isru-style energy, it does not re-derive them).
</content>
