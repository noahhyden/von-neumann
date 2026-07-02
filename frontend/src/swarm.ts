/**
 * TS port of the `swarm` module (slice 1) — a deterministic settlement front.
 *
 * Faithful port of the Python `swarm.sim`: probes spread star-to-star through a seeded
 * field, settling the nearest unsettled star at a fraction of c and launching offspring.
 * Pure, seeded, fixed-step; the mulberry32 RNG is byte-identical to the Python (and to
 * the other modules), so the star field and the whole run replay bit-for-bit. Parity
 * tested against the Python ground truth in `swarm.test.ts` (Layer A). Self-contained
 * (no sibling ports), so it loads directly under `node --test`.
 *
 * The result exposes the final star field (positions + per-star settlement year) so the
 * frontend can draw the front at any scrubbed year without re-running the fold.
 */

// c in parsecs per Julian year — derived from defined constants (see swarm/REFERENCES.md).
export const C_PC_PER_YEAR = (299792.458 * 3.15576e7) / 3.0856775814913673e13;
export const KM_S_TO_PC_YR = (3.15576e7) / 3.0856775814913673e13; // 1 km/s in pc/yr

export type Policy = "powered" | "slingshot_nearest" | "slingshot_maxboost";

// ── mulberry32, threaded — mirrors swarm/rng.py ────────────────────────────────
function nextFloat(state: number): [number, number] {
  const s = (state + 0x6d2b79f5) | 0;
  let t = Math.imul(s ^ (s >>> 15), 1 | s);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return [((t ^ (t >>> 14)) >>> 0) / 4294967296, s | 0];
}
const seedState = (seed: number): number => seed | 0;

export interface SwarmParams {
  nStars: number;
  densityStarsPerPc3: number;
  probeSpeedC: number;
  offspringPerSettlement: number;
  settleTimeYears: number;
  dtYears: number;
  maxYears: number;
  // slingshot dynamics (mirrors the Python; see swarm/REFERENCES.md)
  policy: Policy;
  starSpeedKmS: number;
  starSpeedDispersionKmS: number;
  escapeVelocityKmS: number;
  maxBoostCandidates: number;
  speedCapC: number;
}

export const SWARM_DEFAULTS: SwarmParams = {
  nStars: 500,
  densityStarsPerPc3: 1.0, // Nicholson & Forgan use a uniform 1 star/pc^3
  probeSpeedC: 3e-5, // N&F powered cruise: 3e-5 c ≈ 9 km/s
  offspringPerSettlement: 2,
  settleTimeYears: 0,
  dtYears: 5000,
  maxYears: 50_000_000,
  policy: "powered", // default = no slingshots; keeps powered baselines identical
  starSpeedKmS: 220, // [ESTIMATE] galactic rotation
  starSpeedDispersionKmS: 40, // [ESTIMATE] disc dispersion
  escapeVelocityKmS: 617.5, // solar sqrt(2GM/R), derived
  maxBoostCandidates: 30, // [ESTIMATE] max-boost scans this many nearest
  speedCapC: 0.05, // [ESTIMATE] sanity ceiling
};

export const boxSidePc = (p: SwarmParams): number => Math.pow(p.nStars / p.densityStarsPerPc3, 1 / 3);
export const probeSpeedPcPerYear = (p: SwarmParams): number => p.probeSpeedC * C_PC_PER_YEAR;

interface Probe {
  id: number;
  target: number;
  arriveYear: number;
  speedPcYr: number; // current galactic-frame speed (constant for powered; accumulates otherwise)
}

/**
 * A uniform-grid spatial index over the (static) star positions. Cells hold star
 * indices; nearest-unsettled queries expand Chebyshev shells outward and stop once no
 * unexamined cell can beat the best distance. Built once (positions never move); only
 * the settled mask changes between queries. Returns EXACTLY what the brute-force scan
 * returns — same nearest star, same lowest-index tie-break — so it's a pure speedup
 * (proven bit-identical in the tests). This is the "scale" slice's core (§7: the
 * spatial index lives in the frontend, not the pure Python ground truth).
 */
export interface Grid {
  cellSize: number;
  dim: number; // cells per axis
  cells: number[][]; // cells[ix*dim*dim + iy*dim + iz] = star indices in that cell
}

export interface SwarmState {
  rng: number;
  year: number;
  xs: number[];
  ys: number[];
  zs: number[];
  settledYear: number[]; // -1 while unsettled
  origin: number;
  probes: Probe[];
  nextProbeId: number;
  totalLaunched: number;
  grid: Grid; // spatial index for nearest-unsettled (accelerates the O(N) scan)
  settledCount: number; // tracked incrementally so per-step metrics are O(1), not O(N)
  frontMaxPc: number; // farthest settled star from the origin, tracked incrementally
  starSpeedPcYr: number[]; // per-star speed magnitude (drives the slingshot boost)
  maxSpeedPcYr: number; // fastest probe launched so far
}

