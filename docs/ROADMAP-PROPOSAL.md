# Roadmap proposal: candidate modules for von-neumann

Status: **proposal**, not yet adopted. Nothing here is committed to `ROADMAP.md`.

This is the synthesis of a four-wave research pass (thirteen literature scouts plus one
adversarial completeness critic) over the existing eight modules, the bibliography
(`frontend/src/sources.ts` / `papers/refs.bib`), and the methodology (`CLAUDE.md`,
`ROADMAP.md`, `FINDINGS.md`). Every candidate was gated on the question the iron rule
(CLAUDE.md 1) forces: **not "is it interesting?" but "is it groundable?"** Each was
researched to a verdict, a sourced numbers table, a scope with a validation, a clean
interface, and an over-nesting risk. A critic then attacked the whole set for what was
missing, overclaimed, or un-groundable; a verification agent took the three softest
numbers back to primary sources. The full per-scout research is in the session task
outputs; this is the distilled result.

The candidate set converged: the critic's search for further module-worthy gaps returned
only two (propellant, output-value), both since researched, plus items it judged
correctly to be *not* modules (see "Deliberately not modules"). No further gaps remain
open.

---

## The organizing insight (corrected for honesty)

The project's most valued move (the `spine` module) is to **replace a number one module
*assumes* with a number another module *derives***. An earlier draft of this proposal
claimed most candidates do this; the critic was right that it was oversold. The honest
count: **six candidates retire a specific hand-set number**; the rest add a new mass, a
new wall, or a new closure axis that no current module carries at all. Both kinds are
worth building - but only the first kind is the `spine` move, and the distinction should
not be blurred.

| Retires an existing assumption | Adds new physics / mass / wall |
|---|---|
| `transfer` - multi-probe's hand-set ~365 d transit time | `thermal` - the (free) cost of heat rejection -> BOM mass |
| `isru` - closure-sim's ~5 kWh/kg build energy | `comms` - a new data-return wall |
| `power-source` - the total power power-budget splits | `shielding` - the (free) mass that defends the electronics wall |
| `structures` - closure-sim's `producible_locally` boolean | `propellant` - a new propellant-closure axis + import wall |
| `assembly` - closure-sim's ~20 kg/day build rate | `chip-fab` - the *height* of the electronics wall |
| `autonomy` - the 0.70 manuf/compute split | `value` - the (missing) output side of the economic case |

**The sharpest single point from the critique:** the most load-bearing hand-set number
in the whole project is the **~20 kg/day build rate** - it is FINDINGS #9's ~582-day
doubling clock, the fleet's entire cadence. NASA's own 1980 AASM study implies ~274
kg/day for the same job, a >10x disagreement between the repo's two lineage numbers. That
number is exactly what `assembly` derives, and it was the biggest omission from the
original nine. It is now included.

Two natural clusters: **the factory-on-a-body stack** (`isru` -> `structures` ->
`assembly`, `thermal`, `power-source`, `shielding`, `propellant`) and **the
fleet-in-space stack** (`transfer`, `comms`, `autonomy`, `reliability`). `chip-fab` and
`value` sit apart as a paper and a fold (below).

---

## Verdicts at a glance

| Candidate | Groundable? | Status | Headline contribution |
|---|---|---|---|
| `transfer` | **YES** (highest) | build | Delta-v + trip time; Edelbaum closed form; retires the 13.6 AU wall |
| `power-source` | **YES** (top-tier) | build | Solar/nuclear crossover d = sqrt(sp_solar/sp_nuclear) ~ 4-5 AU |
| `thermal` | **YES** (top-tier) | build | Radiator area/mass; heat rejection stops being free |
| `propellant` | **YES** | build | Propellant closure vs the noble-gas import wall |
| `comms` | **YES** (well-anchored) | build | Data rate ~1/d^2 (JPL-confirmed); a new data-return wall |
| `isru` | **YES** lunar / **PARTLY** asteroid | build | Derives closure-sim's build energy from regolith physics |
| `shielding` | **YES** (2 estimate seams) | build | Local regolith vs imported rad-hardness; GCR non-monotonic |
| `assembly` | **PARTLY** (`[ESTIMATE]`) | build | Derives the ~582-day doubling clock |
| `autonomy` | **PARTLY** (bracketed) | build | Compute demand vs supply -> an autonomy wall; closes power-budget's loop |
| `reliability` | **PARTLY** (highest risk) | build | Real-world messiness; unlocks the swarm Aurora steady-state |
| `structures` | **PARTLY** | likely a parameter | Strength test for closure; may collapse into closure-sim |
| `chip-fab` | **PARTLY** (`[GAP]` core) | a paper | Node-capability vs fab-complexity trade |
| `value` | **PARTLY** (mostly `[GAP]`) | fold into launch-economics | Launch-cost-avoided value; debunks the "quintillion asteroid" |

