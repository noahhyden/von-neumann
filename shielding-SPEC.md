# shielding - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. Ninth module from
`ROADMAP-PROPOSAL.md` (after transfer, comms, assembly, isru, propellant, thermal,
power-source, autonomy). Numbers recomputed and confirmed (see "Validation").

`shielding` computes the mass of radiation shielding needed to keep a dose budget, split
into imported vs locally-built (regolith) mass. Its mirror-image contribution: shielding
is *locally buildable* mass that **raises** closure - the opposite of electronics
vitamins - and it answers a genuinely novel question: can local regolith shielding around
cheap COTS parts substitute for imported rad-hardness?

---

## Scope

**Models (pure, deterministic, plain-data - zero pimas imports, no RNG):** given (a) an
environment (GCR deep-space, SPE, or Jovian TID as parameterized dose-vs-areal-density
curves), (b) a dose budget from the electronics' TID rating and mission lifetime, and
(c) a material, compute the areal density and hence shielding mass, split into imported
vs local (regolith). Ingest published attenuation curves as lookup tables; interpolate;
never transport particles.

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3): Monte-Carlo / deterministic
particle transport (no GEANT4/FLUKA/HZETRN/OLTARIS re-implementation - it *consumes*
their published outputs); electronics failure physics (that is `reliability`); multilayer
optimization or angular/geometry effects beyond slab areal density.

---

## Sourced numbers (REFERENCES.md format)

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| ~20 (dose-eq minimum; worse beyond) | g/cm^2 Al | GCR dose-equivalent minimum vs Al thickness (non-monotonic) | Slaba et al. 2017, LSSR | https://pubmed.ncbi.nlm.nih.gov/28212703/ | sourced |
| up to 60 (net); 90 (neutron) | % of dose-eq | Secondary radiation behind Al | Acta Astronautica S0094576517311724 | https://www.sciencedirect.com/science/article/abs/pii/S0094576517311724 | sourced |
| no local minimum (monotonic) | - | Polyethylene attenuation shape (H-rich, fewer secondaries) | Slaba et al. 2017 | https://pubmed.ncbi.nlm.nih.gov/28212703/ | sourced |
| LH2 > polyethylene > Al (Al weakest) | ranking | Material effectiveness per unit mass | Cucinotta, NASA NTRS 20070005030 | https://ntrs.nasa.gov/api/citations/20070005030 | sourced |
| 0.7-1.0 % per g/cm^2 (~= Al) | dose cut | Regolith dose reduction per areal density | LPI 2028 (2008) | https://www.lpi.usra.edu/meetings/nlsc2008/pdf/2028.pdf | sourced |
| 227 (= 2.27 t/m^2) | g/cm^2 | Regolith for 50% effective-dose-eq cut (OLTARIS) | ScienceDirect S0032063325000832 | https://www.sciencedirect.com/science/article/pii/S0032063325000832 | sourced |
| 1.6-3.2 | g/cm^3 | Regolith bulk density | LPI 2028 | (as above) | sourced |
| ~20 water-equiv | g/cm^2 | SPE storm-shelter sufficiency | NASA RadWorks NTRS 20150001237 | https://ntrs.nasa.gov/api/citations/20150001237 | sourced |
| 9.2 mm Al (= 2.48 g/cm^2); 150 kg vault; 150 krad(Si); parts 300 krad | mixed | Europa Clipper vault (Jovian TID design point) | NASA + Springer | https://www.nasa.gov/missions/europa-clipper/how-nasa-is-protecting-europa-clipper-from-space-radiation/ | sourced |
| 4.11 g/cm^2 -> 250 krad; 11 g/cm^2 -> 35 krad | mixed | Clipper distributed-sensor areal-density -> dose | Springer 10.1007/s11214-025-01139-9 | https://link.springer.com/article/10.1007/s11214-025-01139-9 | sourced |
| ~200 kg; ~1 cm Ti; dose factor ~800; <25 krad | mixed | Juno radiation vault (houses RAD750) | Wikipedia Juno vault | https://en.wikipedia.org/wiki/Juno_Radiation_Vault | sourced |
| R=100; F=300; H=1000 | krad(Si) | Rad-hard TID grades (MIL-PRF-38535) | Wikipedia radiation hardening | https://en.wikipedia.org/wiki/Radiation_hardening | sourced |
| 5-10 (commercial); 100-300 (space-grade) | krad(Si) | COTS vs space-grade TID (the electronics wall band) | Wikipedia radiation hardening | (as above) | sourced |
| Al 2.70; HDPE 0.95; water 1.0 | g/cm^3 | Densities (g/cm^2 <-> cm <-> kg conversion) | textbook constants | - | exact |
| regolith vs Jovian TID (electron) environment | - | Regolith performance against trapped-electron TID | published regolith data is GCR/SPE | - | **[ESTIMATE]** (proxy) |

