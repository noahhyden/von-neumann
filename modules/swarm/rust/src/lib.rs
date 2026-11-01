//! swarm_rust - Rust drop-in for the swarm hot paths.
//!
//! Issue #33 Phase 1 shipped the k-d tree nearest-unsettled QUERY
//! (`nearest_unsettled`, mirror of `swarm/src/swarm/kd_njit.py`). Tier 2 of the
//! 200k event-loop speedup adds `run_fill`, which owns the WHOLE event loop for
//! the supported config (`policy="powered"`, `coordination in {instant,
//! lightspeed}`, `stepping="event"`) - the config the 200k scale sweeps use.
//! Galaxy generation and the k-d tree build stay in Python (the seeded RNG is
//! not ported); Rust receives the pre-built SoA field + tree and returns raw
//! aggregates, from which `swarm.sim` builds an identical `SwarmResult`.
//!
//! Determinism (matches `sim.py` / `kd_njit.py`, and gated by the oracle in
//! `tests/test_rust_fill_loop.py`):
//!   - Every arithmetic op is written in the same left-to-right order as the
//!     Python reference; both sides are IEEE 754 f64.
//!   - No `fastmath`; `f64::sqrt` is the correctly-rounded hardware sqrt.
//!   - The ONE transcendental in the reference (`density**(-1/3)` for the mean
//!     NN distance) is precomputed in Python and passed as `inv_d_nn`, so the
//!     loop has no `powf` whose libm rounding could drift.
//!   - Periodic minimum-image wrap uses `round_ties_even` to match Python's
//!     banker's-rounding `round()`.
//!   - Event order is reproduced with a min-heap keyed `(arrive_year, pid)` plus
//!     the same `(arrive_year, id)` batch re-sort the Python `_resolve_batch`
//!     does, so heap internals are not load-bearing (see the audit in the branch
//!     history). For powered/instant+lightspeed no heap entry is ever stale
//!     (each pid has at most one live entry), so no lazy-validation is needed.

use numpy::{IntoPyArray, PyReadonlyArray1, PyReadwriteArray1};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::cmp::Reverse;
use std::collections::{BinaryHeap, HashSet};

/// Speed of light in parsecs per Julian year (from `swarm/models.py`). Same
/// left-to-right expression so the Rust `const` matches Python's runtime f64.
const C_PC_PER_YEAR: f64 = 299792.458_f64 * 3.15576e7_f64 / 3.0856775814913673e13_f64;

// The pure-Python fold computes inter-star and mid-flight distances with `** 0.5`, which CPython
// evaluates as libm `pow(x, 0.5)`. On this platform glibc `pow(x, 0.5)` is NOT bit-identical to
// hardware `sqrt(x)` - it is 1 ULP off for some arguments (a real glibc pow imperfection). The
// QUERY kernel uses `sqrt` (matching numba `nearest_unsettled_njit` and the committed query
// backend), but the fold's HOP distances use `pow`, so a bit-identical fill must reproduce glibc
// `pow` for hops. `black_box` on the exponent stops LLVM's SimplifyLibCalls from folding
// `pow(x, 0.5)` back into `sqrt` (which would silently reintroduce the 1-ULP divergence).
extern "C" {
    fn pow(base: f64, exp: f64) -> f64;
}
#[inline]
fn ref_root(s: f64) -> f64 {
    unsafe { pow(s, std::hint::black_box(0.5)) }
}

/// Nearest believed-unsettled star to `(px, py, pz)` at `year`, or -1 if none.
///
/// Bit-identical mirror of `swarm._nearest_unsettled_at_python`. Written as a
/// plain function over slices so both the `#[pyfunction]` wrapper and the
/// in-process `run_fill` loop call the exact same traversal.
#[allow(clippy::too_many_arguments)]
fn nn_impl(
    px: f64,
    py: f64,
    pz: f64,
    year: f64,
    is_instant: bool,
    xs: &[f64],
    ys: &[f64],
    zs: &[f64],
    sy: &[f64],
    kd_root: i32,
    axis: &[i8],
    split: &[f64],
    lo: &[i32],
    hi: &[i32],
    bxmin: &[f64],
    bxmax: &[f64],
    bymin: &[f64],
    bymax: &[f64],
    bzmin: &[f64],
    bzmax: &[f64],
    nuns: &[i32],
    tsmax: &[f64],
    bucket_flat: &[i32],
    bucket_offsets: &[i32],
    excl: &[i32],
    n_ex: usize,
) -> i64 {
    if kd_root < 0 {
        return -1;
    }
    let c = C_PC_PER_YEAR;
    let mut best: i64 = -1;
    let mut best_d2 = f64::INFINITY;

    let mut stack: [i32; 128] = [0; 128];
    stack[0] = kd_root;
    let mut sp: usize = 1;

    while sp > 0 {
        sp -= 1;
        let node = stack[sp] as usize;

        let mut dlo2: f64 = 0.0;
        let mut t = bxmin[node] - px;
        if t > 0.0 {
            dlo2 = t * t;
        } else {
            t = px - bxmax[node];
            if t > 0.0 {
                dlo2 = t * t;
            }
        }
        t = bymin[node] - py;
        if t > 0.0 {
            dlo2 += t * t;
        } else {
            t = py - bymax[node];
            if t > 0.0 {
                dlo2 += t * t;
            }
        }
        t = bzmin[node] - pz;
        if t > 0.0 {
            dlo2 += t * t;
        } else {
            t = pz - bzmax[node];
            if t > 0.0 {
                dlo2 += t * t;
            }
        }
        if dlo2 > best_d2 {
            continue;
        }
        if nuns[node] == 0 {
            if is_instant {
                continue;
            }
            let mut a = px - bxmin[node];
            let mut b = px - bxmax[node];
            let mut a2 = a * a;
            let mut b2 = b * b;
            let mut dhi2 = if a2 > b2 { a2 } else { b2 };
            a = py - bymin[node];
            b = py - bymax[node];
            a2 = a * a;
            b2 = b * b;
            dhi2 += if a2 > b2 { a2 } else { b2 };
            a = pz - bzmin[node];
            b = pz - bzmax[node];
            a2 = a * a;
            b2 = b * b;
            dhi2 += if a2 > b2 { a2 } else { b2 };
            if tsmax[node] + dhi2.sqrt() / c <= year {
                continue;
            }
        }
        let ax = axis[node];
        if ax == -1 {
            let start = bucket_offsets[node] as usize;
            let end = bucket_offsets[node + 1] as usize;
            for k in start..end {
                let i = bucket_flat[k] as usize;
                let mut skipped = false;
                for j in 0..n_ex {
                    if excl[j] as usize == i {
                        skipped = true;
                        break;
                    }
                }
                if skipped {
                    continue;
                }
                let sy_i = sy[i];
                if sy_i >= 0.0 {
                    if is_instant {
                        continue;
                    }
                    let dx = xs[i] - px;
                    let dy = ys[i] - py;
                    let dz = zs[i] - pz;
                    // The QUERY (kernel) uses sqrt - matches numba `nearest_unsettled_njit` and the
                    // committed query backend. (Hops are a separate story; see `dist` / `ref_root`.)
                    let d = (dx * dx + dy * dy + dz * dz).sqrt();
                    if sy_i + d / c <= year {
                        continue;
                    }
                }
                let dx = xs[i] - px;
                let dy = ys[i] - py;
                let dz = zs[i] - pz;
                let d2 = dx * dx + dy * dy + dz * dz;
                let i_i64 = i as i64;
                if d2 < best_d2 || (d2 == best_d2 && best >= 0 && i_i64 < best) {
                    best_d2 = d2;
                    best = i_i64;
                }
            }
        } else {
            let p_ax = if ax == 0 {
                px
            } else if ax == 1 {
                py
            } else {
                pz
            };
            if p_ax < split[node] {
                stack[sp] = hi[node];
                sp += 1;
                stack[sp] = lo[node];
                sp += 1;
            } else {
                stack[sp] = lo[node];
                sp += 1;
                stack[sp] = hi[node];
                sp += 1;
            }
        }
    }
    best
}

/// Fold star `star`'s settlement into the subtree aggregates leaf->root.
/// Mirror of `sim._kd_mark_settled`.
fn mark_settled(
    star: usize,
    y: f64,
    nuns: &mut [i32],
    tsmax: &mut [f64],
    parent: &[i32],
    star_leaf: &[i32],
) {
    let mut node = star_leaf[star];
    while node != -1 {
        let n = node as usize;
        nuns[n] -= 1;
        if y > tsmax[n] {
            tsmax[n] = y;
        }
        node = parent[n];
    }
}

/// Minimum-image separation between two points on a torus (or plain distance).
/// Mirror of `sim._dist`; `round_ties_even` matches Python's `round()`.
#[inline]
fn dist(
    xs: &[f64],
    ys: &[f64],
    zs: &[f64],
    a: usize,
    b: usize,
    periodic: bool,
    box_side: f64,
) -> f64 {
    let mut dx = xs[a] - xs[b];
    let mut dy = ys[a] - ys[b];
    let mut dz = zs[a] - zs[b];
    if periodic {
        let l = box_side;
        dx -= l * (dx / l).round_ties_even();
        dy -= l * (dy / l).round_ties_even();
        dz -= l * (dz / l).round_ties_even();
    }
    // Python `_dist` uses `** 0.5` (glibc `pow`), NOT hardware sqrt (see `ref_root`). Matching it
    // exactly matters: a 1-ULP hop cascades (hop -> arrive -> a star's settled_year -> every
    // downstream learn_year -> which target a mid-flight learner re-selects).
    ref_root(dx * dx + dy * dy + dz * dz)
}