---

## The ten buildable modules, in three tiers

### Tier 1 - build first (fully grounded, low risk, foundational)

**1. `transfer` - interplanetary Delta-v and trip time.** Textbook-exact; every constant
canonically citable (GM_sun, AU, orbital radii from the NASA fact sheet already in the
bibliography). Validated: same-orbit -> 0; Earth->Mars heliocentric 5.59 km/s / 259 d.
**Verification upgrade:** low-thrust trip time is no longer a naive bracket - Edelbaum's
1961 equation gives a sourced closed form, reducing for coplanar circle-to-circle
heliocentric hops to `Delta_V = |V1 - V2|`, `t = Delta_V / f`. Retires multi-probe's
parameterized transit time and makes the ~13.6 AU wall a derived output. Interstellar
stays in `swarm`.

**2. `assembly` - robotic build rate.** Derives closure-sim's most load-bearing assumed
number: `machinery_rate = manipulators x throughput x duty_cycle x yield`, from published
metal-AM deposition rates (WAAM 1-4 kg/h, LPBF 0.1-0.5 kg/h), robot mass-vs-payload, and
OEE/first-pass-yield. Honest `[ESTIMATE]` - terrestrial-robot proxies for a space
factory - carrying the 12-274 kg/day spread as its uncertainty band. The `spine`-style
derivation of the doubling clock. Guard: no discrete-event floor sim; throughput is a
parameter, not an assembly simulator.

**3. `isru` - in-situ feedstock processing.** Retires closure-sim's ~5 kWh/kg build
energy. Lunar side exceptionally sourced (2025 PNAS full-chain 24.3 +/- 5.8 kWh/kg LOX;
excavation negligible, reduction/electrolysis dominates). Derives ~4 kWh/kg metal (molten
oxide electrolysis) and the closure *ceiling* (cannot close on an element the body lacks).
One module, two internal stages (excavate -> refine). `[ESTIMATE]`: in-situ metal and
asteroid extraction energy use terrestrial molten-oxide-electrolysis as a proxy; build
the lunar-oxygen tier solid first, asteroid support as a tagged second tier.

**4. `power-source` - solar vs fission vs RTG crossover.** Exceptionally grounded (every
figure from a flown system or documented program). The crossover is a two-line
derivation: `d_cross = sqrt(sp_solar_1AU / sp_nuclear)` ~ 4-5 AU, independent of power
level (P cancels) - matches reality (Juno runs solar at Jupiter, everything beyond
switches to RTG). Second crossover by power level: RTGs win below ~1 kWe, fission above.
New "vitamin"-style wall: Pu-238 production ~0.5-1.5 kg/yr, one GPHS-RTG needs ~8 kg.
Emits available power to `power-budget` and plant mass to `closure-sim`; **calls
`thermal`** for reactor radiator mass. Basis landmine: solar W/kg spans 4x - pin it
(default conservative flight system-level).

