# mission - the whole probe operation, end to end

This module does one thing: it **runs the entire story once**, as a single
deterministic function. Launch a small self-replicating seed, fly it out to some
distance from the Sun, let its solar array power the factory, split that power
between *building more of itself* and *thinking for itself*, and see whether it grows
into a full installation - then price what you saved by not launching the finished
mass.

It writes **no new physics and no new numbers**. Every stage is a call into one of the
four sibling modules through its public API (CLAUDE.md §4); `mission` is only the
wiring that makes them one flow. That is the point the user asked for: a very simple,
honest, end-to-end proof that the existing pieces already compose.

## The six stages

| # | Stage | Module used | What it answers |
|---|-------|-------------|-----------------|
| 0 | **Launch** | launch-economics | How much mass do we actually launch (seed + vitamins), and why is $/kg so high? (the rocket equation's propellant fraction) |
| 1 | **Closure** | closure-sim | What fraction of its own mass can the factory make locally? |
| 2 | **Arrive** | probe-sim | How much solar power reaches the probe at distance *d*? (inverse-square) |
| 3 | **Split** | power-budget | Divide that power into build / think / housekeeping. |
| 4 | **Replicate** | closure-sim | Feed the *manufacturing* share into the replication sim - does output ever reach target? |
| 5 | **Think** | power-budget | What compute does the *compute* share buy? (FLOPS, brain-equivalents) |
| 6 | **Payoff** | launch-economics | Launch-mass leverage and dollars saved vs. launching the finished installation. |

The single scalar that ties the middle together is **delivered power (W)**: the array
sets it from distance, the split divides it, and the manufacturing slice becomes the
replication sim's `available_power_kw`. Move the probe outward and the whole chain
responds - power falls as 1/d², the factory slows, and past a crossover distance it
never reaches target at all.

## What it reconciles, and one honest caveat

- **Seed mass is no longer duplicated.** launch-economics' `comparison_from_closure`
  takes `seed_mass_kg` as an independent argument; the mission feeds it the factory's
  own `replication.seed_mass_kg`, so the two can't drift.
- **The power split is decided once.** probe-sim's `range.py` hands the factory 100%
  of delivered power; the mission instead routes only the *manufacturing* share to
  replication and the *compute* share to throughput - the split is the whole story.
- **Caveat (a documented `[GAP]`):** there is still no sourced per-module mass
  breakdown for the Borgue & Hein probe, so the mission's factory is closure-sim's
  **lunar-regolith seed scenario** used as a stand-in - a real, sourced bill of
  materials, but not a probe-specific one. This is stated in the UI and in
  REFERENCES.md; no masses are invented (CLAUDE.md §1).

## Run it

```sh
uv run --extra dev python -c "from mission import default_mission_scenario, run_mission; print(run_mission(default_mission_scenario()))"
uv run --extra dev pytest -q          # 12 end-to-end behavior tests
```

Override any scenario scalar by keyword:

```python
from mission import default_mission_scenario, run_mission
run_mission(default_mission_scenario(distance_au=5.203))   # power-starved at Jupiter
run_mission(default_mission_scenario(fraction_compute=1.0, fraction_manufacturing=0.0))  # all think, no build
```

## Shape (CLAUDE.md §7)

`run_mission(scenario) -> MissionResult` is a pure, deterministic fold over plain
data with zero pimas imports. It is the **ground truth** the frontend's TypeScript
port (`frontend/src/mission.ts`) is parity-tested against. All sourced numbers and
flagged design choices are in [`REFERENCES.md`](REFERENCES.md).
