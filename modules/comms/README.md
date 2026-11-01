# comms - how fast a probe can phone home

A self-replicating probe is only as useful as the findings it can send back. And the
further it goes, the slower it can talk: a deep-space link's data rate falls as the
**inverse square of distance**, the same law that dims its sunlight. This module turns
distance into an achievable downlink rate, and from there into a new wall the fleet
runs into.

## What it models

`link.py`, a handful of pure functions:

- **`data_rate_at(distance)` - the two-regime rate.** `R(d) = min(k/d^2, R_max)`. Far
  out the link is **power-limited** and falls as 1/d^2 (Shannon meeting Friis, confirmed
  directly by JPL's DSOC laser-comms demo). Near Earth it is **rate-limited**: the modem
  tops out at a fixed ceiling `R_max` no matter how strong the signal.
- **`calibrate_k(rate, distance)` - fit the one constant** `k = R * d^2` to a real
  mission anchor. The two DSOC anchors (25 Mbps at 1.506 AU, 8.3 Mbps at 2.582 AU) fit
  to k ~ 56 and agree to 2.5% - the built-in confirmation that the law holds.
- **`return_backlog(...)` - the data-return wall.** When a probe generates science
  faster than its link can return it, an un-sent backlog grows without bound.
- **`aggregate_return_rate_mbps(...)` - the fleet consequence.** Once every link is
  saturated, total knowledge return is the *sum of per-probe link rates*, not probe
  count. Building more probes than the 1/d^2 links can drain buys diminishing returns.

`k` and `R_max` default to the DSOC optical calibration but are parameters: RF vs
optical is the same law with a different `k` (10-100x), not a second module. Distance
is the **Earth-spacecraft range** (not heliocentric). All figures sourced in
[`REFERENCES.md`](REFERENCES.md). Deterministic, plain data, no RNG (CLAUDE.md §7).

## What it does NOT model (over-nesting guardrails, CLAUDE.md §3)

No per-photon link budget (pointing jitter, PPM slot statistics, DSN gain-vs-elevation);
no DSN scheduling/contention; no modulation/coding internals; no uplink or relay
topologies. The Friis/Shannon derivation lives in REFERENCES to justify the 1/d^2 shape;
the runtime is one division and a clamp.

## What it found

- **The link is the bottleneck, not the antenna count.** A probe at 5 AU returns only
  ~2.2 Mbps on the DSOC calibration; a probe generating 100 Mbit/s of science there
  builds an unbounded backlog. Aggregate fleet knowledge saturates at the sum of the
  distance-limited link rates.
- **Two regimes with a sharp crossover** at `d = sqrt(k/R_max) ~ 0.46 AU`: inside it
  the hardware limits you; outside it, physics does.

## Interfaces

- **-> `power-budget`:** comms is a fourth power draw (transmit power ~5% of bus power,
  derived from Voyager/New Horizons). power-budget allocates watts; comms turns them
  into bits/s.
- **parallel to `probe-sim`:** `data_rate_at(distance)` is a third 1/d^2 curve on the
  distance axis, alongside solar power and compute headroom - same shape, clean seam,
  different (Earth-range) basis.
- **composes with `swarm` (does not fuse):** swarm's `lightspeed` coordination is
  *latency* (news no sooner than dist/c); comms is *throughput* (how fast it then
  trickles in). A future coupling - swarm's news carrying a finite bit budget - is a
  later slice.

## Run the tests

```
uv run --extra dev pytest -q
```

12 tests: the two-anchor calibration agreeing to 2.5%, the 1/d^2 ratio check, both
regimes and their crossover, the near/far edges, and the data-return wall (unbounded
backlog + fleet saturation at sum-of-rates).
