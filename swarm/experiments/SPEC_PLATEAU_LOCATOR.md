# Paired-free retarget-cap plateau locator: spec

Issue #73. The `retarget_cap` sweep measures the fuel tax `tau` at a ladder of
`max_retargets` caps to find `cap*(N)`: the smallest cap beyond which the tax
stops moving (the plateau). That sweep is *paired* - it runs both the `instant`
baseline and the `lightspeed` treatment at every cap - which is the expensive
half.

The shortcut: the plateau can be located from the **instant baseline alone**,
without ever running the paired treatment.

## The empirical basis

Within each `(N, cap)`, the instant-mode bounce depth

```
b = W_inst / N = wasted_arrivals(instant) / n_stars
```

moves in lockstep with the paired fuel tax `tau`. Across every row of the
committed `retarget_cap.json` and `retarget_cap_scale.json` (top-level and `p2`
blocks, N = 400 .. 262 144), the sign of the step in `b` from one cap to the next
matches the sign of the step in `tau`, and `Delta b -> 0` coincides with
`Delta tau -> 0` at the plateau. So the *location* of the plateau (not its tax
value) is fully determined by the instant runs.

This is a locator, not a law. It says nothing new about physics; it is a
wall-clock shortcut that exploits an observed correspondence in already-committed
data. `tests/test_winst_locator.py` pins the correspondence against those JSONs so
a future fold change that breaks it fails loudly.

## The pure decision function

`locate_plateau(b_by_cap: dict[int, float], threshold: float) -> int | None`

- Input: a mapping `cap -> b` (bounce depth at that cap) and a convergence
  `threshold` (default `0.05`, see below).
- For each cap `k` in ascending order whose double `2*k` is also a key, compute
  `Delta b = b[2*k] - b[k]`.
- Return the **smallest** such `k` with `Delta b < threshold` - the plateau is
  reached at `k`, because doubling the cap no longer moves `b`.
- Return `None` when no doubling pair converges: the plateau lies above the tested
  ladder (need larger caps), or - the honest #86 finding at large N - there is no
  plateau in range and `cap` is a lower bound, not a saturation point.

`b` is monotonically non-decreasing in `cap` (more retarget bookkeeping can only
reclassify more arrivals as bounces), so `Delta b >= 0` in expectation and a small
positive step is the convergence signal; the strict `< threshold` (not `abs`)
therefore also, correctly, treats a noise-driven negative step as converged. The
comparison is strict, so `Delta b == threshold` is *not* converged.

## The threshold (0.05) is a diagnostic tolerance, not a physical number

`0.05` is a bounce-depth step in units of arrivals-per-star. It is a tunable knob
on a diagnostic tool, not a measured quantity, and every use site exposes it. Its
default is motivated by the committed N=400 rows, where the converged step is
`Delta b = 0.000` (cap 16 -> 32) and the last still-climbing step is
`Delta b = 0.120` (cap 8 -> 16): `0.05` sits cleanly between them, so at N=400 the
locator returns `cap* = 16`. See `REFERENCES.md`.

## The instant-only sweep and CLI

`--locate-plateau N [--plateau-caps 8,16,32] [--plateau-seeds K]
[--plateau-threshold T] [--plateau-paired]`:

1. Run **instant-only** folds at each cap (few seeds); capture `wasted_arrivals`.
2. `b_k = median_seeds(W_inst / N)`.
3. `cap* = locate_plateau({k: b_k}, T)`.
4. Print the ladder (`cap`, `b_median`, `Delta b`) and the verdict. With
   `--plateau-paired` and a located `cap*`, run **one** paired measurement at
   `cap*` to report the tax value there.

Wall-clock (issue #73, N=200 000): three instant-only folds x 8 seeds ~= 12 min,
vs the paired 5-cap sweep at ~40 min - roughly 3x, more when extended to
intermediate N.

## Scope / non-goals

- Locates `cap*` only. The **tax value** at the plateau still needs one paired
  run (step 4).
- No closed form spanning multiple N; the plateau moves with N.
- Not a fine-grained `tau(cap)` curve - only the plateau location (or its
  absence).

## Correctness criteria (how we know it is right)

- Unit: `locate_plateau` on synthetic ladders - plateau at the first pair, at a
  later pair, no plateau, a missing `2*k` partner, a negative step, the
  `Delta b == threshold` boundary, and degenerate (empty / single cap) inputs.
- Data: feed the committed `b` medians from all four `retarget_cap*` blocks into
  `locate_plateau` and assert `cap*` = 16 at N=400 and `None` at N >= 32 768 (the
  #86 no-plateau regime), at the default threshold.
- Correspondence: across every consecutive cap pair in all four blocks, `b` and `tau`
  are co-monotone up to seed noise - neither falls (while the other climbs) by more
  than a small noise floor (issue #73's verification path). Strict sign equality is
  too tight in the near-zero-tax regime at large N, where a physically flat step
  (e.g. cap 2 vs 4 at N=262,144, tau ~ 0.27%) can jitter by ~0.0002pp.
- End-to-end fold: the instant-only sweep at a tiny N reproduces a direct
  `simulate_swarm(coordination="instant", ...)` bounce depth exactly
  (deterministic fold).
