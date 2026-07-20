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

use numpy::PyReadonlyArray1;
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

#[pymodule]
fn swarm_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(nearest_unsettled, m)?)?;
    m.add_function(wrap_pyfunction!(run_fill, m)?)?;
    m.add_function(wrap_pyfunction!(c_pc_per_year, m)?)?;
    Ok(())
}