function buildGrid(xs: number[], ys: number[], zs: number[], boxSide: number): Grid {
  const n = xs.length;
  const dim = Math.max(1, Math.round(Math.cbrt(n))); // ~1 star per cell
  const cellSize = boxSide / dim;
  const cells: number[][] = Array.from({ length: dim * dim * dim }, () => []);
  const cellIndex = (x: number, y: number, z: number): number => {
    const ix = Math.min(dim - 1, Math.max(0, Math.floor(x / cellSize)));
    const iy = Math.min(dim - 1, Math.max(0, Math.floor(y / cellSize)));
    const iz = Math.min(dim - 1, Math.max(0, Math.floor(z / cellSize)));
    return (ix * dim + iy) * dim + iz;
  };
  for (let i = 0; i < n; i++) cells[cellIndex(xs[i], ys[i], zs[i])].push(i);
  return { cellSize, dim, cells };
}

/** Remove a (now-settled) star from its grid cell, so future queries never scan it.
 *  This keeps nearest-unsettled fast even late in the fill, when most stars are settled. */
function removeFromGrid(s: SwarmState, i: number): void {
  const g = s.grid;
  const ix = Math.min(g.dim - 1, Math.max(0, Math.floor(s.xs[i] / g.cellSize)));
  const iy = Math.min(g.dim - 1, Math.max(0, Math.floor(s.ys[i] / g.cellSize)));
  const iz = Math.min(g.dim - 1, Math.max(0, Math.floor(s.zs[i] / g.cellSize)));
  const cell = g.cells[(ix * g.dim + iy) * g.dim + iz];
  const at = cell.indexOf(i);
  if (at !== -1) cell[cell.length - 1] === i ? cell.pop() : (cell[at] = cell.pop()!);
}

/** Brute-force nearest unsettled star — the reference the grid must match exactly. */
function bruteNearestUnsettled(s: SwarmState, frm: number, exclude: Set<number>): number | null {
  let best: number | null = null;
  let bestD2 = Infinity;
  const fx = s.xs[frm], fy = s.ys[frm], fz = s.zs[frm];
  for (let i = 0; i < s.xs.length; i++) {
    if (s.settledYear[i] >= 0 || exclude.has(i)) continue;
    const dx = s.xs[i] - fx, dy = s.ys[i] - fy, dz = s.zs[i] - fz;
    const d2 = dx * dx + dy * dy + dz * dz;
    if (d2 < bestD2) {
      bestD2 = d2;
      best = i;
    }
  }
  return best;
}

/** Grid-accelerated nearest unsettled star; returns the same result as brute force. */
function gridNearestUnsettled(s: SwarmState, frm: number, exclude: Set<number>): number | null {
  const g = s.grid;
  const dim = g.dim, cs = g.cellSize;
  const fx = s.xs[frm], fy = s.ys[frm], fz = s.zs[frm];
  const qx = Math.min(dim - 1, Math.max(0, Math.floor(fx / cs)));
  const qy = Math.min(dim - 1, Math.max(0, Math.floor(fy / cs)));
  const qz = Math.min(dim - 1, Math.max(0, Math.floor(fz / cs)));
  let best: number | null = null;
  let bestD2 = Infinity;
  const consider = (i: number) => {
    if (s.settledYear[i] >= 0 || exclude.has(i)) return;
    const dx = s.xs[i] - fx, dy = s.ys[i] - fy, dz = s.zs[i] - fz;
    const d2 = dx * dx + dy * dy + dz * dz;
    // strict <, or equal-distance tie broken by lowest index — matches brute force.
    if (d2 < bestD2 || (d2 === bestD2 && (best === null || i < best))) {
      bestD2 = d2;
      best = i;
    }
  };
  for (let r = 0; r < dim; r++) {
    const lox = Math.max(0, qx - r), hix = Math.min(dim - 1, qx + r);
    const loy = Math.max(0, qy - r), hiy = Math.min(dim - 1, qy + r);
    const loz = Math.max(0, qz - r), hiz = Math.min(dim - 1, qz + r);
    for (let ix = lox; ix <= hix; ix++) {
      for (let iy = loy; iy <= hiy; iy++) {
        for (let iz = loz; iz <= hiz; iz++) {
          // shell only: skip cells strictly inside the r-1 cube (already examined).
          if (Math.max(Math.abs(ix - qx), Math.abs(iy - qy), Math.abs(iz - qz)) !== r) continue;
          for (const i of g.cells[(ix * dim + iy) * dim + iz]) consider(i);
        }
      }
    }
    // After finishing shell r, the closest possible star in shell r+1 is >= r*cs away.
    if (best !== null && r * cs >= Math.sqrt(bestD2)) break;
  }
  return best;
}

