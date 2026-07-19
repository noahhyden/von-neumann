# Compute hardware inventory

The machines available to run this repo's models and experiments. The heavy runs
live inside the modules (for example `swarm`'s event-driven paired ensembles), but the
hardware is a shared, repo-wide resource, so it is recorded here rather than under any
one module. This is a personal-stack inventory that grows over time: add an entry per
machine as the stack changes (new laptop, home desktop, a cloud ensemble).

Each entry records only the specs that bear on compute, and maps directly onto the
compute-scaling plan (`swarm` scale work, issue #27):

- **Physical core count** bounds the parallel-seed speed-up (the seed ensemble is
  embarrassingly parallel; SMT/hyperthreads add only a little on this compute-bound
  float work).
- **SIMD width** (AVX2 vs AVX-512) sets how much `numpy` / `numba @njit`
  vectorization buys on the distance-and-gate hot loop.
- **GPU + CUDA availability** decides whether the deferred GPU path is even on the
  table for a given machine.

## Determinism note (read this first)

The models are pure, seeded, deterministic folds (CLAUDE.md section 7). Results are
**bit-identical across every machine in this list**, regardless of core count, SIMD
width, or OS. Hardware changes wall-clock time only, never the numbers. So nothing in
this file is a source for any figure in the repo; it exists to reason about run time
and to plan the compute roadmap, not to explain a result.

## Assertion mode (issue #48)

The fold modules carry `if __debug__:` invariant checks at each `step` call site
(reliability, multi-probe, closure-sim, swarm). By default, `python` runs with
`__debug__ == True`, so assertions are live in tests and in interactive use.

- **Ensemble runs** (Sobol sweeps, 200k-star swarm ensembles, anything measuring wall
  clock) should invoke Python with `-O`: it strips both the `if __debug__:` prologue
  and every `assert` statement, restoring bit-identical results at zero overhead.
  The swarm ensemble scripts (`swarm/experiments/*.py`) print a one-line stderr
  warning if they are run without `-O`, so the discipline surfaces even when
  someone bypasses `make sweep` (which already passes `-O`). See
  `swarm/experiments/_run.py`.
- **Everything else** runs with assertions on. Losing a bug because it violated an
  invariant we forgot to check in release is a §2 failure mode; keep the guard on
  unless the specific run needs the speed.

`python -O` does not change any number the fold produces - the invariants are
observational, never load-bearing. It only changes how expensive it is to notice a
bug at runtime.

## Optional Rust toolchain (issue #33, swarm only)

The swarm module ships an optional pyo3 Rust drop-in for its nearest-unsettled
k-d tree query (`swarm/rust/`), gated behind the `[project.optional-dependencies]
rust` extra. Building it needs a stable Rust toolchain (`cargo`, `rustc`) plus
`maturin`; the extra pulls maturin, and any recent `rustup default stable`
provides Cargo. To build and install the extension into `swarm`'s venv:

```sh
cd swarm
uv sync --extra dev --extra rust
uv run --extra rust maturin develop --release --manifest-path rust/Cargo.toml
```

Determinism note (repeats §7): the crate's `[profile.release]` disables LTO,
pins `codegen-units = 1`, and never enables `fastmath`. `f64::sqrt` delegates
to the hardware SQRTSD/FSQRT (correctly-rounded IEEE 754 on every modern
platform), so Rust and Python produce bit-identical outputs. Verified end-to-end
by `swarm/tests/test_kdtree_backends.py` (A/B/C oracle: Rust, numba, and pure
Python return the same star for the same query) plus every committed drift-guard
fixture (`tests/test_measure_results.py`) run through each backend.

Optional at runtime. A checkout without Cargo, without `maturin`, or without
building the extension still runs and passes the whole test suite; `swarm/sim.py`
falls back to numba (`swarm.kd_njit`) or pure Python. Override via
`SWARM_NO_RUST=1` / `SWARM_NO_NJIT=1`.

## Machines

### k02 - primary laptop (active)

Day-to-day development and moderate ensembles. This is the reference machine the
compute-scaling estimates in issue #27 are written against.

| Field | Value |
|---|---|
| Role | Primary dev laptop; parallel-seed ensembles |
| CPU | AMD Ryzen AI 7 PRO 350 (Zen 5), 8 cores / 16 threads, boost 5.09 GHz |
| SIMD | Native AVX-512 (F, DQ, BW, VL, IFMA, VBMI, VBMI2, VNNI, BF16, VPOPCNTDQ, ...), plus AVX2, FMA, VAES, GFNI |
| Cache | L2 8 MiB (8x1 MiB), L3 16 MiB |
| RAM | 27 GiB |
| GPU | AMD Radeon 860M integrated (RDNA 3.5). No NVIDIA, no CUDA. |
| Storage | 954 GB NVMe SSD (SK Hynix) |
| OS | Ubuntu 24.04.4 LTS, kernel 6.17.0-1023-oem |
| Recorded | 2026-07-11, from `lscpu` / `free` / `lspci` (see "Adding a machine") |

**Compute role.** Parallel seeds give roughly 8x (8 physical cores; the 16 threads add
about 1.1-1.3x on top). Native Zen 5 AVX-512 puts `numba` / `numpy` vectorization of the
hot loop at the top of its range, essentially for free. GPU work is not applicable here
(no CUDA). With the cell-list spatial index of issue #27 plus these two, the source
model's 200,000-star scale is reachable on this laptop alone; RAM and disk are never the
constraint for this workload (the fold's footprint is a few MB even at 200k, per worker).

### <desktop> - home desktop with GPU (planned)

The machine that could revisit the deferred GPU path (issue #27). Fill in when added;
the GPU fields are the ones that matter for that decision.

| Field | Value |
|---|---|
| Role | TODO (heavier local runs; possible GPU work) |
| CPU | TODO (model, physical cores / threads, boost) |
| SIMD | TODO (AVX2 / AVX-512?) |
| RAM | TODO |
| GPU | TODO (**model, VRAM, CUDA version** - decisive for the GPU path) |
| Storage | TODO |
| OS | TODO |
| Recorded | TODO |

### <aws-ensemble> - cloud burst (planned, only if needed)

A spot-instance fleet or batch service for large ensembles at scale. Deferred in issue
#27; the seed ensemble is map-only (zero cross-run communication), so this is a linear,
predictable spend when it is worth it. Fill in with instance type, vCPU count, and
per-run cost when provisioned.

## Adding a machine

Capture a new machine's specs with the commands below (the ones used for `k02`), then
add a section following the templates above. Always note the date and that the values
are self-reported by these tools on that date.

```sh
# CPU: model, core/thread count, clocks
lscpu | grep -iE 'model name|^cpu\(s\)|thread|core|max mhz'
# SIMD feature flags (AVX-512 subset matters for numpy/numba)
lscpu | grep -oiE 'avx512[a-z0-9]*|avx2|avx|fma' | sort -u | tr '\n' ' '; echo
# Memory
free -h
# GPU + CUDA (nvidia-smi prints nothing / errors when there is no NVIDIA GPU)
lspci | grep -iE 'vga|3d|display'
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>/dev/null || echo 'no NVIDIA/CUDA'
# Storage (ROTA=0 is SSD, 1 is spinning) and free space
lsblk -d -o NAME,SIZE,ROTA,MODEL; df -h /
# Identity
. /etc/os-release; echo "$PRETTY_NAME"; uname -r; hostname
```