/// hop-length bin: count of leading edges `<= d` (mirror of `sim._hop_bin` /
/// the inlined loop in `_process_arrivals`).
#[inline]
fn bin_ge(edges: &[f64], v: f64) -> usize {
    let mut k = 0usize;
    for &e in edges {
        if v >= e {
            k += 1;
        } else {
            break;
        }
    }
    k
}

// State-of-arrays probe pool for the powered/event fast path. Speed is constant
// (= probe cruise) under the powered policy, so it is not stored per probe. The
// `from_*` launch position is read only by inflight mid-flight interpolation
// (unset/zero and unread under instant/lightspeed, matching the Python defaults).
struct Pool {
    target: Vec<i64>,
    arrive: Vec<f64>,
    hop: Vec<f64>,
    retargets: Vec<i64>,
    launch: Vec<f64>,
    from_x: Vec<f64>,
    from_y: Vec<f64>,
    from_z: Vec<f64>,
    live: Vec<bool>,
}

impl Pool {
    fn new() -> Self {
        Pool {
            target: Vec::new(),
            arrive: Vec::new(),
            hop: Vec::new(),
            retargets: Vec::new(),
            launch: Vec::new(),
            from_x: Vec::new(),
            from_y: Vec::new(),
            from_z: Vec::new(),
            live: Vec::new(),
        }
    }
    #[allow(clippy::too_many_arguments)]
    fn push(
        &mut self,
        target: i64,
        arrive: f64,
        hop: f64,
        retargets: i64,
        launch: f64,
        from_x: f64,
        from_y: f64,
        from_z: f64,
    ) -> i64 {
        let pid = self.target.len() as i64;
        self.target.push(target);
        self.arrive.push(arrive);
        self.hop.push(hop);
        self.retargets.push(retargets);
        self.launch.push(launch);
        self.from_x.push(from_x);
        self.from_y.push(from_y);
        self.from_z.push(from_z);
        self.live.push(true);
        pid
    }
}

/// Mirror of `sim._learn_year`: year the beacon overtakes probe `pid` in flight.
#[inline]
fn learn_year_of(pid: usize, target: &[i64], arrive: &[f64], sy: &[f64], v_over_c: f64) -> f64 {
    let t = target[pid] as usize;
    (sy[t] + v_over_c * arrive[pid]) / (1.0 + v_over_c)
}

/// Mirror of `sim._actionable_year`: mid-flight learn time if doomed under inflight, else arrival.
#[inline]
fn actionable_of(
    pid: usize,
    target: &[i64],
    arrive: &[f64],
    sy: &[f64],
    is_inflight: bool,
    v_over_c: f64,
) -> f64 {
    if is_inflight {
        let t = target[pid] as usize;
        if sy[t] >= 0.0 {
            let tl = learn_year_of(pid, target, arrive, sy, v_over_c);
            if tl < arrive[pid] {
                return tl;
            }
        }
    }
    arrive[pid]
}

// Min-heap entry keyed by (arrive_year, pid).
#[derive(Clone, Copy)]
struct Ev {
    key: f64,
    pid: i64,
}
impl PartialEq for Ev {
    fn eq(&self, o: &Self) -> bool {
        self.key == o.key && self.pid == o.pid
    }
}
impl Eq for Ev {}
impl PartialOrd for Ev {
    fn partial_cmp(&self, o: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(o))
    }
}
impl Ord for Ev {
    fn cmp(&self, o: &Self) -> std::cmp::Ordering {
        // Total order on finite positive years; ties broken by pid. Wrapped in
        // Reverse at the heap so the smallest (arrive_year, pid) pops first.
        self.key.total_cmp(&o.key).then(self.pid.cmp(&o.pid))
    }
}

