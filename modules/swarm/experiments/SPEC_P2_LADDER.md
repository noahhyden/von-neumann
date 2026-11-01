# Dual-ladder p2 companion: spec

Follow-up to PRs #79 / #80 / #81 (flat p2 kd-tree + `run_fill_flat` + target-cpu
tuning). Those PRs unlocked a ~1.2-1.5x whole-fill speedup at any `n_stars = 2^k`
via the flat p2 kd-tree; this migration adds a **p2 companion sweep alongside
every existing measurement** so the coordination-tax paper's numbers get:

- a second, cleanly-p2 lever arm for every headline claim, and
- coverage of the fast-path (`run_fill_flat` fires at p2 N; the historical
  non-p2 ladder still uses the pointer path).

## Guiding constraint: preserve every existing key byte-for-byte

The frozen result JSONs are the paper's pinned drift-guard artifacts. **No
committed number in a shipped JSON may move.** The p2 ladder adds new keys
alongside the historical ones; historical `data`, `config`, `scale_regression`
etc. stay untouched.

## Schema

Every result JSON grows a top-level `p2` key holding a self-contained
companion:

```json
{
  "schema_version": 3,          // unchanged
  "generator": "...",           // unchanged
  "measurement": "...",         // unchanged
  "config": {...},              // unchanged
  "data": {...},                // unchanged - the historical (non-p2) ladder
  "scale_regression": {...},    // unchanged
  "p2": {
    "config": {...},            // p2 companion config (same keys, p2 N values)
    "data": {...},              // p2 companion per-N blocks
    "scale_regression": {...}   // p2 companion slope (only for N-sweeps)
  }
}
```

For fixed-N sweeps (`branching`, `concurrency`, etc.), `p2.data` holds a single
block at N=512 alongside the historical N=300/400/500 block.

For N-sweeps (`finite_size`, `finite_size_interior`, `finite_size_periodic`),
`p2.data` holds the p2 ladder blocks and `p2.scale_regression` holds an
independent OLS slope on the p2 lever arm.

For scale companions (`*_scale.json`, currently at N=200_000), `p2.data`
holds a single block at N=262_144.

## Sweep sizes

### N-sweeps: finite_size / finite_size_interior / finite_size_periodic

Historical ladder: `[(300, 48), (600, 48), (1200, 48), (2400, 48), (4800, 32),
(9600, 32), (24000, 24), (48000, 16), (200000, 8)]`

P2 companion ladder: `[(256, 48), (512, 48), (1024, 48), (2048, 48), (4096,
32), (8192, 32), (16384, 24), (32768, 16), (262144, 8)]`

Nine points each. Roughly matched sizes (256 vs 300, ..., 262144 vs 200000).
Seed counts match the historical rows exactly so seed cost is comparable.

### Scale companions: *_scale.json

Historical: N=200_000.
P2 companion: N=262_144 (next p2 above 200k). Same seeds as the 200k version.

Files:
- `concurrency_scale.json`
- `floor_bracket_scale.json`
- `retarget_cap_scale.json`
- `clumpiness_scale.json`
- `lambda_sweep_scale.json`
- `branching_scale.json` (there's no separate `branching_scale.json` yet -
  branching's scale companion may live inside `branching.json`; verify.)

### Fixed-N base sweeps

Historical: n_stars = 300 / 400 / 500 (varies per measurement).
P2 companion: N=512 for all.

Files: `branching`, `concurrency`, `floor_bracket`, `retarget_cap`,
`lambda_sweep`, `dt_artifact`, `validation`, `clumpiness`.

Note: `dt_artifact` is stepping="fixed" and doesn't benefit from the flat
path (which only fires for stepping="event"). Included anyway per the
"do them all" scope decision - it will run at N=512 via the pointer path.

## What the p2 companion validates

1. **The tax-vs-N decline claim survives the p2 ladder.** If `finite_size`'s
   -7.0 pp/decade slope over 300..200_000 is a genuine bulk saturation, the
   256..262_144 slope should match within CI. If it turns out to be scaffold
   sensitivity, the p2 ladder will disagree - that's the honest finding.
2. **The scale companions hold at N=262_144.** Every `*_scale.json` claim
   ("does the mechanism hold at 200k?") gets a second data point at a slightly
   larger, cleanly-p2 N.
3. **The fast path (`run_fill_flat`) runs the whole ladder.** Every p2
   companion above N=8 dispatches through `run_fill_flat` (via the wiring in
   PR #80). Bit-identical to the pointer path at matching N per the oracle -
   so the p2 numbers are trustworthy to the same standard as the frozen
   non-p2 numbers.

## What the p2 companion does NOT do

- **No historical number moves.** The old ladder is still the paper's canonical
  ladder for now. If the paper eventually wants to cite p2 numbers, that's a
  separate call.
- **No new physics.** Same fold, same seeds, same paired instant/lightspeed
  design. Only N moves.

## Drift-guard extension

`swarm/tests/test_measure_results.py` currently exercises each JSON's smallest
non-p2 N for two seeds. It grows a companion assertion for each JSON's
smallest p2 N (also two seeds), so a fold change breaking either path fails
here.

## Cost estimate (measured on the k02 dev machine, 2026-07-20)

Single-thread per-paired-seed wall-clock at each p2 N (via `_paired`, so this is
one instant + one lightspeed run):

| N | s/pair |
|---|---|
| 256 | 0.004 |
| 512 | 0.009 |
| 1024 | 0.018 |
| 2048 | 0.040 |
| 4096 | 0.091 |
| 8192 | 0.156 |
| 16384 | 0.281 |
| 32768 | 0.656 |
| 262144 | 8.792 |

At those numbers a full p2 regen totals **~54 min single-thread, ~7 min at
SWARM_WORKERS=8** on 16-core k02. Dominant cost is `clumpiness_scale` at
N=262_144 (~30 min single-thread; 5 sigma levels × 5 lambdas × 8 seeds =
200 pairs × 8.8s each). Every other measurement is 1-6 min single-thread.

## CLI + resumability

```sh
# Run p2 companions on top of existing historical JSONs (skip if p2 key present):
uv run --extra dev python -O -m experiments.measure --p2

# Regenerate p2 companion for one JSON:
uv run --extra dev python -O -m experiments.measure --p2 --force clumpiness_scale

# Env: SWARM_WORKERS=<N> for parallelism.
```

If the p2 companion is missing from a JSON, the corresponding p2 drift-guard
test in `tests/test_measure_results.py` skips (not fails); so a partial
migration is safe to commit.