export interface SwarmStep {
  year: number;
  nSettled: number;
  fractionSettled: number;
  inFlight: number;
  frontRadiusPc: number;
}

export interface SwarmResult {
  nStars: number;
  finalSettled: number;
  totalProbesLaunched: number;
  t50Years: number | null;
  t90Years: number | null;
  t100Years: number | null;
  frontRadiusPc: number;
  maxProbeSpeedKmS: number;
  policy: Policy;
  steps: SwarmStep[];
  // final field, for the viz:
  xs: number[];
  ys: number[];
  zs: number[];
  settledYear: number[];
  origin: number;
  boxSidePc: number;
}

function generateGalaxy(p: SwarmParams, rng: number): { xs: number[]; ys: number[]; zs: number[]; starSpeed: number[]; rng: number } {
  const L = boxSidePc(p);
  const xs: number[] = [], ys: number[] = [], zs: number[] = [];
  for (let i = 0; i < p.nStars; i++) {
    let x: number, y: number, z: number;
    [x, rng] = nextFloat(rng);
    [y, rng] = nextFloat(rng);
    [z, rng] = nextFloat(rng);
    xs.push(x * L);
    ys.push(y * L);
    zs.push(z * L);
  }
  // Second pass: star speeds (magnitudes, pc/yr). Drawn AFTER all positions so the
  // position stream — and hence the powered policy — is bit-identical to before.
  const base = p.starSpeedKmS * KM_S_TO_PC_YR;
  const disp = p.starSpeedDispersionKmS * KM_S_TO_PC_YR;
  const starSpeed: number[] = [];
  for (let i = 0; i < p.nStars; i++) {
    let u: number;
    [u, rng] = nextFloat(rng);
    starSpeed.push(Math.max(0, base + disp * (2 * u - 1)));
  }
  return { xs, ys, zs, starSpeed, rng };
}