/// Run the whole powered/event fill loop and return raw aggregates as a dict.
///
/// Bit-identical to `swarm.sim.simulate_swarm` for `policy="powered"`,
/// `coordination in {instant, lightspeed, inflight}`, `stepping="event"`,
/// `record_steps=False`. Under `inflight` (`is_inflight=true`) the loop also runs
/// mid-flight relay: a probe whose target is claimed learns at `_learn_year` and
/// redirects from its interpolated position; `by_target` + lazy heap validation
/// reproduce the decrease-key. The caller (`swarm.sim._simulate_swarm_rust`) builds
/// `SwarmResult` from the returned dict exactly as the Python loop's tail does.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn run_fill(
    py: Python<'_>,
    xs: PyReadonlyArray1<f64>,
    ys: PyReadonlyArray1<f64>,
    zs: PyReadonlyArray1<f64>,
    origin: i64,
    kd_root: i32,
    kd_axis: PyReadonlyArray1<i8>,
    kd_split: PyReadonlyArray1<f64>,
    kd_lo: PyReadonlyArray1<i32>,
    kd_hi: PyReadonlyArray1<i32>,
    kd_parent: PyReadonlyArray1<i32>,
    kd_bxmin: PyReadonlyArray1<f64>,
    kd_bxmax: PyReadonlyArray1<f64>,
    kd_bymin: PyReadonlyArray1<f64>,
    kd_bymax: PyReadonlyArray1<f64>,
    kd_bzmin: PyReadonlyArray1<f64>,
    kd_bzmax: PyReadonlyArray1<f64>,
    kd_nuns: PyReadonlyArray1<i32>,
    kd_tsmax: PyReadonlyArray1<f64>,
    star_leaf: PyReadonlyArray1<i32>,
    kd_bucket_flat: PyReadonlyArray1<i32>,
    kd_bucket_offsets: PyReadonlyArray1<i32>,
    is_instant: bool,
    is_inflight: bool,
    box_side: f64,
    periodic: bool,
    probe_speed: f64,
    offspring: i64,
    settle_time: f64,
    max_years: f64,
    max_retargets: i64,
    inv_d_nn: f64,
    hop_edges: PyReadonlyArray1<f64>,
    wall_edges: PyReadonlyArray1<f64>,
) -> PyResult<Py<PyDict>> {
    let xs = xs.as_slice()?;
    let ys = ys.as_slice()?;
    let zs = zs.as_slice()?;
    let axis = kd_axis.as_slice()?;
    let split = kd_split.as_slice()?;
    let lo = kd_lo.as_slice()?;
    let hi = kd_hi.as_slice()?;
    let parent = kd_parent.as_slice()?;
    let bxmin = kd_bxmin.as_slice()?;
    let bxmax = kd_bxmax.as_slice()?;
    let bymin = kd_bymin.as_slice()?;
    let bymax = kd_bymax.as_slice()?;
    let bzmin = kd_bzmin.as_slice()?;
    let bzmax = kd_bzmax.as_slice()?;
    let star_leaf = star_leaf.as_slice()?;
    let bucket_flat = kd_bucket_flat.as_slice()?;
    let bucket_offsets = kd_bucket_offsets.as_slice()?;
    let hop_edges = hop_edges.as_slice()?;
    let wall_edges = wall_edges.as_slice()?;

    let n = xs.len();
    // Mutable copies of the unsettled-set aggregates (Python mutates its own copies).
    let mut sy: Vec<f64> = vec![-1.0; n];
    let mut nuns: Vec<i32> = kd_nuns.as_slice()?.to_vec();
    let mut tsmax: Vec<f64> = kd_tsmax.as_slice()?.to_vec();

    let n_hop = hop_edges.len() + 1;
    let n_wall = wall_edges.len() + 1;

    // Aggregate accumulators (mirror the SwarmState counters).
    let mut settled_count: i64 = 1;
    let mut total_launched: i64 = 0;
    let mut total_arrivals: i64 = 0;
    let mut wasted_arrivals: i64 = 0;
    let mut retarget_count: i64 = 0;
    let mut wasted_travel_pc: f64 = 0.0;
    let mut front_radius: f64 = 0.0;
    let mut settle_hop_sum: f64 = 0.0;
    let mut settle_hop_count: i64 = 0;
    let mut wasted_hop_sum: f64 = 0.0;
    let mut wasted_hop_count: i64 = 0;
    let mut settle_v_sum: f64 = 0.0;
    let mut settle_v2_sum: f64 = 0.0;
    let mut wasted_v_sum: f64 = 0.0;
    let mut wasted_v2_sum: f64 = 0.0;
    let mut midflight_aborts: i64 = 0;
    let mut launch_speed_sum: f64 = 0.0;
    let mut launch_count: i64 = 0;
    let mut settle_hop_hist: Vec<i64> = vec![0; n_hop];
    let mut wasted_hop_hist: Vec<i64> = vec![0; n_hop];
    let mut settle_wall_hist: Vec<i64> = vec![0; n_wall];
    let mut wasted_wall_hist: Vec<i64> = vec![0; n_wall];
    let mut wasted_s_hist: Vec<i64> = vec![0; 32];

    // Thresholds (25,50,75,90,99,100)% coverage -> first year reached (-1 = never).
    let pcts: [f64; 6] = [25.0, 50.0, 75.0, 90.0, 99.0, 100.0];
    let mut thr: [f64; 6] = [-1.0; 6];
    let n_f = n as f64;
    let record_thresholds = |settled_count: i64, year: f64, thr: &mut [f64; 6]| {
        let frac = settled_count as f64 / n_f * 100.0;
        for k in 0..6 {
            if thr[k] < 0.0 && frac >= pcts[k] {
                thr[k] = year;
            }
        }
    };

    let mut pool = Pool::new();
    let mut heap: BinaryHeap<Reverse<Ev>> = BinaryHeap::new();
    // inflight decrease-key index: for each star, the probe ids that have targeted it (with
    // stale entries; `_on_settled` filters by live + still-targeting). Empty/unused otherwise.
    let mut by_target: Vec<Vec<i64>> = if is_inflight {
        (0..n).map(|_| Vec::new()).collect()
    } else {
        Vec::new()
    };
    let v_over_c = probe_speed / C_PC_PER_YEAR; // powered: constant per-probe speed

    // Helper closure would borrow too much; inline the query call each time.
    macro_rules! nn {
        ($px:expr, $py:expr, $pz:expr, $year:expr, $excl:expr, $n_ex:expr) => {
            nn_impl(
                $px, $py, $pz, $year, is_instant, xs, ys, zs, &sy, kd_root, axis, split, lo, hi,
                bxmin, bxmax, bymin, bymax, bzmin, bzmax, &nuns, &tsmax, bucket_flat,
                bucket_offsets, $excl, $n_ex,
            )
        };
    }
    // Current actionable time of probe `pu` (mirror of _actionable_year).
    macro_rules! actionable {
        ($pu:expr) => {
            actionable_of($pu, &pool.target, &pool.arrive, &sy, is_inflight, v_over_c)
        };
    }
    // Register a probe: mark live, push its heap entry keyed at the actionable time, and (inflight)
    // index it under its target for the decrease-key. Mirror of _add_probe.
    macro_rules! add_probe {
        ($pid:expr) => {{
            let _pid: i64 = $pid;
            let _pu = _pid as usize;
            pool.live[_pu] = true;
            let _k = actionable!(_pu);
            heap.push(Reverse(Ev { key: _k, pid: _pid }));
            if is_inflight {
                by_target[pool.target[_pu] as usize].push(_pid);
            }
        }};
    }

    // --- origin settle + seed launch (mirror initial_state) ---
    let origin_u = origin as usize;
    sy[origin_u] = 0.0;
    mark_settled(origin_u, 0.0, &mut nuns, &mut tsmax, parent, star_leaf);
    // Launch offspring from origin at year 0 (powered: departing speed = probe_speed).
    {
        let ox = xs[origin_u];
        let oy = ys[origin_u];
        let oz = zs[origin_u];
        let mut chosen: Vec<i32> = Vec::new();
        let departing = probe_speed;
        for _ in 0..offspring {
            let target = nn!(ox, oy, oz, 0.0, &chosen, chosen.len());
            if target < 0 {
                break;
            }
            chosen.push(target as i32);
            let hop = dist(xs, ys, zs, origin_u, target as usize, periodic, box_side);
            let travel = hop / departing;
            let pid = pool.push(target, 0.0 + settle_time + travel, hop, 0, 0.0 + settle_time, ox, oy, oz);
            add_probe!(pid);
            total_launched += 1;
            launch_speed_sum += departing;
            launch_count += 1;
        }
    }
    // Seed probes in flight right after initial_state (for the single record_steps=False snapshot).
    let initial_in_flight = launch_count;
    record_thresholds(settled_count, 0.0, &mut thr);

    // --- event loop (mirror simulate_swarm's event branch + _resolve_batch) ---
    let mut batch: Vec<i64> = Vec::new();
    let mut arrivals: Vec<i64> = Vec::new();
    let mut learns: Vec<i64> = Vec::new();
    let mut seen: HashSet<i64> = HashSet::new();
    loop {
        // _next_valid_event: discard stale heap tops (probe dead, or key superseded by an
        // inflight decrease-key), return the earliest valid actionable time; NaN = none left.
        let ne = loop {
            match heap.peek() {
                None => break f64::NAN,
                Some(&Reverse(top)) => {
                    let pu = top.pid as usize;
                    if !pool.live[pu] || actionable!(pu) != top.key {
                        heap.pop();
                        continue;
                    }
                    break top.key;
                }
            }
        };
        if ne.is_nan() || ne > max_years {
            break;
        }
        let year = ne;
        // _pop_due(ne): pop entries with key <= ne (== the min), filtering stale + duplicate pids.
        batch.clear();
        seen.clear();
        while let Some(&Reverse(e)) = heap.peek() {
            if e.key > ne {
                break;
            }
            heap.pop();
            let pu = e.pid as usize;
            if !pool.live[pu] || seen.contains(&e.pid) || actionable!(pu) != e.key {
                continue;
            }
            seen.insert(e.pid);
            batch.push(e.pid);
        }
        // _resolve_batch: classify against the state BEFORE processing, sort each, arrivals first.
        arrivals.clear();
        learns.clear();
        for &pid in &batch {
            let pu = pid as usize;
            let tu = pool.target[pu] as usize;
            let is_learn = is_inflight
                && sy[tu] >= 0.0
                && learn_year_of(pu, &pool.target, &pool.arrive, &sy, v_over_c) < pool.arrive[pu];
            if is_learn {
                learns.push(pid);
            } else {
                arrivals.push(pid);
            }
        }
        arrivals.sort_by(|&a, &b| {
            pool.arrive[a as usize].total_cmp(&pool.arrive[b as usize]).then(a.cmp(&b))
        });
        learns.sort_by(|&a, &b| {
            pool.arrive[a as usize].total_cmp(&pool.arrive[b as usize]).then(a.cmp(&b))
        });

        // --- _process_arrivals: remove arrivals from the live set up front, then settle-or-waste.
        for &pid in &arrivals {
            pool.live[pid as usize] = false;
        }
        total_arrivals += arrivals.len() as i64;
        for &pid in &arrivals {
            let pu = pid as usize;
            let target = pool.target[pu];
            let tu = target as usize;
            let hop_len = pool.hop[pu];
            let v = probe_speed;

            let hb = bin_ge(hop_edges, hop_len);
            let x = xs[tu];
            let y = ys[tu];
            let z = zs[tu];
            let mut wall = if x < box_side - x { x } else { box_side - x };
            let yy = if y < box_side - y { y } else { box_side - y };
            if yy < wall {
                wall = yy;
            }
            let zz = if z < box_side - z { z } else { box_side - z };
            if zz < wall {
                wall = zz;
            }
            let r = wall * inv_d_nn;
            let wb = bin_ge(wall_edges, r);

            if sy[tu] < 0.0 {
                // First to arrive: settle and spread.
                sy[tu] = year;
                mark_settled(tu, year, &mut nuns, &mut tsmax, parent, star_leaf);
                settled_count += 1;
                let d_origin = dist(xs, ys, zs, tu, origin_u, periodic, box_side);
                if d_origin > front_radius {
                    front_radius = d_origin;
                }
                // _on_settled(target): inflight decrease-key for probes still heading here.
                if is_inflight {
                    let m = by_target[tu].len();
                    for k in 0..m {
                        let qpid = by_target[tu][k];
                        let qu = qpid as usize;
                        if pool.live[qu] && pool.target[qu] == target {
                            let kk = actionable!(qu);
                            heap.push(Reverse(Ev { key: kk, pid: qpid }));
                        }
                    }
                    by_target[tu].clear();
                }
                settle_hop_sum += hop_len;
                settle_hop_count += 1;
                settle_hop_hist[hb] += 1;
                settle_wall_hist[wb] += 1;
                settle_v_sum += v;
                settle_v2_sum += v * v;
                let departing = probe_speed;
                let mut chosen: Vec<i32> = Vec::new();
                for _ in 0..offspring {
                    let nt = nn!(x, y, z, year, &chosen, chosen.len());
                    if nt < 0 {
                        break;
                    }
                    chosen.push(nt as i32);
                    let hop = dist(xs, ys, zs, tu, nt as usize, periodic, box_side);
                    let travel = hop / departing;
                    let npid =
                        pool.push(nt, year + settle_time + travel, hop, 0, year + settle_time, x, y, z);
                    add_probe!(npid);
                    total_launched += 1;
                    launch_speed_sum += departing;
                    launch_count += 1;
                }
            } else {
                // Raced and lost: a wasted trip; re-target from here.
                wasted_arrivals += 1;
                wasted_hop_sum += hop_len;
                wasted_hop_count += 1;
                wasted_hop_hist[hb] += 1;
                wasted_wall_hist[wb] += 1;
                wasted_travel_pc += hop_len;
                wasted_v_sum += v;
                wasted_v2_sum += v * v;
                let span = pool.arrive[pu] - pool.launch[pu];
                if span > 0.0 {
                    let s = (sy[tu] - pool.launch[pu]) / span;
                    let sb: usize = if s < 0.0 {
                        0
                    } else if s >= 1.0 {
                        31
                    } else {
                        (s * 32.0) as usize
                    };
                    wasted_s_hist[sb] += 1;
                }
                if pool.retargets[pu] >= max_retargets {
                    continue;
                }
                let empty: [i32; 0] = [];
                let nt = nn!(x, y, z, year, &empty, 0);
                if nt >= 0 {
                    retarget_count += 1;
                    let hop = dist(xs, ys, zs, tu, nt as usize, periodic, box_side);
                    let travel = hop / v;
                    pool.target[pu] = nt;
                    pool.arrive[pu] = year + travel;
                    pool.retargets[pu] += 1;
                    pool.hop[pu] = hop;
                    pool.launch[pu] = year;
                    pool.from_x[pu] = x;
                    pool.from_y[pu] = y;
                    pool.from_z[pu] = z;
                    add_probe!(pid);
                }
            }
        }

        // --- _process_learns (inflight): abort the doomed hop mid-flight and redirect.
        for &pid in &learns {
            pool.live[pid as usize] = false;
        }
        for &pid in &learns {
            let pu = pid as usize;
            let tu = pool.target[pu] as usize;
            let span = pool.arrive[pu] - pool.launch[pu];
            let mut frac = if span > 0.0 { (year - pool.launch[pu]) / span } else { 1.0 };
            frac = if frac < 0.0 {
                0.0
            } else if frac > 1.0 {
                1.0
            } else {
                frac
            };
            let px = pool.from_x[pu] + (xs[tu] - pool.from_x[pu]) * frac;
            let py = pool.from_y[pu] + (ys[tu] - pool.from_y[pu]) * frac;
            let pz = pool.from_z[pu] + (zs[tu] - pool.from_z[pu]) * frac;
            wasted_travel_pc += pool.hop[pu] * frac;
            midflight_aborts += 1;
            if pool.retargets[pu] >= max_retargets {
                continue;
            }
            let empty: [i32; 0] = [];
            let nt = nn!(px, py, pz, year, &empty, 0);
            if nt < 0 {
                continue;
            }
            retarget_count += 1;
            let dx = xs[nt as usize] - px;
            let dy = ys[nt as usize] - py;
            let dz = zs[nt as usize] - pz;
            let hop = ref_root(dx * dx + dy * dy + dz * dz); // `** 0.5` (glibc pow), match Python
            let travel = hop / probe_speed;
            pool.target[pu] = nt;
            pool.arrive[pu] = year + travel;
            pool.retargets[pu] += 1;
            pool.hop[pu] = hop;
            pool.from_x[pu] = px;
            pool.from_y[pu] = py;
            pool.from_z[pu] = pz;
            pool.launch[pu] = year;
            add_probe!(pid);
        }

        record_thresholds(settled_count, year, &mut thr);
    }

    // final front radius: the Python `_front_radius` rescan equals the incrementally
    // maintained maximum (both are max over settled stars of dist-to-origin), so we
    // return the incremental value; sim._simulate_swarm_rust uses it directly.
    let d = PyDict::new_bound(py);
    d.set_item("final_settled", settled_count)?;
    d.set_item("total_launched", total_launched)?;
    d.set_item("total_arrivals", total_arrivals)?;
    d.set_item("wasted_arrivals", wasted_arrivals)?;
    d.set_item("retarget_count", retarget_count)?;
    d.set_item("wasted_travel_pc", wasted_travel_pc)?;
    d.set_item("midflight_aborts", midflight_aborts)?;
    d.set_item("front_radius_pc", front_radius)?;
    d.set_item("max_speed_pc_yr", probe_speed)?;
    d.set_item("settle_hop_sum_pc", settle_hop_sum)?;
    d.set_item("settle_hop_count", settle_hop_count)?;
    d.set_item("wasted_hop_sum_pc", wasted_hop_sum)?;
    d.set_item("wasted_hop_count", wasted_hop_count)?;
    d.set_item("settle_v_sum_pc_yr", settle_v_sum)?;
    d.set_item("settle_v2_sum", settle_v2_sum)?;
    d.set_item("wasted_v_sum_pc_yr", wasted_v_sum)?;
    d.set_item("wasted_v2_sum", wasted_v2_sum)?;
    d.set_item("launch_speed_sum_pc_yr", launch_speed_sum)?;
    d.set_item("launch_count", launch_count)?;
    d.set_item("t25", if thr[0] < 0.0 { py.None() } else { thr[0].into_py(py) })?;
    d.set_item("t50", if thr[1] < 0.0 { py.None() } else { thr[1].into_py(py) })?;
    d.set_item("t75", if thr[2] < 0.0 { py.None() } else { thr[2].into_py(py) })?;
    d.set_item("t90", if thr[3] < 0.0 { py.None() } else { thr[3].into_py(py) })?;
    d.set_item("t99", if thr[4] < 0.0 { py.None() } else { thr[4].into_py(py) })?;
    d.set_item("t100", if thr[5] < 0.0 { py.None() } else { thr[5].into_py(py) })?;
    d.set_item("settle_hop_hist", settle_hop_hist)?;
    d.set_item("wasted_hop_hist", wasted_hop_hist)?;
    d.set_item("settle_wall_hist", settle_wall_hist)?;
    d.set_item("wasted_wall_hist", wasted_wall_hist)?;
    d.set_item("wasted_s_hist", wasted_s_hist)?;
    d.set_item("initial_in_flight", initial_in_flight)?;
    Ok(d.into())
}

