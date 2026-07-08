# autonomy - how much thinking a probe needs (not just how much it can afford)

A probe light-hours from Earth cannot phone home for instructions; it has to run its own
perception and control. `probe-sim` already worked out how much compute a probe can
*power* at a given distance (it falls as 1/d^2 with the sunlight). What was missing was
the other half: how much compute it actually *needs*. Without that, `mission` and
`multi-probe` just assumed a 0.70 manufacturing / 0.30 compute power split. This module
supplies the demand, and where demand meets the falling supply is the **autonomy wall**.

## What it models

`autonomy.py`, pure functions:

- **`required_compute_band()`** - the demand as a sourced **band, not a point**: honeybee
  brain (~1e13 ops/s), a self-driving car (~1.4e14 ops/s / 140 TOPS), and a mouse brain
  (~1e15 ops/s). The engineered self-driving figure lands between the two biological
  estimates - three independent lines converging on 1e13-1e15.
- **`compute_fraction_needed(...)`** - the **derived** compute power fraction that
  replaces the hand-set 0.30: it falls out of sourced demand and available power (140
  TOPS at 1e10 FLOPS/W on a 100 kW bus is 0.14, not 0.30).
- **`autonomy_wall_au(supply_1AU, required)`** = `sqrt(supply_1AU / required)` - the
  distance where affordable compute drops below what the probe needs. Heavier "brains"
  hit the wall sooner. Verified to equal `probe-sim`'s supply-side
  `max_distance_for_compute` - the loop is closed.

All numbers sourced in [`REFERENCES.md`](REFERENCES.md). Pure, deterministic, no pimas,
no RNG (CLAUDE.md 7).

## What it does NOT model (over-nesting guardrails, CLAUDE.md 3)

No neural-net, SLAM, or planner simulation - just accounting over sourced per-system
compute costs, exactly as `power-budget` does for watts->FLOPS. "FLOPS to run a whole
factory" is left as a tagged `[GAP]`, bounded to the anchor band rather than invented.

## What it found

- **Autonomy has its own wall, and it can be closer in than the power wall.** A probe
  that needs mouse-brain-scale compute runs out of affordable thinking far sooner than
  one that needs only honeybee-scale - the required compute, not just the available
  power, sets how far a probe can operate alone.
- **The 0.70/0.30 split was a free parameter, and now it is not.** The compute share is
  derived from demand and power, so it moves with distance and hardware efficiency
  instead of being assumed.

## Interfaces

- **<- `probe-sim`:** reuses `max_distance_for_compute` and `SolarArray`; supplies the
  sourced `required_flops` they treated as free.
- **reuses `power-budget`:** watts<->FLOPS conversion.
- **-> `mission` / `multi-probe`:** the derived compute fraction retires their 0.70/0.30
  choice; the autonomy wall is a new operating limit.

## Run the tests

```
uv run --extra dev pytest -q
```

8 tests: the three-line demand band, the power/capacity inverse, the derived compute
fraction (0.14, not 0.30) and its infeasibility guard, the 1/d^2 supply, the wall vs
demand ordering, and the loop-closure check against `probe-sim`.
