# autonomy - build-ready spec (proposal)

Status: **proposal / build-ready spec**, not yet built. Eighth module from
`ROADMAP-PROPOSAL.md` (after transfer, comms, assembly, isru, propellant, thermal,
power-source). Numbers recomputed and confirmed (see "Validation").

`autonomy` models onboard compute **demand** to close power-budget's open loop:
`probe-sim.autonomy` already models compute *supply* (falling as 1/d^2); this models what
running-yourself-far-from-Earth *requires*, producing an **autonomy wall** - the distance
where affordable compute drops below required. It retires the 0.70 manuf/compute split
(today a free choice in mission/multi-probe). **The deliverable is a band, not a point** -
this is the demand side of a system that does not exist, and the honest output is a range
plus a crossover, never a single "a factory needs X FLOPS".

---

## Scope

**Models (pure, deterministic, plain-data - zero pimas imports, no RNG):** compute demand
(a low/nominal/high FLOPS band) for a chosen autonomy level, assembled from sourced
per-task costs, and compared to `probe-sim`'s affordable compute vs distance to find the
autonomy wall. Pure accounting over sourced costs - exactly as power-budget accounts
watts -> FLOPS.

**Does NOT model** (over-nesting guardrails, CLAUDE.md 3): any actual AI/robotics
computation - no neural-net simulator, no SLAM implementation, no motion planner. If a
demand term cannot be sourced it is a `[GAP]`, not a sub-simulation.

---

## Sourced numbers (REFERENCES.md format)

| Value | Unit | What | Source | URL | Verdict |
|---|---|---|---|---|---|
| ~200-400 | MIPS | RAD750 (Perseverance/Curiosity CPU) - integer ops, not FLOPS | Wikipedia RAD750 | https://en.wikipedia.org/wiki/RAD750 | sourced |
| quad-core 2.26 GHz | - | Ingenuity flight computer (Snapdragon 801) - first real onboard autonomy off Earth | Wikipedia Ingenuity | https://en.wikipedia.org/wiki/Ingenuity_(helicopter) | sourced |
| ~898 | GFLOPS | Snapdragon spaceflight co-processor GPU (SA8155P, JPL) | IEEE 11068431 | https://ieeexplore.ieee.org/document/11068431/ | sourced |
| ~100x current flight CPUs | - | HPSC (NASA/AFRL next-gen rad-hard, 8-10 core RISC-V) | NASA HPSC white paper | https://www.nasa.gov/wp-content/uploads/2024/07/hpsc-white-paper-tmg-26jun2024-final.pdf | sourced |
| 144 (= 1.44e14 ops/s) | TOPS INT8 | Tesla FSD HW3 - full self-driving-car autonomy compute | Tesla HW analysis | (industry) | sourced |
| 3.86-4.0 | GFLOPs/inference | ResNet-50 forward pass (one perception inference) | ResNet TensorRT benchmark | https://github.com/DimaBir/ResNetTensorRT | sourced |
| ~0.09 (YOLOv8n) | J/inference | Object-detection energy (perception -> watts) | ScienceDirect S2210537923000124 | https://www.sciencedirect.com/science/article/pii/S2210537923000124 | sourced |
| ~30 FPS on ~1 TFLOPS board | - | Visual SLAM (ORB-SLAM2) real-time - dominant nav load | IEEE 8967814 | https://ieeexplore.ieee.org/document/8967814/ | sourced |
| ~1.39e5 / 9.6e5 / 7.1e7 / 8.6e10 | neurons | fruit fly / honeybee / mouse / human brain | FlyWire (Nature); Frontiers; PMC2776484 | https://www.nature.com/articles/s41586-024-07968-y | sourced |
| 1e18 (1e18-1e25 range) | FLOPS | Human-brain compute equivalent (power-budget already uses 1e18) | Sandberg & Bostrom 2008 | https://www.fhi.ox.ac.uk/brain-emulation-roadmap-report.pdf | [ESTIMATE] (in source) |
| ALFUS: 5 levels, 3 axes | - | Autonomy-level taxonomy (teleop -> full) | NIST SP 1011-I-2.0 | https://www.nist.gov/system/files/documents/el/isd/ks/NISTSP_1011-I-2-0.pdf | sourced |
| ~1e11 (H100 ~8.6e10 FP64) | FLOPS/W | Compute hardware efficiency (supply-side input) | power-budget/REFERENCES.md | (repo) | sourced |
| "FLOPS to run a self-replicating factory" | FLOPS | The demand point value | no such system exists | - | **[GAP]** -> bracket, never a point |

