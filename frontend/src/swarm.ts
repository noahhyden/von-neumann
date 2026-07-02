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
}

export const SWARM_DEFAULTS: SwarmParams = {
  nStars: 500,
  densityStarsPerPc3: 0.14,
  probeSpeedC: 0.1,
  offspringPerSettlement: 2,
  settleTimeYears: 0,
  dtYears: 25,
  maxYears: 2_000_000,
};

export const boxSidePc = (p: SwarmParams): number => Math.pow(p.nStars / p.densityStarsPerPc3, 1 / 3);
export const probeSpeedPcPerYear = (p: SwarmParams): number => p.probeSpeedC * C_PC_PER_YEAR;

interface Probe {
  id: number;
  target: number;
  arriveYear: number;
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
  steps: SwarmStep[];
  // final field, for the viz:
  xs: number[];
  ys: number[];
  zs: number[];
  settledYear: number[];
  origin: number;
  boxSidePc: number;
}

function generateGalaxy(p: SwarmParams, rng: number): { xs: number[]; ys: number[]; zs: number[]; rng: number } {
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
  return { xs, ys, zs, rng };
}

function dist(s: SwarmState, a: number, b: number): number {
  const dx = s.xs[a] - s.xs[b], dy = s.ys[a] - s.ys[b], dz = s.zs[a] - s.zs[b];
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

function nearestUnsettled(s: SwarmState, frm: number, exclude: Set<number>): number | null {
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

function launchFrom(s: SwarmState, star: number, p: SwarmParams): void {
  const speed = probeSpeedPcPerYear(p);
  const chosen = new Set<number>();
  for (let k = 0; k < p.offspringPerSettlement; k++) {
    const target = nearestUnsettled(s, star, chosen);
    if (target === null) break;
    chosen.add(target);
    const travel = dist(s, star, target) / speed;
    s.probes.push({ id: s.nextProbeId, target, arriveYear: s.year + p.settleTimeYears + travel });
    s.nextProbeId += 1;
    s.totalLaunched += 1;
  }
}

export function initialState(p: SwarmParams, seed: number): SwarmState {
  const { xs, ys, zs, rng } = generateGalaxy(p, seedState(seed));
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
  const s: SwarmState = { rng, year: 0, xs, ys, zs, settledYear, origin, probes: [], nextProbeId: 0, totalLaunched: 0 };
  launchFrom(s, origin, p);
  return s;
}

export function step(s: SwarmState, p: SwarmParams): SwarmState {
  s.year += p.dtYears;
  const arrivals = s.probes
    .filter((pr) => pr.arriveYear <= s.year)
    .sort((a, b) => a.arriveYear - b.arriveYear || a.id - b.id);
  if (arrivals.length === 0) return s;

  const arrivedIds = new Set(arrivals.map((pr) => pr.id));
  const speed = probeSpeedPcPerYear(p);
  s.probes = s.probes.filter((pr) => !arrivedIds.has(pr.id));

  for (const pr of arrivals) {
    if (s.settledYear[pr.target] < 0) {
      s.settledYear[pr.target] = s.year;
      launchFrom(s, pr.target, p);
    } else {
      const target = nearestUnsettled(s, pr.target, new Set());
      if (target !== null) {
        const travel = dist(s, pr.target, target) / speed;
        s.probes.push({ id: pr.id, target, arriveYear: s.year + travel });
      }
    }
  }
  return s;
}

function nSettled(s: SwarmState): number {
  let n = 0;
  for (const y of s.settledYear) if (y >= 0) n++;
  return n;
}

function frontRadius(s: SwarmState): number {
  let r = 0;
  for (let i = 0; i < s.xs.length; i++) {
    if (s.settledYear[i] >= 0) {
      const d = dist(s, i, s.origin);
      if (d > r) r = d;
    }
  }
  return r;
}

function snapshot(s: SwarmState, nStars: number): SwarmStep {
  const n = nSettled(s);
  return { year: s.year, nSettled: n, fractionSettled: n / nStars, inFlight: s.probes.length, frontRadiusPc: frontRadius(s) };
}

export function simulateSwarm(params: SwarmParams, seed = 0x9e3779b9): SwarmResult {
  const s = initialState(params, seed);
  const nStars = s.xs.length;
  const steps = [snapshot(s, nStars)];
  const thr: Record<number, number | null> = { 50: null, 90: null, 100: null };
  const recordThresholds = () => {
    const frac = (nSettled(s) / nStars) * 100;
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
    finalSettled: nSettled(s),
    totalProbesLaunched: s.totalLaunched,
    t50Years: thr[50],
    t90Years: thr[90],
    t100Years: thr[100],
    frontRadiusPc: frontRadius(s),
    steps,
    xs: s.xs,
    ys: s.ys,
    zs: s.zs,
    settledYear: s.settledYear,
    origin: s.origin,
    boxSidePc: boxSidePc(params),
  };
}