/// Nearest believed-unsettled star to `(px, py, pz)` at `year`, or -1 if none.
/// Bit-identical mirror of `swarm.kd_njit.nearest_unsettled_njit` (thin wrapper
/// around `nn_impl`; kept for the k-d tree backend + its oracle).
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn nearest_unsettled(
    px: f64,
    py: f64,
    pz: f64,
    year: f64,
    is_instant: bool,
    xs: PyReadonlyArray1<f64>,
    ys: PyReadonlyArray1<f64>,
    zs: PyReadonlyArray1<f64>,
    settled_year: PyReadonlyArray1<f64>,
    kd_root: i32,
    kd_axis: PyReadonlyArray1<i8>,
    kd_split: PyReadonlyArray1<f64>,
    kd_lo: PyReadonlyArray1<i32>,
    kd_hi: PyReadonlyArray1<i32>,
    kd_bxmin: PyReadonlyArray1<f64>,
    kd_bxmax: PyReadonlyArray1<f64>,
    kd_bymin: PyReadonlyArray1<f64>,
    kd_bymax: PyReadonlyArray1<f64>,
    kd_bzmin: PyReadonlyArray1<f64>,
    kd_bzmax: PyReadonlyArray1<f64>,
    kd_nuns: PyReadonlyArray1<i32>,
    kd_tsmax: PyReadonlyArray1<f64>,
    kd_bucket_flat: PyReadonlyArray1<i32>,
    kd_bucket_offsets: PyReadonlyArray1<i32>,
    exclude: PyReadonlyArray1<i32>,
    n_excludes: i64,
) -> PyResult<i64> {
    Ok(nn_impl(
        px,
        py,
        pz,
        year,
        is_instant,
        xs.as_slice()?,
        ys.as_slice()?,
        zs.as_slice()?,
        settled_year.as_slice()?,
        kd_root,
        kd_axis.as_slice()?,
        kd_split.as_slice()?,
        kd_lo.as_slice()?,
        kd_hi.as_slice()?,
        kd_bxmin.as_slice()?,
        kd_bxmax.as_slice()?,
        kd_bymin.as_slice()?,
        kd_bymax.as_slice()?,
        kd_bzmin.as_slice()?,
        kd_bzmax.as_slice()?,
        kd_nuns.as_slice()?,
        kd_tsmax.as_slice()?,
        kd_bucket_flat.as_slice()?,
        kd_bucket_offsets.as_slice()?,
        exclude.as_slice()?,
        n_excludes as usize,
    ))
}

/// Build-verification helper: Rust's left-to-right f64 for `C_PC_PER_YEAR`.
#[pyfunction]
fn c_pc_per_year() -> f64 {
    C_PC_PER_YEAR
}

// ============================================================================
// Flat p2 kd-tree (issue #38 P2 spec: swarm/rust/SPEC_FLAT_KDTREE.md).
//
// At `N = 2^k, k >= 3` and `_KD_LEAF = 8`, the pointer tree collapses to a
// perfect binary tree with `M = N/8` leaves. Heap indexing (`children = 2i+1,
// 2i+2; parent = (i-1) >> 1; leaf iff i >= M-1`) replaces the `lo`, `hi`,
// `parent` arrays entirely - the "bit-shift shenanigans" the p2 standardization
// buys. The build's median-split rule (widest axis, sort by `(coord, index)`,
// split at `mid = len/2`) is byte-for-byte identical to `sim._build_kdtree`,
// so the flat tree is a drop-in for the pointer tree at matching p2 N and
// returns star indices in the *original* space via `star_perm`.
// ============================================================================

const KD_LEAF: usize = 8;

/// Kd-tree leaf capacity (mirrors `sim._KD_LEAF` = 8). Exposed as a `const` so
/// the compiler can bake the value into the leaf indexing arithmetic.
#[inline]
fn is_power_of_two(n: usize) -> bool {
    n > 0 && (n & (n - 1)) == 0
}

