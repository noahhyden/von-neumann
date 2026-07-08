# dispositions - the three candidates that are not full modules (proposal)

Status: **proposal**, not yet adopted. Companion to the ten build-ready module specs
(`transfer`, `comms`, `assembly`, `isru`, `propellant`, `thermal`, `power-source`,
`autonomy`, `shielding`, `reliability`). This covers the three `ROADMAP-PROPOSAL.md`
candidates that research and the completeness critic judged should NOT become full
modules - and says exactly what each should be instead. Numbers below were recomputed and
confirmed.

Recording a disposition is as much a deliverable as a spec: under the iron rule, "do not
build this as a module" is a real, defensible engineering decision, and writing down why
prevents someone rebuilding it later on numbers that cannot be sourced.

---

## 1. `structures` -> a mass-penalty parameter inside closure-sim (not a directory)

**What it would do:** give closure-sim's hand-set `producible_locally` boolean a physics
basis - compare a part's required strength to the best local material's strength, and
apply a mass penalty `k` for weaker material.

**Why not a full module:** the `k = 1.0` regression test (must reproduce closure-sim
exactly when local material meets the requirement) is itself the admission that it may
collapse into closure-sim. It carries a `[GAP]` (no measured structural-vs-precision mass
fraction for a complete factory) and a paywalled key input (ferrosilicon UTS).

**Disposition: implement as a `strength_penalty(part, material, load_case)` helper in
closure-sim.** Promote to its own directory ONLY if, once wired in, the physics moves real
closure numbers versus today's booleans. Confirmed penalty behavior (tension, k =
S_ref/S_local against 6061-T6 UTS 310 MPa):

| local material | strength | k (tension) |
|---|---|---|
| sintered regolith (weak) | 45 MPa | 6.9x |
| sintered regolith (mid) | 206 MPa | 1.5x |
| vat-photopoly ceramic | ~200 MPa flex | 1.6x |
| cast basalt (tensile) | ~14 MPa | 22x |

Key design constraint the helper must encode: regolith/ceramic is strong in compression
but weak in tension (cast basalt 400+ MPa compressive vs ~14 MPa tensile), so the penalty
is per **load case** - `k = S_ref/S_local` for tension members, a weaker
`k ~ (E_ref/E_local)^0.5` for bending/buckling. A single scalar penalty would be wrong.
Sources: Gupta et al. 2023 (arXiv 2308.14331), cast basalt (Lunarpedia), 6061-T6
(Wikipedia), AASM 1980 structural vitamins (bearings, precision fasteners).

---

## 2. `chip-fab` -> a `papers/` write-up (not a BOM input)

**What is groundable and novel:** the node-capability-vs-fab-complexity trade. A factory
controller is not a datacenter GPU - the Intel 4004 ran control tasks with 2,300
transistors on a 10 um node (no EUV); industrial control lives on 28-180 nm. Dropping the
target node collapses nearly every wall metric: masks ~90 -> ~25, no EUV monopoly tool,
purity 9N instead of 11N (12N is marketing, verified), fewer of the >100 chemicals. The
wall is tall only if you insist on cutting-edge chips. This is a strong, fully sourced
result (CSIS, SEMI, Williams 2002, Nagapurkar 2022, Bernreuter/Wacker on purity).

**The disqualifying `[GAP]`:** the one number closure-sim would want - a minimal fab's
imported *mass* - has no published value (real fabs report cost, area, tools, water, never
tonnage). It can only be an `[ESTIMATE]` from floor-area/tool-count proxies.

**Disposition: write the node-vs-complexity trade as a `papers/` paper**, reusing the
`sources.ts` -> `refs.bib` pipeline so its citations match the live surfaces. **Do NOT
wire the fab-mass `[ESTIMATE]` into closure-sim's BOM** - it feeds the project's flagship
electronics-wall finding, and CLAUDE.md opens with exactly this failure mode ("a single
unsourced number compounds into confident nonsense"). The paper quantifies the wall's
height honestly; the mass estimate is illustrative, not a model input. A thin
`fab_requirement(node) -> {steps, masks, purity, needs_euv, ...}` helper (no mass) could
back the paper's figures if wanted.

---

## 3. `value` -> fold the defensible core into launch-economics (do not build the ambitious version)

**The real gap:** the economic case is one-sided - mission prices cost avoided, never
value returned.

**What survives the iron rule:** exactly one output - launch-cost-avoided value,
`value = installed_mass_kg x $/kg-in-orbit`, definitional arithmetic over numbers
launch-economics already sources (~$3,060/kg to LEO). Confirmed: 1 t installed in LEO is
worth ~$3.06M; 1000 t ~$3.06B, on that basis. Everything past it - realized PGM value,
settlement value, $/bit for returned data - is `[ESTIMATE]` or `[GAP]`.

**The honesty backbone (fully sourced):** the entire annual global platinum market is
~$7.2B, yet one "football-field asteroid" is quoted at ~$50B of platinum - **6.9 years of
global supply in one rock**. Dumping it collapses the price, so the "$X quintillion
asteroid" headlines are arithmetic fictions (mass x sticker price). Realized value is
demand-limited: `~ min(supply, 0.2 x annual demand) x post-crash price`, tagged
`[ESTIMATE]`.

**Disposition: add a `value.py` to launch-economics** producing the launch-cost-avoided
delivered-mass value and a value-over-time curve (consuming installed-mass-over-time from
multi-probe/swarm), reusing the existing $/kg so there is one provenance chain. This
completes mission's payoff stage with a two-sided picture (cost avoided + value delivered)
and **zero new unsourced numbers**. Treat PGM value only as a heavily-caveated
illustration whose *point* is to debunk the headline figures - never a load-bearing model
output. Do NOT build a standalone valuation engine that prices knowledge, future markets,
or settlement; it cannot meet the iron rule. Sources: SpaceX pricing (in repo), Kornuta
2019, Sonter 1997, Elvis 2014, Physics World, Monday Economist (Psyche debunk).

---

## Also deliberately not modules (the critic's exclusions, endorsed)

- **Navigation / GNC** - rolls into `autonomy` (compute demand) plus sensor mass (a BOM
  line). Does not earn a directory (over-nesting rule).
- **Multi-decade time value / discounting** - a real gap, but a `launch-economics`
  analysis, not a module.

---

## Build-prep phase: complete

With these dispositions, every one of the 13 researched candidates now has a resolution:
**10 verified build-ready specs** + **3 dispositions** (a closure-sim parameter, a paper,
a launch-economics fold). Nothing module-shaped remains open. The next phase is actual
implementation in code (per the recommended build order in `ROADMAP-PROPOSAL.md`), which
is a separate commitment for the repo owner to authorize.
</content>