**5. `thermal` - heat rejection and radiator sizing.** Closes the project's own gap
(FINDINGS: "a power-and-cooling problem, not a physics one" - yet no cooling model). One
closed form (Stefan-Boltzmann); radiator specific mass (~3 kg/m^2 target) from convergent
NASA/DOE sources; ISS (70 kW, ~275 K radiators) is a flight anchor. Distance story is one
equation: waste heat and the sink term both fall as ~1/d^2, so the radiator-to-array area
ratio is nearly distance-independent. Must allow per-source radiator temperature (hot
smelting radiators are ~10x lighter per kW than ~300 K compute radiators). Returns a
radiator mass into closure-sim's BOM.

### Tier 2 - build next (grounded, open new ground, honest estimate content)

**6. `comms` - link budget and data return.** Unusually well-anchored: real-mission
rates span ~7 orders of magnitude, and JPL confirms DSOC verified data rate falls as
**1/d^2** (the same gate probe-sim uses for power); DSOC 25 vs 8.3 Mbps reproduces it to
~2%. Opens a new wall: build probes faster than a 1/d^2 link returns their bits and
aggregate knowledge saturates at sum(R(d_i)), not probe count. A fourth power draw in
power-budget; keep distinct from swarm's light-speed *latency* layer (this is
*throughput*). Guard: R(d) = k/d^2 calibrated to a mission anchor + a modem ceiling, not
a link-budget engine. Pin distance basis (Earth-range vs heliocentric).

**7. `propellant` - reaction-mass ISRU and propellant closure.** The seam the critic
found between `transfer` and `isru`. Propellant mass per hop is Tsiolkovsky (already in
launch-economics) fed by transfer's Delta-v; production energy is derivable (water
electrolysis 4.41 kWh/kg is the thermodynamic HHV minimum, cross-checked to Kornuta's
full-chain ~10 kWh/kg). Owns a genuinely new concept: **propellant closure** as a
distinct axis - water/O2 routes reach 1.0 on a water-bearing body, but noble-gas EP
(xenon, world supply ~50-60 t/yr) is a hard import wall. The payoff: to close propellant,
a probe must use water-derived chemical or water-EP; high-Isp noble-gas EP trades
propellant mass for a permanent Earth tether. Keep the seam with isru clean (regolith ->
parts vs water-ice -> reaction mass); do not merge.

**8. `autonomy` - onboard compute demand.** Closes power-budget's open loop:
`probe-sim.autonomy` already models compute *supply* (falling as 1/d^2); this models
*demand*, producing an **autonomy wall** (distance where affordable compute drops below
required). Its most defensible anchor: the insect-brain proxy (honeybee ~1e13 to mouse
~1e15 FLOPS) brackets a self-driving car's ~1.4e14 ops/s from both sides - three
independent lines converging. The deliverable is a *band*, not a point; "FLOPS to run a
factory" stays a `[GAP]`, boundable to the same bar as isru's asteroid tier. Retires the
0.70 manuf/compute split (today a free choice in mission/multi-probe). Basis warning:
MIPS/TOPS (integer) vs FLOPS - pin and convert. Guard: no neural-net or SLAM sim; pure
accounting over sourced per-task costs, exactly as power-budget does for watts->FLOPS.

**9. `shielding` - radiation shielding mass.** Inputs strongly grounded by published
attenuation-vs-areal-density curves (no particle transport needed); real vaults (Europa
Clipper 150 kg, Juno ~200 kg) anchor the test. Encodes the crucial GCR non-monotonicity:
dose-equivalent has a *minimum* near ~20 g/cm^2 Al and thicker aluminum is *worse*
(secondaries) - the module must refuse to exceed it or it produces confident nonsense.
Mirror-image contribution: shielding is *locally buildable* mass that **raises** closure
(opposite of vitamins), and answers "can local regolith shielding around cheap COTS parts
substitute for imported rad-hardness?" `[ESTIMATE]` seams: regolith vs Jovian TID
(electron) environment is a proxy; the substitution verdict is derived. Pin dose units
(krad(Si) for electronics vs mSv for GCR).

