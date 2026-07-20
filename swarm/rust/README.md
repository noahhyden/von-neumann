# swarm_rust: Rust drop-ins for the swarm hot paths

Two trees coexist:

- **Pointer kd-tree** - the original (`_build_kdtree` in `swarm/src/swarm/sim.py`,
  mirrored by `nn_impl` / `run_fill` here). Works at any `n_stars >= 1`. Serves
  the frozen non-power-of-two result JSONs in `swarm/experiments/results/*.json`
  (the paper's pinned drift-guard artifacts) - those never regenerate, so this
  tree stays around as their oracle.

- **Flat p2 kd-tree** - a heap-indexed perfect binary tree over
  `n_stars = 2^k, k >= 3` (i.e. `n_stars in {8, 16, 32, ..., 262144, ...}`).
  Node `i` has children at `2i+1, 2i+2` and parent at `(i - 1) >> 1`, so the
  `lo`, `hi`, `parent` arrays vanish - the p2 discipline's bit-shift dividend.
  Same median-split rule as the pointer tree, so at matching p2 N the flat tree
  is bit-identical (verified: `tests/test_flat_kdtree_oracle.py`).

## When each fires

The two trees are not mutually exclusive - both live in `swarm_rust`. The
pointer tree fires via `nearest_unsettled` / `run_fill`; the flat tree via
`build_flat_kdtree` / `nearest_unsettled_flat` / `mark_settled_flat` /
`run_fill_flat`. `swarm.sim._simulate_swarm_rust` dispatches at the boundary:

- **`n_stars = 2^k, k >= 3`** and the flat functions are compiled -> the flat
  tree is built in Rust and `run_fill_flat` owns the event loop. Byte-identical
  aggregates to the pointer path at matching N
  (`tests/test_flat_run_fill_oracle.py`).
- Non-p2 N, or an older crate build missing the flat functions -> the pointer
  tree + `run_fill` (unchanged).
- `SWARM_NO_RUST_FLAT=1` env override forces the pointer path at p2 N too,
  useful for A/B benching and the oracle harness.

## What p2 buys, honestly

- **Query wall-clock: ~4% at N in {1024, 4096, 32768}** (see
  `experiments/bench_flat_kdtree.py`). Modest, and expected: the pointer tree
  was already using SoA arrays with cache-friendly layout; the flat tree's win
  is the elimination of two per-internal-node array loads (`lo[i]`, `hi[i]`)
  in favor of a shift+add on `i`, plus a cheaper leaf test (`i >= M-1` vs
  `axis[i] == -1`). This is a real speedup, not a large one.

- **Whole-fill wall-clock: 1.3-1.8x** (see `experiments/bench_flat_run_fill.py`).
  The per-query win compounds through the event loop; inflight sees the biggest
  lift (1.79x at N=4096) because it hits the NN kernel more often via the
  decrease-key reschedule path. `simulate_swarm` at p2 N gets this for free
  now that the dispatch is wired.

- **Contiguous 8-star leaves.** `xs_p, ys_p, zs_p` are the star coordinates
  stored in **permuted** order, one leaf's 8 stars at a stretch. A future
  SIMD leaf scan (AVX2: 4 f64 per lane; AVX-512: 8 f64 per lane) reads them
  as one aligned block. This is where the layout is likely to pay a real
  multiple; not built here.

- **Ensemble ergonomics.** New sweeps at p2 seed counts (128, 256, 512) shard
  evenly across any K in `{1, 2, 4, 8, ...}` boxes with the `--seed-slice N/K`
  CLI (issue #33 item 2). The current `n_seeds in {6, 48}` counts don't. The
  coordination-tax paper needs this at 200k+ N with N seeds well beyond the
  current 8.

- **Kd-tree balance.** At `n_stars = 2^k`, every leaf sits at depth exactly
  `k - 3`, so the traversal stack depth is a compile-time-knowable constant
  (18 at N=262144). The pointer tree is near-balanced but has slack.

## Non-perfect p2: the documented escape

The perfect-p2 layout requires `n_stars = 2^k, k >= 3`. Three degrees of freedom
if a future measurement wants an N that isn't:

1. **Padded p2 with sentinels.** Pad up to the next `2^k * 8` with sentinel
   stars at `+INF` coords, permanently settled (`sy = +INF, nuns = 0` at the
   sentinel leaves at build time). Existing pruning dismisses `nuns == 0`
   subtrees, so sentinels cost only build time.
2. **Ragged last-level leaves.** Allow the last-level leaves to hold 1..8
   stars via a small `bucket_offsets` array over just the last level.
3. **Non-perfect tree.** Drop the perfect-balance assumption; internal nodes
   split near-median; add an `is_leaf` bit. Loses ~half the pointer-free win
   (still no `lo`/`hi`).

For today: `build_flat_kdtree` raises `ValueError` if N is not a power of two
`>= 8`. The error is at the build boundary so callers can't silently get a
broken tree.

## Determinism

All the determinism disciplines from the pointer-tree Rust port apply here:

- Same left-to-right f64 arithmetic order as the Python reference.
- No `fastmath`. `f64::sqrt` is the correctly-rounded hardware sqrt.
- `total_cmp` for float ordering (agrees with `partial_cmp` on non-NaN, and
  galaxy coords are never NaN); ties on `(coord, index)` break by index.
- No wall clock, no ambient RNG. The build is a pure fold of `(xs, ys, zs)`.

See `SPEC_FLAT_KDTREE.md` in this directory for the full layout / API spec,
including the mutation-red-team results and the bit-identity contract.

## Building

```sh
cd swarm
uv run --extra dev maturin develop --manifest-path rust/Cargo.toml --release
uv run --extra dev pytest tests/test_flat_kdtree_oracle.py -q
```
