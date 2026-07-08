# assembly - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. Third module from
`ROADMAP-PROPOSAL.md` worked to an implementable spec (after `transfer`, `comms`). Every
load-bearing number below was recomputed and confirmed (see "Validation").

`assembly` derives the single most load-bearing hand-set number in the project:
closure-sim's build rate (`local_build_rate_kg_per_day`, default 12; ~20 in multi-probe),
which is FINDINGS #9's ~582-day doubling clock - the fleet's entire cadence. NASA's own
1980 AASM study implies ~274 kg/day for the same job: a **13.7x-33.3x disagreement**
between the repo's two lineage numbers. That gap is exactly what this module resolves, by
deriving the rate from build physics instead of assuming it - the same move `spine` made
for the swarm's dwell time.

---

## Scope

**Models (pure, deterministic, plain-data - zero pimas imports, no RNG):**

`machinery_rate_kg_per_day = manipulator_count * per_manipulator_throughput_kg_per_day
* duty_cycle * first_pass_yield`

where `per_manipulator_throughput` is a weighted blend over the process mix
(additive-manufacturing deposition, plus discrete assembly) matched to the copy's part
list. Also emits **manipulator + tooling mass** as a BOM line item, so build capacity
carries its own replicable mass cost (more build rate -> more manipulator mass to
replicate -> feeds back into closure).

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3):
- No discrete-event factory-floor simulation, no per-part scheduling.
- No robot-motion / path planning.
- No thermal / interpass-cooling sub-simulation (interpass cooling enters only as a
  duty-cycle discount).
- No material feasibility (that is `structures`: can a part be made and is it strong
  enough; `assembly` is only how fast a made part is built into the copy).

---

## Sourced numbers (REFERENCES.md format)

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| 100 | t | AASM lunar seed mass | Freitas (1981), growing lunar factory | https://www.rfreitas.com/Astro/GrowingLunarFactory1981.htm | sourced |
| 1 | yr | AASM replication time (authors call it a crude trial value) | Freitas 1981 / NASA CP-2255 | https://ntrs.nasa.gov/citations/19820045716 | sourced ([ESTIMATE] in source) |
| 274 (calendar) / 400 (250 working days) | kg/day | AASM implied build rate - derived from the two above | derived | (derivation) | derived |
| 12 (default) / ~20 (multi-probe) | kg/day | closure-sim's currently ASSUMED build rate - the number this replaces | repo: closure-sim/src/closure_sim/models.py | (repo) | assumed (to be retired) |
| 0.1-0.5 | kg/h | LPBF (laser powder-bed fusion) deposition rate | acsmaterial; metal-am.com | https://www.metal-am.com/articles/ | sourced |
| 1-4 (typical); 9.5-15 (high) | kg/h | WAAM (wire-arc DED) deposition rate | Springer IJAMT; Taylor & Francis WA-DED review | https://link.springer.com/article/10.1007/s00170-024-14144-z | sourced |
| 11.9 | kg/h | Electron-beam wire DED (IN718) | metal-am.com | https://www.metal-am.com/articles/ | sourced |
| 4,000-6,000 (up to 12,000) | parts/h | Delta pick-and-place throughput (light parts) | Standard Bots; EVS | https://standardbots.com/blog/everything-you-need-to-know-about-high-speed-pick-and-place-robots | sourced |
| 3.5-12 (e.g. ABB IRB 6600: 1700 kg / 225 kg) | ratio | Robot body mass / payload | KUKA; ABB spec | https://www.kuka.com/en-us/products/robotics-systems/industrial-robots/ | sourced |
| 85 (world-class) / 40-60 (typical) | % | OEE (overall equipment effectiveness = availability x performance x quality) | Lean Production; Tractian | https://www.leanproduction.com/oee/ | sourced |
| >=95 (world-class) | % | First-pass yield | Averroes; Tractian | https://tractian.com/en/blog/first-pass-yield | sourced |
| ~35 (nameplate) / ~71 (50% duty) | kg tooling / (kg/day) | Derived manipulator mass per throughput (1700 kg robot, WAAM 2 kg/h) | derived from robot mass + deposition | (derivation) | [ESTIMATE] |

The headline `machinery_rate` and the mass-per-throughput are `[ESTIMATE]`: terrestrial,
Earth-gravity, mature-supply-chain robots are an imperfect proxy for a space factory. The
module tags its output `[ESTIMATE]`, cites the proxy chain, and carries the 12-274 kg/day
spread as its honest uncertainty band.

---

