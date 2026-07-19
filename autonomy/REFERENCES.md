# Where the numbers come from

Every quantity in `autonomy` traces to a source below, or is derived from ones that do
(CLAUDE.md 1). Units: FLOPS / operations per second, W, AU. This module supplies the
compute *demand* that `probe-sim` models the *supply* for; the demand is an honest
`[ESTIMATE]` band, not a point.

## Basis warning (pinned, CLAUDE.md 1)

The self-driving figure is **TOPS** (integer tera-operations per second); the brain
figures are **FLOPS** (floating-point operations per second). They are not the same unit.
This module compares them only as order-of-magnitude "operations per second" for
accounting, and flags the distinction rather than silently equating them. A scenario that
needs a precise FLOP/integer-op conversion must state it.

## Compute-demand anchors (three converging lines)

- **`HONEYBEE_BRAIN_FLOPS = 1e13`** - honeybee brain compute. Estimates span a spike-model
  floor of ~1e10 FLOPS to ~1e16 FLOPS with full non-neuronal physiology; 1e13 is a
  representative middle used as the lower autonomy anchor. Source: "The case for emulating
  insect brains...", arXiv:1812.09362, https://arxiv.org/pdf/1812.09362 . Verdict:
  `[ESTIMATE]` (wide range; representative point).
- **`SELF_DRIVING_OPS_PER_S = 1.4e14`** - onboard compute of a self-driving car, ~140
  TOPS. Context: full autonomous-vision workloads are 50-100 TOPS, L4 ~320 TOPS, NVIDIA
  Orin 254 TOPS, Mobileye EyeQ6 128 TOPS. 140 TOPS is a representative L4-class figure.
  Sources: Edge AI and Vision Alliance,
  https://www.edge-ai-vision.com/2021/04/autonomous-vehicles-drive-ai-chip-innovation/ ;
  GSA, https://www.gsaglobal.org/forums/edge-ai-computing-advancements-driving-autonomous-vehicle-potential/ .
  Verdict: sourced (engineered system of known capability - the strongest anchor).
- **`MOUSE_BRAIN_FLOPS = 1e15`** - mouse brain compute. Brain-compute estimates span
  ~1e13-1e17 FLOP/s; 1e15 is a representative middle used as the upper anchor. Source:
  Open Philanthropy brain-computation report,
  https://www.openphilanthropy.org/brain-computation-report . Verdict: `[ESTIMATE]`.

The point is convergence: an engineered autonomous system (self-driving car) sits between
two independent biological estimates (honeybee, mouse), so the demand band 1e13-1e15
ops/s is triangulated three ways, not asserted once.

## `[GAP]` (tagged, not invented)

- **"FLOPS to run a whole self-replicating factory" is a genuine `[GAP]`** - no measured
  value exists. But it is *boundable* to the same 1e13-1e15 band by analogy to the
  anchors above (a factory's control/perception is comparable to a self-driving car's),
  rather than fabricated. Flagged here and at any use site.

## The derivations (shown, validated in tests)

- **`required_compute_power_w = required_flops / efficiency`** - the inverse of
  `power_budget.compute_capacity_flops` (flops = power x efficiency); the FLOPS/W
  efficiency is a sourced scenario input documented in `power-budget/REFERENCES.md`.
- **`compute_fraction_needed = required_compute_w / total_power`** - the DERIVED
  replacement for the hand-set 0.70 manufacturing / 0.30 compute split in
  `mission`/`multi-probe`. The compute share now falls out of sourced demand and
  available power (140 TOPS at 1e10 FLOPS/W on a 100 kW bus -> 0.14, not 0.30).
- **`autonomy_wall_au = sqrt(supply_1AU / required)`** - supply falls as 1/d^2, demand is
  flat, so they cross at this distance. Verified to equal
  `probe_sim.max_distance_for_compute` fed the same array, split, and efficiency - the
  supply/demand loop is closed, not two disconnected models.

## Note on the brain scale vs power-budget

`power-budget` carries a *human*-brain scale marker (~1e18 FLOPS, Sandberg & Bostrom) for
"general intelligence per watt". This module uses *insect and small-mammal* brains as the
demand anchors for probe autonomy - a different, lower, and better-bounded quantity. No
contradiction: different brains for different questions.

## Interface wiring

- **<- probe-sim:** reuses `max_distance_for_compute` (supply) and `SolarArray`; this
  module supplies the sourced `required_flops` those took as a free input.
- **reuses power-budget:** the watts<->FLOPS conversion (single source of truth).
- **-> mission / multi-probe:** the derived compute fraction retires their 0.70/0.30
  free choice; the autonomy wall is a new distance limit alongside the power wall.

## Further reading (bibliography)

- **Open Philanthropy brain-computation report** - the brain-FLOP/s ranges behind the
  honeybee and mouse anchors.
- **Edge AI and Vision Alliance / GSA** - the TOPS-by-autonomy-level figures behind the
  self-driving-car central anchor.

## Analytical companion (issue #50, Phase 2)

`docs/FINDINGS_CLASSIFICATION.md` #30 asserts the autonomy wall
`d_wall = sqrt(supply_flops_at_1AU / required_flops)`. This is the compute
analogue of the power-source distance crossover (finding #24), from the
demand side. Derivation:

Solar-fed compute supply falls as `1/d^2`; autonomy demand is
distance-independent (set by the control problem, not the range):

    S(d) = S_1AU / d^2
    D    = required_flops

The wall is where supply drops below demand: `S(d_wall) = D`, hence

    d_wall = sqrt(S_1AU / D)

Two structural facts follow:
- **Absolute magnitude cancels** if S and D scale together
  (`d_wall(alpha*S, alpha*D) = d_wall(S, D)`).
- Only the **ratio** `S_1AU / D` controls the wall - not either quantity
  individually.

Tests in `tests/test_analytical_companions.py` verify (i) the closed form
matches, (ii) supply exactly equals demand at `d = d_wall`, (iii) the
absolute-magnitude cancellation via a joint-rescaling sweep, and (iv) the
`sqrt(2)` elasticity to doubling supply or demand.