Basis warning (CLAUDE.md 1): MIPS/TOPS (integer) != FLOPS. RAD750 (200 MIPS) and FSD (144
TOPS) are integer-op; neuron and ResNet figures are FLOP. Pin one basis and convert
explicitly, or the demand estimate drifts an order of magnitude for free.

---

## The demand band (confirmed) - the honest headline

Naive linear neuron-scaling from power-budget's 1e18 human FLOPS (1.16e7 FLOPS/neuron,
tagged `[ESTIMATE]`, uncertainty >=2 orders each way):
- honeybee (9.6e5 neurons) -> **1.1e13 FLOPS**
- mouse (7.1e7 neurons) -> **8.3e14 FLOPS**

**The three-line convergence (the module's headline anchor):** a self-driving car's real
full-autonomy compute (1.44e14 ops/s) sits squarely *inside* the honeybee-to-mouse
bracket - three independent lines (two biological proxies + one real system) agreeing on
~1e13-1e15 FLOPS. That coincidence is the most defensible statement the demand side can
make. "FLOPS to run a factory" stays a `[GAP]`; the honeybee(1e13)-to-mouse(1e15) band
with the AV cross-check is the deliverable.

---

## The autonomy wall (confirmed, illustrative)

Supply (from probe-sim) `~ P_1AU * hw_efficiency / d^2` crosses fixed demand at
`d_wall = sqrt(supply_1AU / demand)`. Verified sensitivity:

| P at 1 AU | demand 1e13 (low) | 1e14 (nominal) | 1e15 (high) |
|---|---|---|---|
| 1 kW | 3.16 AU | 1.00 AU | 0.32 AU |
| 10 kW | 10.0 AU | 3.16 AU | 1.00 AU |

The wall moves Sun-ward as demand rises or the array shrinks. The wide spread (0.32-10 AU)
IS the honest uncertainty and must ship with the result, not a false-precision point.

---

## Proposed API

```python
def demand(level: AutonomyLevel, *, perception_fps: float, ...) -> ComputeDemand:
    """Low/nominal/high FLOPS band for an autonomy level, from sourced per-task costs."""

def autonomy_wall(array: SolarArray, level: AutonomyLevel, ...) -> DistanceBand:
    """Distance band where probe-sim supply == demand band."""

def min_level_for_lag(round_trip_time_s: float) -> AutonomyLevel:
    """The autonomy floor forced by light-lag to Earth (ties swarm's coordination regime)."""
```
Pure functions; band-valued outputs; no globals, clock, or RNG.

---

## Validation plan (verified targets)

- Teleoperation level -> onboard demand ~ 0 (Earth does the thinking); assert demand
  collapses toward the housekeeping floor.
- Full autonomy level -> demand in the 1e13-1e15 band; assert AV compute (1.44e14) falls
  inside the band. This is the key sanity assertion.
- Crossover exists: assert a finite `d_wall` where supply == demand; raising the autonomy
  level moves it Sun-ward, a bigger array moves it outward. Assert both monotonicities.
- Band, not point: `demand` returns low < nominal < high spanning >= 2 orders; assert the
  spread is reported, not collapsed.
- Basis: assert MIPS/TOPS inputs are converted to FLOPS with a documented factor before
  comparison (no silent integer-vs-float mixing).

---

## Interface wiring

- **closes the loop with power-budget:** demand is denominated in the same FLOPS (and
  `brain_equivalents`) power-budget's `compute_capacity_flops` / `brain_equivalents`
  produce. Same units, direct comparison. Reuses the ~1e11 FLOPS/W efficiency.
- **-> probe-sim:** consumes `probe_sim.autonomy.compute_headroom_at(array, d)` as the
  supply curve; `autonomy_wall` is the demand-side analogue of the existing
  `max_distance_for_compute` (which today takes an externally-supplied `required_flops` -
  this module produces that argument from first principles).
- **-> swarm:** `min_level_for_lag(round_trip_time)` gives swarm's stale-view probes a
  sourced compute floor for operating alone - more lag -> higher required level -> higher
  demand -> wall moves Sun-ward. Ties the light-speed coordination regime to a compute cost.
- **retires the 0.70 split:** the manuf/compute allocation in mission/multi-probe stops
  being a free choice and becomes bounded by the demand band.

---

## Why it earns a module (with honest caveats)

It has its own reference set (autonomy taxonomy, AV/space processors, per-task costs,
brain counts) distinct from power-budget's thermodynamics-and-brains scope, and it is the
demand *counterpart* to a supply module - a clean seam. It is thin (accounting only), so
if the reference surface ever shrinks it could fold into `probe-sim.autonomy` instead; do
NOT fuse it into power-budget's physics. The demand number is genuinely uncertain and the
module must wear that - band and crossover as the deliverable, `[ESTIMATE]`/`[GAP]` tags
at every use site.
</content>