---

## The math and confirmed conversions

`mass_per_m2 (kg/m^2) = areal_density (g/cm^2) * 10`; `thickness (cm) = areal_density /
density (g/cm^3)`. Verified: Clipper vault 9.2 mm Al = 2.48 g/cm^2; regolith at 1.8 g/cm^3
needs 6.1 cm (110 kg/m^2) to match Clipper's 11 g/cm^2 sensor shield, or 126 cm (2.27
t/m^2) for a 50% GCR dose-equivalent cut.

**GCR non-monotonicity (the trap the module MUST encode):** aluminum dose-equivalent has
a *minimum* near ~20 g/cm^2; thicker Al is *worse* (up to 60% of net dose-equivalent is
secondaries). Polyethylene is monotonic. "More shield = safer" is false for GCR - the
model must refuse to exceed the Al minimum or it produces confident nonsense.

**The substitution (the module's novel output):** imported rad-hard F-grade parts (300
krad, heavy supply chain = the wall) vs local regolith shield around COTS parts (5-30
krad). On a surface, regolith mass is free (not launched); in transit it is full launch
cost. Rows for COTS TID + areal-density->dose + regolith-per-g/cm^2 let the module answer,
per environment, whether local shielding substitutes for imported rad-hardness.

---

## Proposed API

```python
def shielding_mass(environment: RadEnvironment, dose_budget_krad: float,
                   material: Material, *, on_surface: bool) -> ShieldingResult:
    """Areal density, thickness, mass; imported vs local split. Refuses to exceed the
    GCR Al minimum. on_surface flips regolith mass to free (not launch-charged)."""
```
Pure function; interpolates sourced curves; no globals, clock, or RNG.

---

## Validation plan (verified targets)

- Generous dose budget (budget >= unshielded dose) -> shielding ~0 kg. Assert.
- Harsh Jovian TID with COTS parts (5-10 krad) -> large mass approaching Clipper/Juno-class
  vaults (150-200 kg). Assert order-of-magnitude against rows.
- **GCR + aluminum: assert the optimizer refuses to exceed ~20 g/cm^2 and that modeled
  dose RISES past it.** This is the non-monotonicity guard.
- Polyethylene curve strictly decreasing (no minimum). Assert.
- `on_surface=True` -> regolith mass does NOT count against launch/closure debt;
  `on_surface=False` -> full launch cost. Assert the accounting flips.
- Conversions: 9.2 mm Al -> 2.48 g/cm^2; 11 g/cm^2 regolith at 1.8 g/cm^3 -> 110 kg/m^2.
  Assert to 1%.

---

## Interface wiring

- **-> closure-sim:** shielding is locally-buildable mass (regolith, cast metal) that
  RAISES effective closure - hands closure-sim a local-vs-imported mass split (the lever
  it already tracks).
- **<-> reliability (feedback loop):** `reliability` computes dose -> degradation/SEU;
  `shielding` computes shielding -> reduced dose. Clean seam: dose (krad(Si) or mSv)
  crosses the boundary, not internals. **Both should consume one shared
  radiation-environment primitive** (see ROADMAP-PROPOSAL cross-cutting note) rather than
  duplicate dose curves.
- **-> launch-economics:** emits both mass bills (imported rad-hard parts vs local
  regolith shielding) so launch-economics can price the trade.

---

## Two honesty guards

1. **Dose-unit basis (CLAUDE.md 1):** electronics use krad(Si) TID; GCR/human use mSv
   dose-equivalent. The module must pin which per environment - mixing them silently is a
   classic order-of-magnitude bug (the vault rows are TID).
2. **[ESTIMATE] seams:** regolith performance against the *Jovian TID (electron)*
   environment is a proxy from GCR/SPE data; the substitution verdict itself is derived,
   not cited. Both rest on sourced inputs - tag and bound them, never present as measured.

---

## Why it earns a module (not part of reliability)

reliability's job is dose -> failure; shielding's job is mass <-> dose. Different sources,
different validation edges, a clean dose interface. Fusing them would bury the
closure-relevant mass trade inside a failure model that does not care about mass. Keep the
seam; share only the radiation-environment primitive. Guard hard against becoming a
particle-transport simulator - it is a table-lookup + mass-accounting fold.
</content>
