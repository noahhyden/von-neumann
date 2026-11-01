# Flat-array kd-tree in Rust: spec

## Motivation

The pointer-based kd-tree (`_build_kdtree` in `swarm/src/swarm/sim.py`, mirrored in
`swarm/rust/src/lib.rs::nn_impl`) uses per-node `lo[i]`, `hi[i]`, `parent[i]` arrays -
one memory load per traversal step. At `N=2^k` stars with `_KD_LEAF=8`, the tree
becomes a perfect binary tree with `M = N/8` leaves at the same depth `k-3`, and
the child/parent lookups collapse to arithmetic. This is the substrate for later
SIMD-friendly leaf scans; it is also the smallest non-trivial place a
"power-of-two standardization" earns its keep in this repo.

The pointer tree is **not** deleted. It remains the reference for the frozen,
non-p2 result JSONs in `swarm/experiments/results/`, which are the paper's pinned
drift-guard artifacts. The flat tree fires only at p2 `n_stars`; future
measurements adopt p2 sizes and get the fast path.

## Layout

For `N = 2^k` with `k >= 3` (i.e. `N in {8, 16, 32, ..., 262144, ...}`):

- `M = N / 8` leaves, `M - 1` internal nodes, `2M - 1` total nodes.
- BFS/heap ordering: root at index `0`; children of `i` at `2i+1` and `2i+2`;
  parent of `i` at `(i - 1) >> 1`.
- Internal nodes at indices `0 .. M-2` (inclusive).
- Leaf nodes at indices `M-1 .. 2M-2` (inclusive).
- Leaf `j` (0-indexed among leaves, `j in 0..M`) sits at flat node index `M-1+j`
  and owns exactly 8 stars at permuted positions `j*8 .. j*8+7`.

### Star permutation

The build reorders stars so each leaf's 8 stars are contiguous in memory:

- `star_perm: [i32; N]` - `star_perm[permuted_idx] = original_idx`. Query
  returns the star's *original* index (via this mapping), for bit-identity with
  the pointer tree.
- `xs_p, ys_p, zs_p: [f64; N]` - coordinates in permuted order. Leaf scans over
  8 contiguous stars, ready for later SIMD.
- `sy_p: [f64; N]` - settle year in permuted order, `-1.0` at build. Updated
  by `mark_settled_flat` using the permuted index.
- Inverse permutation `star_perm_inv: [i32; N]` - `star_perm_inv[original_idx]
  = permuted_idx`. Needed by `mark_settled_flat` to locate the star's leaf
  from an original index.

### Node arrays (BFS order, length `2M-1`)

- `axis: [i8; 2M-1]` - split axis (0=x, 1=y, 2=z) for internal nodes; leaves
  hold `-1` (a defensive belt-and-suspenders; the leaf test is `i >= M-1`).
- `split: [f64; 2M-1]` - split coordinate for internal nodes; `0.0` at leaves.
- `bxmin, bxmax, bymin, bymax, bzmin, bzmax: [f64; 2M-1]` - axis-aligned
  bounding box per node (unchanged semantics vs pointer tree).
- `nuns: [i32; 2M-1]` - live unsettled count in the subtree. All-`N`-in-root
  at build minus origin, decremented on settle. Internal-node counts are the
  sum of child counts (Bentley 1975; identical to pointer-tree contract).
- `tsmax: [f64; 2M-1]` - largest settled_year in subtree (`-1.0` at build,
  raised guarded on `mark_settled_flat`).

### No `lo`, `hi`, `parent` arrays

The whole point: those are replaced by `2i+1`, `2i+2`, `(i-1) >> 1`. This is
where the "bit-shift shenanigans" earn their name.

## Build rule

Same median-split as the pointer tree, so at matching p2 N the flat and
pointer trees produce **bit-identical partitions**:

- Widest axis of the node's bounding box (ties: x > y > z).
- Sort star indices by `(coord, star_index)` (deterministic tie-break, matches
  `sim._build_kdtree`).
- Split at `mid = current_range.len() / 2`. At `N = 2^k` and `_KD_LEAF = 8`
  this bottoms out at exactly 8 stars per leaf, at the same depth `k-3` for
  every leaf.

## Query rule

`nearest_unsettled_flat` is a straight port of `nn_impl` (the current Rust
pointer-tree query in `lib.rs`), with two mechanical substitutions:

- Instead of pushing `lo[node]` and `hi[node]` onto the traversal stack, push
  `2*node + 1` and `2*node + 2` respectively.
- Instead of the leaf test `axis[node] == -1`, use `node >= M - 1`.