/// Recursive median-split build (matches the pointer tree's recursion). Not a
/// closure: passes each buffer by `&mut` so the compiler can prove aliasing.
#[allow(clippy::too_many_arguments)]
fn flat_build(
    node: usize,
    start: usize,
    end: usize,
    xs: &[f64],
    ys: &[f64],
    zs: &[f64],
    star_perm: &mut [i32],
    axis: &mut [i8],
    split: &mut [f64],
    bxmin: &mut [f64],
    bxmax: &mut [f64],
    bymin: &mut [f64],
    bymax: &mut [f64],
    bzmin: &mut [f64],
    bzmax: &mut [f64],
    m_minus_one: usize,
) {
    // Bounding box over this node's stars (in permuted order).
    let i0 = star_perm[start] as usize;
    let mut xmn = xs[i0];
    let mut xmx = xmn;
    let mut ymn = ys[i0];
    let mut ymx = ymn;
    let mut zmn = zs[i0];
    let mut zmx = zmn;
    for &p in &star_perm[start + 1..end] {
        let pu = p as usize;
        let xi = xs[pu];
        if xi < xmn {
            xmn = xi;
        } else if xi > xmx {
            xmx = xi;
        }
        let yi = ys[pu];
        if yi < ymn {
            ymn = yi;
        } else if yi > ymx {
            ymx = yi;
        }
        let zi = zs[pu];
        if zi < zmn {
            zmn = zi;
        } else if zi > zmx {
            zmx = zi;
        }
    }
    bxmin[node] = xmn;
    bxmax[node] = xmx;
    bymin[node] = ymn;
    bymax[node] = ymx;
    bzmin[node] = zmn;
    bzmax[node] = zmx;

    if node >= m_minus_one {
        // Leaf: exactly 8 stars at start..end. Nothing to do beyond bbox+aggregates.
        axis[node] = -1;
        split[node] = 0.0;
        return;
    }

    // Widest axis (ties: x > y > z, matching the pointer tree).
    let ex = xmx - xmn;
    let ey = ymx - ymn;
    let ez = zmx - zmn;
    let ax: i8 = if ex >= ey && ex >= ez {
        0
    } else if ey >= ez {
        1
    } else {
        2
    };
    let coord: &[f64] = match ax {
        0 => xs,
        1 => ys,
        _ => zs,
    };
    // Sort star_perm[start..end] by (coord[perm], perm) - the pointer tree's exact tie-break.
    star_perm[start..end].sort_by(|&a, &b| {
        let ca = coord[a as usize];
        let cb = coord[b as usize];
        ca.total_cmp(&cb).then(a.cmp(&b))
    });
    let mid = start + (end - start) / 2;
    axis[node] = ax;
    split[node] = coord[star_perm[mid] as usize];
    flat_build(
        2 * node + 1,
        start,
        mid,
        xs,
        ys,
        zs,
        star_perm,
        axis,
        split,
        bxmin,
        bxmax,
        bymin,
        bymax,
        bzmin,
        bzmax,
        m_minus_one,
    );
    flat_build(
        2 * node + 2,
        mid,
        end,
        xs,
        ys,
        zs,
        star_perm,
        axis,
        split,
        bxmin,
        bxmax,
        bymin,
        bymax,
        bzmin,
        bzmax,
        m_minus_one,
    );
}

/// Build a perfect binary flat kd-tree over N stars, `N = 2^k, k >= 3`.
///
/// Returns a dict with the tree arrays (see `SPEC_FLAT_KDTREE.md`). Raises
/// `ValueError` for any N that is not a power of two >= 8 - the p2 discipline
/// is enforced at the build boundary so callers never silently get a broken
/// tree.
#[pyfunction]
fn build_flat_kdtree(
    py: Python<'_>,
    xs: PyReadonlyArray1<f64>,
    ys: PyReadonlyArray1<f64>,
    zs: PyReadonlyArray1<f64>,
) -> PyResult<Py<PyDict>> {
    let xs = xs.as_slice()?;
    let ys = ys.as_slice()?;
    let zs = zs.as_slice()?;
    let n = xs.len();
    if ys.len() != n || zs.len() != n {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "xs, ys, zs must have equal length",
        ));
    }
    if n < KD_LEAF || !is_power_of_two(n) {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "build_flat_kdtree requires n_stars to be a power of two >= {} (got {})",
            KD_LEAF, n
        )));
    }
    let m = n / KD_LEAF;
    if !is_power_of_two(m) {
        // Redundant given `n` is p2 and `KD_LEAF` is 8 (also p2), but a defense against a future
        // KD_LEAF bump breaking the invariant silently.
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "n_stars / KD_LEAF must also be a power of two (got m={})",
            m
        )));
    }
    let total = 2 * m - 1;

    let mut star_perm: Vec<i32> = (0..n as i32).collect();
    let mut axis: Vec<i8> = vec![-1; total];
    let mut split: Vec<f64> = vec![0.0; total];
    let mut bxmin: Vec<f64> = vec![0.0; total];
    let mut bxmax: Vec<f64> = vec![0.0; total];
    let mut bymin: Vec<f64> = vec![0.0; total];
    let mut bymax: Vec<f64> = vec![0.0; total];
    let mut bzmin: Vec<f64> = vec![0.0; total];
    let mut bzmax: Vec<f64> = vec![0.0; total];

    flat_build(
        0,
        0,
        n,
        xs,
        ys,
        zs,
        &mut star_perm,
        &mut axis,
        &mut split,
        &mut bxmin,
        &mut bxmax,
        &mut bymin,
        &mut bymax,
        &mut bzmin,
        &mut bzmax,
        m - 1,
    );

    // Permuted coordinates for cache-tight leaf scans (each leaf's 8 stars contiguous).
    let mut xs_p: Vec<f64> = Vec::with_capacity(n);
    let mut ys_p: Vec<f64> = Vec::with_capacity(n);
    let mut zs_p: Vec<f64> = Vec::with_capacity(n);
    let mut star_perm_inv: Vec<i32> = vec![-1; n];
    for i in 0..n {
        let orig = star_perm[i] as usize;
        xs_p.push(xs[orig]);
        ys_p.push(ys[orig]);
        zs_p.push(zs[orig]);
        star_perm_inv[orig] = i as i32;
    }

    // Subtree aggregates at build: every star unsettled -> nuns = subtree_size, tsmax = -1.
    // subtree_size for a perfect binary tree with M leaves and 8 stars/leaf: node i's subtree
    // holds N / 2^depth(i) stars. At the root (depth 0) that's N; at each leaf that's 8. Easier
    // to compute in one BFS pass than to track depth explicitly.
    let mut nuns: Vec<i32> = vec![0; total];
    let tsmax: Vec<f64> = vec![-1.0; total];
    // Leaves (indices m-1..2m-2) each hold 8 stars.
    for leaf in (m - 1)..total {
        nuns[leaf] = KD_LEAF as i32;
    }
    // Internal nodes in reverse BFS order: nuns[i] = nuns[2i+1] + nuns[2i+2].
    if m >= 2 {
        for i in (0..(m - 1)).rev() {
            nuns[i] = nuns[2 * i + 1] + nuns[2 * i + 2];
        }
    }

    let d = PyDict::new_bound(py);
    d.set_item("m", m as i64)?;
    d.set_item("total_nodes", total as i64)?;
    d.set_item("xs_p", xs_p.into_pyarray_bound(py))?;
    d.set_item("ys_p", ys_p.into_pyarray_bound(py))?;
    d.set_item("zs_p", zs_p.into_pyarray_bound(py))?;
    d.set_item("star_perm", star_perm.into_pyarray_bound(py))?;
    d.set_item("star_perm_inv", star_perm_inv.into_pyarray_bound(py))?;
    d.set_item("axis", axis.into_pyarray_bound(py))?;
    d.set_item("split", split.into_pyarray_bound(py))?;
    d.set_item("bxmin", bxmin.into_pyarray_bound(py))?;
    d.set_item("bxmax", bxmax.into_pyarray_bound(py))?;
    d.set_item("bymin", bymin.into_pyarray_bound(py))?;
    d.set_item("bymax", bymax.into_pyarray_bound(py))?;
    d.set_item("bzmin", bzmin.into_pyarray_bound(py))?;
    d.set_item("bzmax", bzmax.into_pyarray_bound(py))?;
    d.set_item("nuns", nuns.into_pyarray_bound(py))?;
    d.set_item("tsmax", tsmax.into_pyarray_bound(py))?;
    Ok(d.into())
}