## The derivation (confirmed)

The AASM/closure-sim disagreement becomes legible once decomposed:
- A single WAAM arm (2 kg/h) at 24 h/day: **48 kg/day** nameplate; **38.8** at world-class
  OEE*FPY (0.85*0.95); **22.1** at typical-plant duty (0.50*0.92).
- So closure-sim's ~20 kg/day is essentially **one WAAM arm at typical duty**.
- AASM's 274 kg/day needs **~7 arms at world-class** duty, ~12 at typical.
- Manipulator mass: a 1700 kg robot at 48 kg/day nameplate -> **35 kg tooling per
  (kg/day)**; at 50% duty -> **71**.

The "13.7x-33.3x disagreement" is really "one arm vs a shop of ~7-12 arms" - a design
choice the module makes explicit instead of burying in a constant.

---

## Proposed API

```python
def machinery_rate(manipulator_count: int, throughput_kg_per_h: float,
                   hours_per_day: float, duty_cycle: float,
                   first_pass_yield: float) -> float:
    """Derived build rate (kg/day) = count * throughput * hours * duty * yield."""

def tooling_mass(manipulator_count: int, robot_mass_kg: float) -> float:
    """Replicable manipulator/tooling mass (kg) for the BOM."""

def blended_throughput(part_mix: Mapping[Process, float]) -> float:
    """Weighted deposition/assembly rate (kg/h) over a copy's process mix."""
```
Pure functions of plain data; no globals, clock, or RNG.

---

## Validation plan (verified targets)

- Corridor: default composition lands the derived rate in the **12-274 kg/day** corridor
  bounded by closure-sim's assumption and AASM; landing outside flags a composition error.
- Reproduce the anchors: 1 WAAM arm (2 kg/h) at typical duty (0.50*0.92) -> 22.1 kg/day
  (~ closure-sim's 20); 7 arms at world-class -> ~272 kg/day (~ AASM's 274). Assert both.
- **Regime coupling with closure-sim (the key behavioral test):**
  - `machinery_rate` set high -> closure-sim reports **energy-binding**
    (`output = energy_cap`), matching its existing `_binding_rate` regime logic.
  - `machinery_rate` set low -> **assembly-binding** (`output = alpha*F` below energy cap).
- Edges:
  - `duty_cycle = 1.0` AND `first_pass_yield = 1.0` -> nameplate throughput exactly (no
    silent discount).
  - `manipulator_count = 0` -> rate 0, factory stalls.
- Mass conservation: `tooling_mass` scales linearly with `manipulator_count`; higher
  build rate costs proportionally more replicable mass.

---

## Interface wiring

- **-> closure-sim (the headline):** derives `local_build_rate_kg_per_day` from
  `manipulator_count x throughput x duty x yield` - routing a quantity into the fold that
  was previously hand-set. Exactly the closure-sim analog of what `spine` did for the
  swarm's `settle_time_years`. Backward compatible: absent inputs fall back to today's
  assumed rate.
- **-> closure-sim BOM:** adds manipulator/tooling mass as closable hardware, so build
  capacity replicates itself (a real feedback: faster copying costs more mass to copy).
- **consumes structures (proposed):** the part list weights the process mix (deposited vs
  machined vs bolted). Firm seam: `structures` = can-this-part-be-made/how-strong;
  `assembly` = how-fast-is-it-built. Do not re-derive material feasibility here.
- **-> multi-probe / spine:** the derived rate flows straight into the doubling clock and
  the cross-scale dwell, replacing the assumed ~20 kg/day at its root.

---

## Two honesty guards

1. **Subtractive vs additive accounting.** CNC material-removal rate is mass *removed*,
   not mass of *finished part*; do not sum it against AM deposition. Either convert
   machining to a finished-part rate via a part-specific stock-removal fraction, or
   exclude machining from the mass-build accounting. State which.
2. **`[ESTIMATE]` at every use site.** The headline rate is a terrestrial-proxy estimate,
   not a measurement. The 12-274 kg/day spread IS the uncertainty and must ship with the
   number, never a false-precision point value.

---

## Why this belongs in Tier 1

It retires the project's most load-bearing assumed number - the doubling clock that
FINDINGS #9 rests on entirely - and it does so from hard, published deposition rates. The
derivation is a handful of multiplies with a clean seam to closure-sim (headline), a BOM
feedback (tooling mass), and a documented boundary against `structures` and against a
factory-flow simulator. It turns a >10x unexplained disagreement into an explicit,
sourced design choice.
</content>