All other semantics (dhi/dlo pruning, `is_instant` short-circuit, the
`(d^2, lowest-index)` tie-break, the `is_instant`/lightspeed light-cone gate)
are copied verbatim. The star index it returns is `star_perm[permuted_idx]` -
the original index, for equality with pointer-tree results.

## Settle rule

`mark_settled_flat(original_idx, year)`:

1. Look up `pidx = star_perm_inv[original_idx]`.
2. Walk from the leaf `node = M - 1 + (pidx / 8)` up to the root using
   `node = (node - 1) >> 1` at each step, terminating when `node == 0` after
   updating.
3. At each visited node: `nuns[node] -= 1`; if `year > tsmax[node]`, set
   `tsmax[node] = year`.
4. Also set `sy_p[pidx] = year` (the leaf's stored settle year).

This is `O(log N)` and pointer-free.

## Bit-identity contract

**Claim**: for the same seeded galaxy at `N = 2^k, k >= 3`, and any sequence
of `(px, py, pz, year, is_instant, excl)` queries interleaved with
`mark_settled` calls, the flat kd-tree returns the same star's *original*
index as the pointer tree, for every query, byte-identical.

This is achievable because:

- The build sees the same inputs and applies the same median-split rule.
  At p2 N the split points are the same.
- The query performs the same DFS traversal and the same `(d^2, index)`
  tie-break; only the child/parent lookup mechanism differs.
- `mark_settled` updates the same set of subtree counts; the walk order is
  leaf-to-root either way.

Verified by the oracle in `swarm/tests/test_flat_kdtree_oracle.py` (see
tests-first section below).

## Non-perfect p2: the escape path (documented, not built)

If a future measurement needs an `N` that is not `2^k` (or a different
`_KD_LEAF`), the layout supports three degrees of freedom, in order of
increasing invasiveness:

1. **Padded p2 with sentinels.** Pad the star list to the next `2^k * 8` with
   sentinel stars at `+INF` coordinates and marked permanently settled
   (`sy = +INF, nuns` at the sentinel leaves = 0 from the start). The pruning
   already dismisses `nuns == 0` subtrees, so sentinels cost only build time,
   not query time.
2. **Ragged last-level leaves.** Allow the last `M` leaves to hold 1..8 stars
   instead of exactly 8. `2M-1` node count and BFS indexing survive; only the
   per-leaf scan bound changes (`bucket_offsets` returns as a small array over
   the last level).
3. **Non-perfect tree.** Drop the perfect-balance assumption entirely; each
   internal node splits its stars near-median, and the heap indexing needs an
   `is_leaf` bit per node. Loses ~half the pointer-free win (still no
   `lo`/`hi`; still has `is_leaf`).

For this PR (see "scope" below) only the perfect-p2 layout is implemented;
the escape path is documented so a later PR knows the entry point.

## Public API (this PR)

Added to the `swarm_rust` pyo3 module:

- `build_flat_kdtree(xs, ys, zs) -> dict` - builds and returns the flat
  arrays as numpy views. Raises `ValueError` if `xs.len()` is not `2^k` for
  some `k >= 3`.
- `nearest_unsettled_flat(px, py, pz, year, is_instant, flat_arrays..., excl,
  n_ex) -> i64` - the query; returns the original star index or -1.
- `mark_settled_flat(original_idx, year, flat_arrays...)` - the settle
  update.

`run_fill_flat` (the full event loop on the flat tree) is intentionally
deferred to a follow-up PR to keep this one small and heavily-verified. The
same reasoning as `run_fill` in `lib.rs` will apply.

## Scope of this PR

**IN:**

- Rust `build_flat_kdtree`, `nearest_unsettled_flat`, `mark_settled_flat`.
- Oracle tests at `N in {8, 32, 128, 512, 4096}` proving bit-identity against
  the pointer tree.
- p2-invariant tests: `build_flat_kdtree(N)` errors at `N in {6, 300, 500,
  1000, 200000}` (non-p2 or `< 8`).
- Mutation red-team: 4 targeted mutants that must fail the suite.
- Bench: `nearest_unsettled` vs `nearest_unsettled_flat` at `N=4096` and
  `N=32768`, 128 queries each, wall-clock report in the PR body.
- Docs: `swarm/rust/README.md`, `swarm/REFERENCES.md` citations.
- 100% coverage on the new Rust functions (via the oracle tests).

**OUT (follow-up PR):**

- `run_fill_flat` (full event loop on the flat tree).
- Wiring `simulate_swarm` to prefer the flat path at p2 N.
- Migrating `experiments/measure.py` measurements to p2 sizes.
- Regenerating result JSONs at p2 sizes.
- Retiring the pointer tree in Python.

## Merge before next

Nothing else starts until this lands green with all guards intact.