**10. `reliability` - degradation and mortality.** The real-world messiness CLAUDE.md 3
wants; every current model is failure-free. Solid ground (flight-measured): array
degradation (~0.18 %/yr, worse near the Sun / in Jovian belts), GCR dose (~1.8 mSv/day),
SEU rates, lunar-dust exponential array loss. Proxy `[ESTIMATE]`: discrete factory
failure has no operational history; a per-day hazard from satellite statistics
(~1.1e-5/day) is a defensible analog, tagged at every use site. Genuine `[GAP]`:
self-replication mutation rate. **Unlocks the Aurora steady-state** - VERIFIED against
Carroll-Nellenback 2019: the ODE `dX/dt = (1/T_l) X (1-X) - (1/T_s) X` gives
`X_eq = 1 - T_l/T_s` (Eq. 32), verbatim correct, but the symbols are counterintuitive -
**T_l is the launch/spread time, T_s the settlement lifetime**, and the plateau needs
`T_l < T_s`. **This is the highest-risk module** (the critic's assessment, and mine): it
is the only one adding new RNG (a stray non-seeded draw would break `speculate` - the
sneakiest bug the project warns about), it carries the worst over-nesting temptation
(dose -> SEU -> latchup), and its mortality half is proxy/gap data. The `hazard=0`
bit-exact regression against current results is the mandatory guard.

---

## Three candidates that are not full modules

**`structures` - likely a parameter inside closure-sim, not a directory.** It gives
closure-sim's `producible_locally` boolean a physics basis (local material strength vs a
required-strength threshold) plus a mass penalty `k` for weaker material. Sintered-
regolith strength spans >100x by technique (2.49-312 MPa), so it must carry uncertainty
bands. The critic's point stands: the `k = 1.0` regression test (must reproduce
closure-sim exactly) is an admission it may collapse into closure-sim. **Default: demote
to a mass-penalty parameter `k` in closure-sim; promote to its own directory only if the
k=1.0 test shows the physics moves real closure numbers.**

**`chip-fab` - ship the trade curve as a `papers/` write-up, not a BOM input.** The
wall's depth and the node-capability-vs-complexity trade are well-sourced and novel
(the Intel 4004 ran control tasks on 2,300 transistors / 10 um; control logic lives on
28-180 nm, no EUV). **Verification firmed the inputs:** electronic-grade polysilicon
9N-11N confirmed (12N is marketing), solar/specialty-gas 6N confirmed, ">100 chemicals"
confirmed as a floor. But the one number closure-sim wants - a minimal fab's imported
*mass* - is a genuine `[GAP]` (real fabs report cost/area/tools, never tonnage). **That
`[GAP]` must never be wired into closure-sim's BOM as if measured** - it feeds the
project's flagship finding and is the worst place to launder a guess. The trade curve is
a strong paper; the mass estimate is not a model input.

**`value` - fold the defensible core into launch-economics; do not build the ambitious
version.** The economic case *is* one-sided (mission prices cost avoided, never value
returned), and the critic was right to flag it. But only one output survives the iron
rule: launch-cost-avoided value (`mass x $/kg-in-orbit`), which is definitional
arithmetic over numbers launch-economics already sources. Realized PGM value, settlement
value, and $/bit for data are `[ESTIMATE]`/`[GAP]`. Honesty backbone (fully sourced): the
entire annual global platinum market is ~$7B, yet one "football-field asteroid" is quoted
at $50B of platinum - so the "$X quintillion" headlines are arithmetic fictions that
collapse under market-flooding. **Add a `value.py` to launch-economics** for the
launch-cost-avoided curve (completing mission's payoff with zero new unsourced numbers);
treat PGM value only as a heavily-caveated illustration whose point is to debunk the
headline figures.

---

## Deliberately not modules (the critic's exclusions, endorsed)

- **Navigation / GNC.** Rolls into `autonomy` (compute demand) plus sensor mass (a BOM
  line). Does not earn a directory under the over-nesting rule (CLAUDE.md 3).
- **Multi-decade time value / discounting.** Builds run 17-29 years with no discount
  rate, which is a real gap - but it belongs as a `launch-economics` analysis, not a new
  module.

---

## Verification results (the three softest numbers, taken to primary sources)

1. **Aurora formula - CONFIRMED (formula) / CORRECTED (symbols).** `X_eq = 1 - T_l/T_s`
   is verbatim correct (Carroll-Nellenback 2019 Eq. 32); T_l = launch/spread time,
   T_s = settlement lifetime; plateau needs `T_l < T_s`. An earlier automated read had
   both the meanings and the condition backwards.
2. **Chip-fab purity - MIXED, mostly confirmed.** 9N-11N electronic, 6N solar/specialty-
   gas, ">100 chemicals" all confirmed; 12N is marketing; per-node purity mapping stays
   `[ESTIMATE]`.
3. **Low-thrust transfer time - CORRECTED (upgraded).** Edelbaum's 1961 equation
   supersedes the naive Delta-v/accel bracket with a sourced closed form; coplanar
   circle-to-circle heliocentric: `Delta_V = |V1 - V2|`, `t = |V1 - V2| / f`.

---

## Recommended build order

Dependency-ordered, incorporating the critic's two corrections (isru before power-source -
size the load before the source; comms pulled up front - low-risk, new result):