function dist(s: SwarmState, a: number, b: number): number {
  const dx = s.xs[a] - s.xs[b], dy = s.ys[a] - s.ys[b], dz = s.zs[a] - s.zs[b];
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

// Production path: the grid-accelerated search (identical result to brute force).
const nearestUnsettled = gridNearestUnsettled;

// Exported so the tests can prove grid ≡ brute across many queries.
export { bruteNearestUnsettled, gridNearestUnsettled };

/** The k nearest unsettled stars to `frm`, ordered by (distance, index) — brute force,
 *  matching the Python (used only by the max-boost policy). */
function nearestKUnsettled(s: SwarmState, frm: number, exclude: Set<number>, k: number): number[] {
  const fx = s.xs[frm], fy = s.ys[frm], fz = s.zs[frm];
  const cands: [number, number][] = [];
  for (let i = 0; i < s.xs.length; i++) {
    if (s.settledYear[i] >= 0 || exclude.has(i)) continue;
    const dx = s.xs[i] - fx, dy = s.ys[i] - fy, dz = s.zs[i] - fz;
    cands.push([dx * dx + dy * dy + dz * dz, i]);
  }
  cands.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return cands.slice(0, k).map(([, i]) => i);
}

/** Next star per policy (mirrors the Python `_select_target`). */
function selectTarget(s: SwarmState, frm: number, exclude: Set<number>, p: SwarmParams): number | null {
  if (p.policy === "slingshot_maxboost") {
    const cand = nearestKUnsettled(s, frm, exclude, p.maxBoostCandidates);
    if (cand.length === 0) return null;
    let best = cand[0];
    for (const i of cand) if (s.starSpeedPcYr[i] > s.starSpeedPcYr[best]) best = i;
    return best;
  }
  return nearestUnsettled(s, frm, exclude);
}

/** Galactic-frame speed after a slingshot (N&F Eq. 4; mirrors the Python `_boosted_speed`). */
function boostedSpeed(currentPcYr: number, starSpeedPcYr: number, p: SwarmParams): number {
  if (p.policy === "powered") return probeSpeedPcPerYear(p);
  const uEsc = p.escapeVelocityKmS * KM_S_TO_PC_YR;
  const uI = currentPcYr + starSpeedPcYr; // boost-optimal head-on approximation [ESTIMATE]
  const dvMax = (uEsc * uEsc) / ((uEsc * uEsc) / (2 * uI) + uI);
  return Math.min(currentPcYr + dvMax, p.speedCapC * C_PC_PER_YEAR);
}

function launchFrom(s: SwarmState, star: number, p: SwarmParams, incomingSpeed: number): void {
  const departing = boostedSpeed(incomingSpeed, s.starSpeedPcYr[star], p);
  if (departing > s.maxSpeedPcYr) s.maxSpeedPcYr = departing;
  const chosen = new Set<number>();
  for (let k = 0; k < p.offspringPerSettlement; k++) {
    const target = selectTarget(s, star, chosen, p);
    if (target === null) break;
    chosen.add(target);
    const travel = dist(s, star, target) / departing;
    s.probes.push({ id: s.nextProbeId, target, arriveYear: s.year + p.settleTimeYears + travel, speedPcYr: departing });
    s.nextProbeId += 1;
    s.totalLaunched += 1;
  }
}

export function initialState(p: SwarmParams, seed: number): SwarmState {
  const { xs, ys, zs, starSpeed, rng } = generateGalaxy(p, seedState(seed));
  const n = xs.length;
  const L = boxSidePc(p);
  const c = L / 2;
  let origin = 0, bestD2 = Infinity;
  for (let i = 0; i < n; i++) {
    const d2 = (xs[i] - c) ** 2 + (ys[i] - c) ** 2 + (zs[i] - c) ** 2;
    if (d2 < bestD2) {
      bestD2 = d2;
      origin = i;
    }
  }
  const settledYear = new Array<number>(n).fill(-1);
  settledYear[origin] = 0;
  const grid = buildGrid(xs, ys, zs, L);
  const vMax = probeSpeedPcPerYear(p);
  const s: SwarmState = {
    rng, year: 0, xs, ys, zs, settledYear, origin, probes: [], nextProbeId: 0, totalLaunched: 0,
    grid, settledCount: 1, frontMaxPc: 0, starSpeedPcYr: starSpeed, maxSpeedPcYr: vMax,
  };
  removeFromGrid(s, origin); // the homeworld is settled; take it out of the candidate set
  launchFrom(s, origin, p, vMax); // seed probes leave at powered cruise, taking the homeworld's slingshot
  return s;
}

export function step(s: SwarmState, p: SwarmParams): SwarmState {
  s.year += p.dtYears;
  const arrivals = s.probes
    .filter((pr) => pr.arriveYear <= s.year)
    .sort((a, b) => a.arriveYear - b.arriveYear || a.id - b.id);
  if (arrivals.length === 0) return s;

  const arrivedIds = new Set(arrivals.map((pr) => pr.id));
  s.probes = s.probes.filter((pr) => !arrivedIds.has(pr.id));

  for (const pr of arrivals) {
    if (s.settledYear[pr.target] < 0) {
      s.settledYear[pr.target] = s.year;
      removeFromGrid(s, pr.target);
      s.settledCount += 1;
      const d = dist(s, pr.target, s.origin);
      if (d > s.frontMaxPc) s.frontMaxPc = d;
      launchFrom(s, pr.target, p, pr.speedPcYr); // slingshot off it; offspring inherit the boost
    } else {
      // Raced and lost: re-target (by policy), keeping this probe's current speed.
      const target = selectTarget(s, pr.target, new Set(), p);
      if (target !== null) {
        const travel = dist(s, pr.target, target) / pr.speedPcYr;
        s.probes.push({ id: pr.id, target, arriveYear: s.year + travel, speedPcYr: pr.speedPcYr });
      }
    }
  }
  return s;
}

function snapshot(s: SwarmState, nStars: number): SwarmStep {
  const n = s.settledCount;
  return { year: s.year, nSettled: n, fractionSettled: n / nStars, inFlight: s.probes.length, frontRadiusPc: s.frontMaxPc };
}

export function simulateSwarm(params: SwarmParams, seed = 0x9e3779b9): SwarmResult {
  const s = initialState(params, seed);
  const nStars = s.xs.length;
  const steps = [snapshot(s, nStars)];
  const thr: Record<number, number | null> = { 50: null, 90: null, 100: null };
  const recordThresholds = () => {
    const frac = (s.settledCount / nStars) * 100;
    for (const pct of [50, 90, 100]) if (thr[pct] === null && frac >= pct) thr[pct] = s.year;
  };
  recordThresholds();

  const nSteps = Math.round(params.maxYears / params.dtYears);
  for (let i = 0; i < nSteps; i++) {
    if (s.probes.length === 0) break;
    step(s, params);
    steps.push(snapshot(s, nStars));
    recordThresholds();
  }

  return {
    nStars,
    finalSettled: s.settledCount,
    totalProbesLaunched: s.totalLaunched,
    t50Years: thr[50],
    t90Years: thr[90],
    t100Years: thr[100],
    frontRadiusPc: s.frontMaxPc,
    maxProbeSpeedKmS: s.maxSpeedPcYr / KM_S_TO_PC_YR,
    policy: params.policy,
    steps,
    xs: s.xs,
    ys: s.ys,
    zs: s.zs,
    settledYear: s.settledYear,
    origin: s.origin,
    boxSidePc: boxSidePc(params),
  };
}