/// Nearest believed-unsettled star to (px, py, pz) at `year`, flat-tree edition.
///
/// Bit-identical mirror of `nn_impl` (the pointer-tree query) with two mechanical
/// substitutions: `2i+1, 2i+2` for children, `i >= M-1` for the leaf test. The
/// `dhi`/`dlo` pruning, lightcone gate, and (d^2, lowest-original-index) tie-break
/// are copied verbatim, so at matching p2 N this returns the SAME original index
/// as the pointer tree for every query - the acceptance criterion in
/// `test_flat_kdtree_oracle.py`.
///
/// `excl` contains ORIGINAL star indices; the leaf scan checks each candidate's
/// original index (via `star_perm`) against `excl[..n_ex]`, matching the pointer
/// tree's semantics.
#[allow(clippy::too_many_arguments)]
fn flat_nn_impl(
    px: f64,
    py: f64,
    pz: f64,
    year: f64,
    is_instant: bool,
    m: usize,
    xs_p: &[f64],
    ys_p: &[f64],
    zs_p: &[f64],
    sy_p: &[f64],
    star_perm: &[i32],
    axis: &[i8],
    split: &[f64],
    bxmin: &[f64],
    bxmax: &[f64],
    bymin: &[f64],
    bymax: &[f64],
    bzmin: &[f64],
    bzmax: &[f64],
    nuns: &[i32],
    tsmax: &[f64],
    excl: &[i32],
    n_ex: usize,
) -> i64 {
    let c = C_PC_PER_YEAR;
    let mut best: i64 = -1;
    let mut best_d2 = f64::INFINITY;

    // Traversal stack. At N=2^k the tree has depth k-3, so at most k-3 <= ~29 nodes on the
    // stack at once (log2 of 2^32); a fixed 128 is defensively over-sized (matches nn_impl).
    let mut stack: [i32; 128] = [0; 128];
    stack[0] = 0; // root
    let mut sp: usize = 1;
    let m_minus_one = m - 1;

    while sp > 0 {
        sp -= 1;
        let node = stack[sp] as usize;

        let mut dlo2: f64 = 0.0;
        let mut t = bxmin[node] - px;
        if t > 0.0 {
            dlo2 = t * t;
        } else {
            t = px - bxmax[node];
            if t > 0.0 {
                dlo2 = t * t;
            }
        }
        t = bymin[node] - py;
        if t > 0.0 {
            dlo2 += t * t;
        } else {
            t = py - bymax[node];
            if t > 0.0 {
                dlo2 += t * t;
            }
        }
        t = bzmin[node] - pz;
        if t > 0.0 {
            dlo2 += t * t;
        } else {
            t = pz - bzmax[node];
            if t > 0.0 {
                dlo2 += t * t;
            }
        }
        if dlo2 > best_d2 {
            continue;
        }
        if nuns[node] == 0 {
            if is_instant {
                continue;
            }
            // dhi: farthest corner; if that beacon has arrived, all inside have.
            let mut a = px - bxmin[node];
            let mut b = px - bxmax[node];
            let mut a2 = a * a;
            let mut b2 = b * b;
            let mut dhi2 = if a2 > b2 { a2 } else { b2 };
            a = py - bymin[node];
            b = py - bymax[node];
            a2 = a * a;
            b2 = b * b;
            dhi2 += if a2 > b2 { a2 } else { b2 };
            a = pz - bzmin[node];
            b = pz - bzmax[node];
            a2 = a * a;
            b2 = b * b;
            dhi2 += if a2 > b2 { a2 } else { b2 };
            if tsmax[node] + dhi2.sqrt() / c <= year {
                continue;
            }
        }
        if node >= m_minus_one {
            // Leaf: 8 contiguous permuted stars at [leaf_offset .. leaf_offset+8).
            //
            // Two-pass structure for auto-vectorization:
            //   Pass 1: branch-free d² compute over 8 contiguous stars. LLVM can vectorize this
            //           as 8 lanes on AVX-512 (or 4+4 on AVX2). Bit-identical to scalar
            //           `((dx*dx) + (dy*dy)) + (dz*dz)` per lane - IEEE 754 rounds every mulpd/addpd
            //           the same as the scalar equivalents, and there is no FMA (default rustc has
            //           no fast-math).
            //   Pass 2: scalar mask/reduce with settled + exclude + light-cone + tie-break. This
            //           keeps the branching out of the vector pipeline, and the reduce visits stars
            //           0..8 in the SAME order as the old single-pass loop, so the tie-break
            //           `(d², lowest original index)` is preserved.
            let leaf_offset = (node - m_minus_one) * KD_LEAF;
            // Two-pass structure: (1) branch-free d² compute over 8 contiguous stars,
            // (2) scalar mask/reduce with the settled/exclude/light-cone/tie-break logic.
            //
            // Explicit AVX2 intrinsics for step (1) were tried and measured *slower* than
            // this scalar loop at `KD_LEAF = 8` (440k vs 557k qps at N=32768, single-thread).
            // The setup/store overhead of writing an intermediate `[f64; 8]` outweighs the
            // arithmetic savings; scalar `vsubsd`/`vmulsd`/`vaddsd` under `-C target-cpu=
            // x86-64-v3` keeps everything in registers. SIMD would win at leaf sizes of
            // ~32-64 stars, but a wider leaf is a separate architectural call.
            let mut d2s: [f64; KD_LEAF] = [0.0; KD_LEAF];
            for k in 0..KD_LEAF {
                let i = leaf_offset + k;
                let dx = xs_p[i] - px;
                let dy = ys_p[i] - py;
                let dz = zs_p[i] - pz;
                d2s[k] = dx * dx + dy * dy + dz * dz;
            }
            for k in 0..KD_LEAF {
                let i = leaf_offset + k;
                let orig = star_perm[i] as i64;
                // Skip excluded stars (original-index comparison, matches pointer tree).
                let mut skipped = false;
                for j in 0..n_ex {
                    if excl[j] as i64 == orig {
                        skipped = true;
                        break;
                    }
                }
                if skipped {
                    continue;
                }
                let d2 = d2s[k];
                let sy_i = sy_p[i];
                if sy_i >= 0.0 {
                    if is_instant {
                        continue;
                    }
                    // Reuse d2 from Pass 1 for the light-cone check; the scalar version recomputed
                    // dx/dy/dz here, so both `d` values here are IEEE-identical.
                    let d = d2.sqrt();
                    if sy_i + d / c <= year {
                        continue;
                    }
                }
                if d2 < best_d2 || (d2 == best_d2 && best >= 0 && orig < best) {
                    best_d2 = d2;
                    best = orig;
                }
            }
        } else {
            let ax = axis[node];
            let p_ax = if ax == 0 {
                px
            } else if ax == 1 {
                py
            } else {
                pz
            };
            // Same "near-first" ordering as the pointer tree: push far first, then near, so
            // the near child pops next (DFS matches, same visitation order, same pruning).
            let (lo_idx, hi_idx) = (2 * node + 1, 2 * node + 2);
            if p_ax < split[node] {
                stack[sp] = hi_idx as i32;
                sp += 1;
                stack[sp] = lo_idx as i32;
                sp += 1;
            } else {
                stack[sp] = lo_idx as i32;
                sp += 1;
                stack[sp] = hi_idx as i32;
                sp += 1;
            }
        }
    }
    best
}

/// pyfunction wrapper for `flat_nn_impl` - exposes the query to Python callers.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn nearest_unsettled_flat(
    px: f64,
    py: f64,
    pz: f64,
    year: f64,
    is_instant: bool,
    xs_p: PyReadonlyArray1<f64>,
    ys_p: PyReadonlyArray1<f64>,
    zs_p: PyReadonlyArray1<f64>,
    sy_p: PyReadonlyArray1<f64>,
    star_perm: PyReadonlyArray1<i32>,
    axis: PyReadonlyArray1<i8>,
    split: PyReadonlyArray1<f64>,
    bxmin: PyReadonlyArray1<f64>,
    bxmax: PyReadonlyArray1<f64>,
    bymin: PyReadonlyArray1<f64>,
    bymax: PyReadonlyArray1<f64>,
    bzmin: PyReadonlyArray1<f64>,
    bzmax: PyReadonlyArray1<f64>,
    nuns: PyReadonlyArray1<i32>,
    tsmax: PyReadonlyArray1<f64>,
    exclude: PyReadonlyArray1<i32>,
    n_excludes: i64,
) -> PyResult<i64> {
    let n = xs_p.len()?;
    if n == 0 || n % KD_LEAF != 0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "flat tree arrays must have length that is a multiple of KD_LEAF (8)",
        ));
    }
    let m = n / KD_LEAF;
    Ok(flat_nn_impl(
        px,
        py,
        pz,
        year,
        is_instant,
        m,
        xs_p.as_slice()?,
        ys_p.as_slice()?,
        zs_p.as_slice()?,
        sy_p.as_slice()?,
        star_perm.as_slice()?,
        axis.as_slice()?,
        split.as_slice()?,
        bxmin.as_slice()?,
        bxmax.as_slice()?,
        bymin.as_slice()?,
        bymax.as_slice()?,
        bzmin.as_slice()?,
        bzmax.as_slice()?,
        nuns.as_slice()?,
        tsmax.as_slice()?,
        exclude.as_slice()?,
        n_excludes as usize,
    ))
}

/// Fold star `original_idx`'s settlement into the flat tree's leaf-to-root
/// aggregates. Pointer-free: parent walk uses `(i - 1) >> 1`.
///
/// Mutates `sy_p`, `nuns`, `tsmax` in place; `star_perm_inv` is read to find the
/// star's permuted position. Must be called exactly once per star, at the time
/// its `settled_year` is first assigned - same contract as
/// `swarm.sim._kd_mark_settled` for the pointer tree.
#[pyfunction]
fn mark_settled_flat(
    original_idx: i64,
    year: f64,
    mut sy_p: PyReadwriteArray1<f64>,
    mut nuns: PyReadwriteArray1<i32>,
    mut tsmax: PyReadwriteArray1<f64>,
    star_perm_inv: PyReadonlyArray1<i32>,
) -> PyResult<()> {
    let perm_inv = star_perm_inv.as_slice()?;
    let n = perm_inv.len();
    if !is_power_of_two(n) || n < KD_LEAF {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "star_perm_inv length must be a power of two >= KD_LEAF (8)",
        ));
    }
    let m = n / KD_LEAF;
    if original_idx < 0 || (original_idx as usize) >= n {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "original_idx out of range for star_perm_inv",
        ));
    }
    let pidx = perm_inv[original_idx as usize] as usize;
    let sy_slice = sy_p.as_slice_mut()?;
    sy_slice[pidx] = year;
    let nuns_slice = nuns.as_slice_mut()?;
    let tsmax_slice = tsmax.as_slice_mut()?;
    // Leaf node containing this star: BFS index `M-1 + pidx / 8`.
    let mut node: i64 = (m - 1 + pidx / KD_LEAF) as i64;
    loop {
        let n_i = node as usize;
        nuns_slice[n_i] -= 1;
        if year > tsmax_slice[n_i] {
            tsmax_slice[n_i] = year;
        }
        if node == 0 {
            break;
        }
        node = (node - 1) >> 1;
    }
    Ok(())
}

/// Fold star `star_orig`'s settlement into the flat tree's aggregates. Free
/// function used inside `run_fill_flat` (which holds mutable borrows to sy, sy_p,
/// nuns, tsmax and cannot use the `#[pyfunction]` `mark_settled_flat` above).
///
/// Updates both `sy` (unpermuted, for O(1) reads by original index in the event
/// loop) and `sy_p` (permuted, threaded into `flat_nn_impl`). The dual write is
/// cheap - one memory store each - and eliminates the permutation lookup in the
/// hot query.
#[inline]
fn mark_settled_flat_impl(
    star_orig: usize,
    year: f64,
    sy: &mut [f64],
    sy_p: &mut [f64],
    nuns: &mut [i32],
    tsmax: &mut [f64],
    star_perm_inv: &[i32],
    m: usize,
) {
    let pidx = star_perm_inv[star_orig] as usize;
    sy[star_orig] = year;
    sy_p[pidx] = year;
    // Leaf containing this star: BFS index `M-1 + pidx / 8`.
    let mut node: i64 = (m - 1 + pidx / KD_LEAF) as i64;
    loop {
        let n_i = node as usize;
        nuns[n_i] -= 1;
        if year > tsmax[n_i] {
            tsmax[n_i] = year;
        }
        if node == 0 {
            break;
        }
        node = (node - 1) >> 1;
    }
}

