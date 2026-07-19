//! swarm_rust - Rust drop-in for the swarm k-d tree nearest-unsettled query.
//!
//! Issue #33, Phase 1. This crate mirrors `swarm/src/swarm/kd_njit.py` (the
//! numba-jitted version) function-for-function. Every arithmetic operation is
//! written in the same order as the Python reference (`sim._nearest_unsettled_at_python`
//! at line 428 of sim.py), because both sides use IEEE 754 f64 and the
//! `SwarmResult` bit-identity acceptance is fragile to any reordering.
//!
//! Discipline (matches `kd_njit.py`, docstring lines 9-13):
//!   - no `fastmath`: never enabled on `f64` here; Rust does not reassociate
//!     floats without `#[allow(clippy::float_cmp)]` shenanigans or explicit
//!     intrinsics, which are absent.
//!   - `f64::sqrt`: delegates to the hardware SQRTSD (x86_64) / FSQRT (aarch64)
//!     instructions, which are bit-identical across every modern platform (SSE2
//!     is IEEE 754 correctly-rounded).
//!   - the DFS stack is an explicit `Vec<i32>` matching the numba preallocated
//!     stack shape: push right-then-left when the probe is on the "lo" side so
//!     the "lo" child pops first (nearer-first DFS).
//!   - the leaf `(d^2, lowest-index)` tie-break is spelled exactly as in the
//!     Python: `d2 < best_d2 || (d2 == best_d2 && best >= 0 && i < best)`.

use numpy::PyReadonlyArray1;
use pyo3::prelude::*;

/// Speed of light in parsecs per Julian year (from `swarm/models.py:24`,
/// `299792.458 * 3.15576e7 / 3.0856775814913673e13`). Written as the same
/// left-to-right expression so a Rust `const` matches Python's runtime f64
/// exactly (no reassociation).
const C_PC_PER_YEAR: f64 = 299792.458_f64 * 3.15576e7_f64 / 3.0856775814913673e13_f64;

/// Nearest believed-unsettled star to `(px, py, pz)` at `year`, or -1 if none.
///
/// Bit-identical mirror of `swarm.kd_njit.nearest_unsettled_njit`. All arrays
/// are read-only zero-copy views on the caller's numpy buffers.
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
    // as_slice() returns Err only on non-contiguous arrays; every caller in
    // swarm.sim passes a plain 1-D numpy array, so this is a bug-not-a-user-
    // error condition, hence the `?` bubbles up as a Python error.
    let xs = xs.as_slice()?;
    let ys = ys.as_slice()?;
    let zs = zs.as_slice()?;
    let sy = settled_year.as_slice()?;
    let axis = kd_axis.as_slice()?;
    let split = kd_split.as_slice()?;
    let lo = kd_lo.as_slice()?;
    let hi = kd_hi.as_slice()?;
    let bxmin = kd_bxmin.as_slice()?;
    let bxmax = kd_bxmax.as_slice()?;
    let bymin = kd_bymin.as_slice()?;
    let bymax = kd_bymax.as_slice()?;
    let bzmin = kd_bzmin.as_slice()?;
    let bzmax = kd_bzmax.as_slice()?;
    let nuns = kd_nuns.as_slice()?;
    let tsmax = kd_tsmax.as_slice()?;
    let bucket_flat = kd_bucket_flat.as_slice()?;
    let bucket_offsets = kd_bucket_offsets.as_slice()?;
    let excl = exclude.as_slice()?;
    let n_ex = n_excludes as usize;

    if kd_root < 0 {
        return Ok(-1);
    }
    let c = C_PC_PER_YEAR;
    let mut best: i64 = -1;
    let mut best_d2 = f64::INFINITY;

    // A stack of 128 int32 entries is what kd_njit uses (`stack = np.empty(128, dtype=np.int32)`)
    // and matches a balanced tree of ~2^30 nodes' worst-case depth (2 log2 N). 200k stars is
    // depth ~36; 128 leaves plenty of headroom.
    let mut stack: [i32; 128] = [0; 128];
    stack[0] = kd_root;
    let mut sp: usize = 1;

    while sp > 0 {
        sp -= 1;
        let node = stack[sp] as usize;

        // dlo^2: nearest point of the node's bounding box to (px, py, pz).
        // Structured EXACTLY like the reference (same branches, same ops) so
        // no phantom rounding is introduced. `dlo2 = t*t` (not `+= t*t`) on
        // the first axis because the accumulator starts at 0.0.
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
            // dhi^2: farthest corner of the box. If tsmax + dhi/c <= year, every
            // star in this subtree is BELIEVED settled at the query point, so
            // skip the whole box. Same three-axis unroll as the reference.
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
            // dhi ** 0.5 in the reference == f64::sqrt(dhi2) here (same operator,
            // both delegate to hardware sqrt).
            if tsmax[node] + dhi2.sqrt() / c <= year {
                continue;
            }
        }
        let ax = axis[node];
        if ax == -1 {
            // Leaf: scan the bucket in stored order (same iteration as the ref).
            let start = bucket_offsets[node] as usize;
            let end = bucket_offsets[node + 1] as usize;
            for k in start..end {
                let i = bucket_flat[k] as usize;
                // exclude check: linear scan (typical len 0-2, hard cap ~30).
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
                // Inlined `_believes_settled_at`: settled AND light has arrived.
                let sy_i = sy[i];
                if sy_i >= 0.0 {
                    if is_instant {
                        continue;
                    }
                    let dx = xs[i] - px;
                    let dy = ys[i] - py;
                    let dz = zs[i] - pz;
                    let d = (dx * dx + dy * dy + dz * dz).sqrt();
                    if sy_i + d / c <= year {
                        continue;
                    }
                }
                // Distance-squared for the tie-break argmin. Recomputed here
                // (not reused from above) to match the reference's op order,
                // which recomputes it inside the tie-break too.
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
            // Internal: DFS the nearer child first. Push the FAR child first
            // so it is popped LAST (LIFO); the near child is on top and popped
            // next iteration.
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
    Ok(best)
}

/// A tiny sanity function exposed for the build-verification test: given the
/// two Python-side numbers that make up `C_PC_PER_YEAR`, return Rust's
/// left-to-right f64 result. The test asserts this bit-matches the Python
/// constant, which pins the "no float reassociation" guarantee at the ABI
/// boundary.
#[pyfunction]
fn c_pc_per_year() -> f64 {
    C_PC_PER_YEAR
}

#[pymodule]
fn swarm_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(nearest_unsettled, m)?)?;
    m.add_function(wrap_pyfunction!(c_pc_per_year, m)?)?;
    Ok(())
}
