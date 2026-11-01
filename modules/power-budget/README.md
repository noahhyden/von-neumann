# power-budget - making vs. thinking, per watt

A self-replicating factory that has to run itself light-minutes from Earth can't
spend all its power making things - it has to spend some *thinking* (autonomy,
control, perception). This module is the pure accounting of that trade: split a
fixed, solar-limited power budget among **manufacturing**, **compute**, and
**housekeeping**, and convert compute-watts into actual throughput.

It's anchored at both ends by hard references:

- the **Landauer limit** (`k_B·T·ln2`) - the thermodynamic floor on energy per bit,
  ~2.9e-21 J at 300 K, i.e. no more than ~3.5e20 irreversible bit-ops per joule, ever;
- the **~20 W human brain** - the canonical scale for general intelligence per watt.

"Intelligence-per-watt" is then just throughput per watt, read against those anchors.

## What it models today

- **`physics.py`** - `landauer_limit_j_per_bit(T)` and `max_bit_operations_per_joule(T)`
  (derived from the exact Boltzmann constant), the 20 W brain power, and
  `brain_equivalents(flops)` against an `[ESTIMATE]` brain-FLOPS scale.
- **`budget.py`** - `PowerBudget` (a total split into manufacturing/compute/
  housekeeping fractions, validated and conserved) and `compute_capacity_flops(power,
  efficiency)`.

## What it found

Thinking is thermodynamically cheap but practically expensive. The Landauer floor
(~2.9e-21 J per erased bit at 300 K) sits roughly 9 to 11 orders of magnitude below
what real hardware spends per operation, so the binding constraint on a probe's onboard
intelligence is hardware efficiency and waste-heat rejection, **not** thermodynamics.
Read against the ~20 W human brain, the takeaway is that autonomy far from Earth is a
power-and-cooling problem, not a physics one.

## What's next (see [`../ROADMAP.md`](../ROADMAP.md))

Couple it to `probe-sim`/`closure-sim`: the delivered solar power *is* the total this
module divides, so a probe's compute headroom (and thus its autonomy) becomes a
function of heliocentric distance. Then a `frontend` surface.

## Architecture

A pure, deterministic, one-shot calculation in plain data with **zero pimas imports**
(CLAUDE.md §7). Any interactive view lives in `frontend/` and reads this model.

## Develop

```sh
uv run --extra dev pytest -q
```

Every number traces to a source - see [`REFERENCES.md`](REFERENCES.md) (Landauer 1961,
Raichle & Gusnard 2002, Sandberg & Bostrom 2008, SI Boltzmann constant).