/// The p2 twin of `run_fill`: same event loop, same aggregate outputs, but the
/// tree ops (`nearest_unsettled`, `mark_settled`) go through the flat p2 kd-tree
/// (issue #38 p2 substrate). At `n_stars = 2^k, k >= 3` this is a drop-in for
/// `run_fill`; the oracle `test_flat_run_fill_oracle.py` requires the two return
/// byte-identical aggregates across every coordination mode + periodicity +
/// (offspring, retarget-cap, seed) combination in the test matrix.
///
/// Every f64 discipline of `run_fill` carries over: `sqrt` in the query kernel
/// (matches numba `nearest_unsettled_njit`), `ref_root` (glibc `pow(x, 0.5)`)
/// for hop distances (matches CPython `** 0.5`, see the module-level notes on
/// the 1-ULP glibc pow/sqrt divergence #78 pinned). The heap, `Pool`, event
/// resolution, and inflight decrease-key are unchanged from `run_fill` because
/// they are tree-agnostic.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn run_fill_flat(
    py: Python<'_>,
    xs: PyReadonlyArray1<f64>,
    ys: PyReadonlyArray1<f64>,
    zs: PyReadonlyArray1<f64>,
    origin: i64,
    xs_p: PyReadonlyArray1<f64>,
    ys_p: PyReadonlyArray1<f64>,
    zs_p: PyReadonlyArray1<f64>,
    star_perm: PyReadonlyArray1<i32>,
    star_perm_inv: PyReadonlyArray1<i32>,
    kd_axis: PyReadonlyArray1<i8>,
    kd_split: PyReadonlyArray1<f64>,
    kd_bxmin: PyReadonlyArray1<f64>,
    kd_bxmax: PyReadonlyArray1<f64>,
    kd_bymin: PyReadonlyArray1<f64>,
    kd_bymax: PyReadonlyArray1<f64>,
    kd_bzmin: PyReadonlyArray1<f64>,
    kd_bzmax: PyReadonlyArray1<f64>,
    kd_nuns: PyReadonlyArray1<i32>,
    kd_tsmax: PyReadonlyArray1<f64>,
    is_instant: bool,
    is_inflight: bool,
    box_side: f64,
    periodic: bool,
    probe_speed: f64,
    offspring: i64,
    settle_time: f64,
    max_years: f64,
    max_retargets: i64,
    inv_d_nn: f64,
    hop_edges: PyReadonlyArray1<f64>,
    wall_edges: PyReadonlyArray1<f64>,
) -> PyResult<Py<PyDict>> {
    let xs = xs.as_slice()?;
    let ys = ys.as_slice()?;
    let zs = zs.as_slice()?;
    let xs_p = xs_p.as_slice()?;
    let ys_p = ys_p.as_slice()?;
    let zs_p = zs_p.as_slice()?;
    let star_perm = star_perm.as_slice()?;
    let star_perm_inv = star_perm_inv.as_slice()?;
    let axis = kd_axis.as_slice()?;
    let split = kd_split.as_slice()?;
    let bxmin = kd_bxmin.as_slice()?;
    let bxmax = kd_bxmax.as_slice()?;
    let bymin = kd_bymin.as_slice()?;
    let bymax = kd_bymax.as_slice()?;
    let bzmin = kd_bzmin.as_slice()?;
    let bzmax = kd_bzmax.as_slice()?;
    let hop_edges = hop_edges.as_slice()?;
    let wall_edges = wall_edges.as_slice()?;

    let n = xs.len();
    if !is_power_of_two(n) || n < KD_LEAF {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "run_fill_flat requires n_stars to be a power of two >= {} (got {})",
            KD_LEAF, n
        )));
    }
    let m_leaves = n / KD_LEAF;
    let mut sy: Vec<f64> = vec![-1.0; n];
    let mut sy_p: Vec<f64> = vec![-1.0; n];
    let mut nuns: Vec<i32> = kd_nuns.as_slice()?.to_vec();
    let mut tsmax: Vec<f64> = kd_tsmax.as_slice()?.to_vec();

    let n_hop = hop_edges.len() + 1;
    let n_wall = wall_edges.len() + 1;

    let mut settled_count: i64 = 1;
    let mut total_launched: i64 = 0;
    let mut total_arrivals: i64 = 0;
    let mut wasted_arrivals: i64 = 0;
    let mut retarget_count: i64 = 0;
    let mut wasted_travel_pc: f64 = 0.0;
    let mut front_radius: f64 = 0.0;
    let mut settle_hop_sum: f64 = 0.0;
    let mut settle_hop_count: i64 = 0;
    let mut wasted_hop_sum: f64 = 0.0;
    let mut wasted_hop_count: i64 = 0;
    let mut settle_v_sum: f64 = 0.0;
    let mut settle_v2_sum: f64 = 0.0;
    let mut wasted_v_sum: f64 = 0.0;
    let mut wasted_v2_sum: f64 = 0.0;
    let mut midflight_aborts: i64 = 0;
    let mut launch_speed_sum: f64 = 0.0;
    let mut launch_count: i64 = 0;
    let mut settle_hop_hist: Vec<i64> = vec![0; n_hop];
    let mut wasted_hop_hist: Vec<i64> = vec![0; n_hop];
    let mut settle_wall_hist: Vec<i64> = vec![0; n_wall];
    let mut wasted_wall_hist: Vec<i64> = vec![0; n_wall];
    let mut wasted_s_hist: Vec<i64> = vec![0; 32];

    let pcts: [f64; 6] = [25.0, 50.0, 75.0, 90.0, 99.0, 100.0];
    let mut thr: [f64; 6] = [-1.0; 6];
    let n_f = n as f64;
    let record_thresholds = |settled_count: i64, year: f64, thr: &mut [f64; 6]| {
        let frac = settled_count as f64 / n_f * 100.0;
        for k in 0..6 {
            if thr[k] < 0.0 && frac >= pcts[k] {
                thr[k] = year;
            }
        }
    };

    let mut pool = Pool::new();
    let mut heap: BinaryHeap<Reverse<Ev>> = BinaryHeap::new();
    let mut by_target: Vec<Vec<i64>> = if is_inflight {
        (0..n).map(|_| Vec::new()).collect()
    } else {
        Vec::new()
    };
    let v_over_c = probe_speed / C_PC_PER_YEAR;

    macro_rules! nn {
        ($px:expr, $py:expr, $pz:expr, $year:expr, $excl:expr, $n_ex:expr) => {
            flat_nn_impl(
                $px, $py, $pz, $year, is_instant, m_leaves,
                xs_p, ys_p, zs_p, &sy_p, star_perm,
                axis, split, bxmin, bxmax, bymin, bymax, bzmin, bzmax,
                &nuns, &tsmax, $excl, $n_ex,
            )
        };
    }
    macro_rules! actionable {
        ($pu:expr) => {
            actionable_of($pu, &pool.target, &pool.arrive, &sy, is_inflight, v_over_c)
        };
    }
    macro_rules! add_probe {
        ($pid:expr) => {{
            let _pid: i64 = $pid;
            let _pu = _pid as usize;
            pool.live[_pu] = true;
            let _k = actionable!(_pu);
            heap.push(Reverse(Ev { key: _k, pid: _pid }));
            if is_inflight {
                by_target[pool.target[_pu] as usize].push(_pid);
            }
        }};
    }

    let origin_u = origin as usize;
    mark_settled_flat_impl(
        origin_u, 0.0,
        &mut sy, &mut sy_p, &mut nuns, &mut tsmax, star_perm_inv, m_leaves,
    );
    {
        let ox = xs[origin_u];
        let oy = ys[origin_u];
        let oz = zs[origin_u];
        let mut chosen: Vec<i32> = Vec::new();
        let departing = probe_speed;
        for _ in 0..offspring {
            let target = nn!(ox, oy, oz, 0.0, &chosen, chosen.len());
            if target < 0 {
                break;
            }
            chosen.push(target as i32);
            let hop = dist(xs, ys, zs, origin_u, target as usize, periodic, box_side);
            let travel = hop / departing;
            let pid = pool.push(target, 0.0 + settle_time + travel, hop, 0, 0.0 + settle_time, ox, oy, oz);
            add_probe!(pid);
            total_launched += 1;
            launch_speed_sum += departing;
            launch_count += 1;
        }
    }
    let initial_in_flight = launch_count;
    record_thresholds(settled_count, 0.0, &mut thr);

    let mut batch: Vec<i64> = Vec::new();
    let mut arrivals: Vec<i64> = Vec::new();
    let mut learns: Vec<i64> = Vec::new();
    let mut seen: HashSet<i64> = HashSet::new();
    loop {
        let ne = loop {
            match heap.peek() {
                None => break f64::NAN,
                Some(&Reverse(top)) => {
                    let pu = top.pid as usize;
                    if !pool.live[pu] || actionable!(pu) != top.key {
                        heap.pop();
                        continue;
                    }
                    break top.key;
                }
            }
        };
        if ne.is_nan() || ne > max_years {
            break;
        }
        let year = ne;
        batch.clear();
        seen.clear();
        while let Some(&Reverse(e)) = heap.peek() {
            if e.key > ne {
                break;
            }
            heap.pop();
            let pu = e.pid as usize;
            if !pool.live[pu] || seen.contains(&e.pid) || actionable!(pu) != e.key {
                continue;
            }
            seen.insert(e.pid);
            batch.push(e.pid);
        }
        arrivals.clear();
        learns.clear();
        for &pid in &batch {
            let pu = pid as usize;
            let tu = pool.target[pu] as usize;
            let is_learn = is_inflight
                && sy[tu] >= 0.0
                && learn_year_of(pu, &pool.target, &pool.arrive, &sy, v_over_c) < pool.arrive[pu];
            if is_learn {
                learns.push(pid);
            } else {
                arrivals.push(pid);
            }
        }
        arrivals.sort_by(|&a, &b| {
            pool.arrive[a as usize].total_cmp(&pool.arrive[b as usize]).then(a.cmp(&b))
        });
        learns.sort_by(|&a, &b| {
            pool.arrive[a as usize].total_cmp(&pool.arrive[b as usize]).then(a.cmp(&b))
        });

        for &pid in &arrivals {
            pool.live[pid as usize] = false;
        }
        total_arrivals += arrivals.len() as i64;
        for &pid in &arrivals {
            let pu = pid as usize;
            let target = pool.target[pu];
            let tu = target as usize;
            let hop_len = pool.hop[pu];
            let v = probe_speed;

            let hb = bin_ge(hop_edges, hop_len);
            let x = xs[tu];
            let y = ys[tu];
            let z = zs[tu];
            let mut wall = if x < box_side - x { x } else { box_side - x };
            let yy = if y < box_side - y { y } else { box_side - y };
            if yy < wall {
                wall = yy;
            }
            let zz = if z < box_side - z { z } else { box_side - z };
            if zz < wall {
                wall = zz;
            }
            let r = wall * inv_d_nn;
            let wb = bin_ge(wall_edges, r);

            if sy[tu] < 0.0 {
                mark_settled_flat_impl(
                    tu, year,
                    &mut sy, &mut sy_p, &mut nuns, &mut tsmax, star_perm_inv, m_leaves,
                );
                settled_count += 1;
                let d_origin = dist(xs, ys, zs, tu, origin_u, periodic, box_side);
                if d_origin > front_radius {
                    front_radius = d_origin;
                }
                if is_inflight {
                    let m = by_target[tu].len();
                    for k in 0..m {
                        let qpid = by_target[tu][k];
                        let qu = qpid as usize;
                        if pool.live[qu] && pool.target[qu] == target {
                            let kk = actionable!(qu);
                            heap.push(Reverse(Ev { key: kk, pid: qpid }));
                        }
                    }
                    by_target[tu].clear();
                }
                settle_hop_sum += hop_len;
                settle_hop_count += 1;
                settle_hop_hist[hb] += 1;
                settle_wall_hist[wb] += 1;
                settle_v_sum += v;
                settle_v2_sum += v * v;
                let departing = probe_speed;
                let mut chosen: Vec<i32> = Vec::new();
                for _ in 0..offspring {
                    let nt = nn!(x, y, z, year, &chosen, chosen.len());
                    if nt < 0 {
                        break;
                    }
                    chosen.push(nt as i32);
                    let hop = dist(xs, ys, zs, tu, nt as usize, periodic, box_side);
                    let travel = hop / departing;
                    let npid =
                        pool.push(nt, year + settle_time + travel, hop, 0, year + settle_time, x, y, z);
                    add_probe!(npid);
                    total_launched += 1;
                    launch_speed_sum += departing;
                    launch_count += 1;
                }
            } else {
                wasted_arrivals += 1;
                wasted_hop_sum += hop_len;
                wasted_hop_count += 1;
                wasted_hop_hist[hb] += 1;
                wasted_wall_hist[wb] += 1;
                wasted_travel_pc += hop_len;
                wasted_v_sum += v;
                wasted_v2_sum += v * v;
                let span = pool.arrive[pu] - pool.launch[pu];
                if span > 0.0 {
                    let s = (sy[tu] - pool.launch[pu]) / span;
                    let sb: usize = if s < 0.0 {
                        0
                    } else if s >= 1.0 {
                        31
                    } else {
                        (s * 32.0) as usize
                    };
                    wasted_s_hist[sb] += 1;
                }
                if pool.retargets[pu] >= max_retargets {
                    continue;
                }
                let empty: [i32; 0] = [];
                let nt = nn!(x, y, z, year, &empty, 0);
                if nt >= 0 {
                    retarget_count += 1;
                    let hop = dist(xs, ys, zs, tu, nt as usize, periodic, box_side);
                    let travel = hop / v;
                    pool.target[pu] = nt;
                    pool.arrive[pu] = year + travel;
                    pool.retargets[pu] += 1;
                    pool.hop[pu] = hop;
                    pool.launch[pu] = year;
                    pool.from_x[pu] = x;
                    pool.from_y[pu] = y;
                    pool.from_z[pu] = z;
                    add_probe!(pid);
                }
            }
        }

        for &pid in &learns {
            pool.live[pid as usize] = false;
        }
        for &pid in &learns {
            let pu = pid as usize;
            let tu = pool.target[pu] as usize;
            let span = pool.arrive[pu] - pool.launch[pu];
            let mut frac = if span > 0.0 { (year - pool.launch[pu]) / span } else { 1.0 };
            frac = if frac < 0.0 {
                0.0
            } else if frac > 1.0 {
                1.0
            } else {
                frac
            };
            let px = pool.from_x[pu] + (xs[tu] - pool.from_x[pu]) * frac;
            let py = pool.from_y[pu] + (ys[tu] - pool.from_y[pu]) * frac;
            let pz = pool.from_z[pu] + (zs[tu] - pool.from_z[pu]) * frac;
            wasted_travel_pc += pool.hop[pu] * frac;
            midflight_aborts += 1;
            if pool.retargets[pu] >= max_retargets {
                continue;
            }
            let empty: [i32; 0] = [];
            let nt = nn!(px, py, pz, year, &empty, 0);
            if nt < 0 {
                continue;
            }
            retarget_count += 1;
            let dx = xs[nt as usize] - px;
            let dy = ys[nt as usize] - py;
            let dz = zs[nt as usize] - pz;
            let hop = ref_root(dx * dx + dy * dy + dz * dz);
            let travel = hop / probe_speed;
            pool.target[pu] = nt;
            pool.arrive[pu] = year + travel;
            pool.retargets[pu] += 1;
            pool.hop[pu] = hop;
            pool.from_x[pu] = px;
            pool.from_y[pu] = py;
            pool.from_z[pu] = pz;
            pool.launch[pu] = year;
            add_probe!(pid);
        }

        record_thresholds(settled_count, year, &mut thr);
    }

    let d = PyDict::new_bound(py);
    d.set_item("final_settled", settled_count)?;
    d.set_item("total_launched", total_launched)?;
    d.set_item("total_arrivals", total_arrivals)?;
    d.set_item("wasted_arrivals", wasted_arrivals)?;
    d.set_item("retarget_count", retarget_count)?;
    d.set_item("wasted_travel_pc", wasted_travel_pc)?;
    d.set_item("midflight_aborts", midflight_aborts)?;
    d.set_item("front_radius_pc", front_radius)?;
    d.set_item("max_speed_pc_yr", probe_speed)?;
    d.set_item("settle_hop_sum_pc", settle_hop_sum)?;
    d.set_item("settle_hop_count", settle_hop_count)?;
    d.set_item("wasted_hop_sum_pc", wasted_hop_sum)?;
    d.set_item("wasted_hop_count", wasted_hop_count)?;
    d.set_item("settle_v_sum_pc_yr", settle_v_sum)?;
    d.set_item("settle_v2_sum", settle_v2_sum)?;
    d.set_item("wasted_v_sum_pc_yr", wasted_v_sum)?;
    d.set_item("wasted_v2_sum", wasted_v2_sum)?;
    d.set_item("launch_speed_sum_pc_yr", launch_speed_sum)?;
    d.set_item("launch_count", launch_count)?;
    d.set_item("t25", if thr[0] < 0.0 { py.None() } else { thr[0].into_py(py) })?;
    d.set_item("t50", if thr[1] < 0.0 { py.None() } else { thr[1].into_py(py) })?;
    d.set_item("t75", if thr[2] < 0.0 { py.None() } else { thr[2].into_py(py) })?;
    d.set_item("t90", if thr[3] < 0.0 { py.None() } else { thr[3].into_py(py) })?;
    d.set_item("t99", if thr[4] < 0.0 { py.None() } else { thr[4].into_py(py) })?;
    d.set_item("t100", if thr[5] < 0.0 { py.None() } else { thr[5].into_py(py) })?;
    d.set_item("settle_hop_hist", settle_hop_hist)?;
    d.set_item("wasted_hop_hist", wasted_hop_hist)?;
    d.set_item("settle_wall_hist", settle_wall_hist)?;
    d.set_item("wasted_wall_hist", wasted_wall_hist)?;
    d.set_item("wasted_s_hist", wasted_s_hist)?;
    d.set_item("initial_in_flight", initial_in_flight)?;
    Ok(d.into())
}

#[pymodule]
fn swarm_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(nearest_unsettled, m)?)?;
    m.add_function(wrap_pyfunction!(run_fill, m)?)?;
    m.add_function(wrap_pyfunction!(c_pc_per_year, m)?)?;
    m.add_function(wrap_pyfunction!(build_flat_kdtree, m)?)?;
    m.add_function(wrap_pyfunction!(nearest_unsettled_flat, m)?)?;
    m.add_function(wrap_pyfunction!(mark_settled_flat, m)?)?;
    m.add_function(wrap_pyfunction!(run_fill_flat, m)?)?;
    Ok(())
}