`transfer` -> `comms` -> `assembly` -> `isru` -> `propellant` -> `thermal` ->
`power-source` -> `autonomy` -> `shielding` + `reliability` (paired) -> then, in parallel
with the rest: `structures` decided as parameter-vs-module, `chip-fab` written as a paper,
`value` folded into launch-economics.

Rationale: `transfer` and `comms` lead (highest groundability, both reuse the 1/d^2 law,
both open clean results with built-in validation anchors). `assembly` -> `isru` retire the
two biggest load-bearing assumed numbers (the doubling clock and the build energy).
`propellant` follows `transfer` (needs its Delta-v). `thermal` precedes `power-source`
(radiators), which follows `isru` (the load it must size to). `reliability` sits late as
the riskiest, paired with `shielding` via the dose model - though note the tension:
CLAUDE.md 3 *wants* the messiness it adds, and it unlocks the Aurora steady-state, so
there is a case for pulling it earlier once the RNG-purity risk is retired.

---

## Cross-cutting notes

- **One shared radiation-environment primitive, not two dose models.** `shielding`
  (attenuation -> mass) and `reliability` (dose -> degradation/mortality) both need the
  same GCR/SPE/Jovian dose numbers. Maintaining them twice invites divergence. Factor a
  single small radiation-environment reference/primitive both consume, rather than two
  peers passing dose between them.
- **These interlock, and suggest a capstone, not a fourteenth module.** Almost every
  candidate becomes a draw, energy cost, mass, or closure axis on
  `power-budget`/`closure-sim`; `transfer`/`comms`/`reliability` feed the fleet;
  `power-source` calls `thermal`; `shielding` and `reliability` share the dose loop;
  `isru` feeds `structures` and shares chemistry with `propellant`. Once Tier 1 lands, a
  `mission`/`spine` refresh could thread them: a seed that chooses a power source, rejects
  its heat, refines feedstock, builds parts strong enough, shields and survives a hazard,
  makes its own propellant, thinks hard enough to run alone, crosses a real transfer time,
  and phones home at 1/d^2 - every number derived, not assumed. That is the natural
  capstone.
- **Discipline reminders that recurred across all thirteen scouts:** keep each a pure
  seeded deterministic fold with pimas only as skin (7); resist over-nesting (every scout
  named a "do not build the full simulator" boundary - trajectory optimizer, heat-pipe
  solver, reactor neutronics, plant model, link-budget engine, particle-transport code,
  FEA, dose->latchup chain, fab process sim, thruster physics, valuation engine); pin
  measurement bases (heliocentric vs Earth-range distance; heliocentric vs from-LEO
  Delta-v; delivered-electrical vs thermal kWh/kg; flight-wing vs blanket W/kg; krad(Si)
  vs mSv; MIPS/TOPS vs FLOPS); and tag every proxy `[ESTIMATE]`/`[GAP]` at its use site.
  Only `reliability` adds RNG; everything else is deterministic algebra or table lookup.
</content>
