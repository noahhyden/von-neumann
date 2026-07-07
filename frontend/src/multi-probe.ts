/**
 * TS port of the `multi-probe` module - a small, deterministic, seeded fleet fold.
 *
 * Faithful port of the Python package (`multi_probe.fleet`): each probe builds copies
 * at `min(machinery rate, energy cap)` - closure-sim's regime logic for a fixed-size
 * probe, reusing probe-sim's 1/d² power - and spawns children that disperse outward
 * and consume imported vitamins. Two ceilings emerge: a finite vitamin pool (the
 * electronics wall at fleet scale) and a spatial power wall (~13.6 AU crossover).
 *
 * Randomness (optional transit jitter) is a seeded mulberry32 generator threaded
 * through the state (CLAUDE.md §7) - byte-identical to the Python and to
 * scripts/gen-diff.mjs, so the fold replays bit-for-bit. Parity-tested against the
 * Python ground truth in `multi-probe.test.ts` (Layer A). Sibling ports imported with
 * `.ts` so this loads under `node --test` (see mission.ts for the why).
 */
import { computeClosure } from "./model.ts";
import type { Factory } from "./model.ts";
import { solarArrayPowerW } from "./probe-sim.ts";

// ── mulberry32, threaded (never ambient) - mirrors multi_probe/rng.py ──────────
export function nextFloat(state: number): [number, number] {
  const s = (state + 0x6d2b79f5) | 0;
  let t = Math.imul(s ^ (s >>> 15), 1 | s);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return [((t ^ (t >>> 14)) >>> 0) / 4294967296, s | 0];
}
export const seedState = (seed: number): number => seed | 0;

export const ProbeStatus = { TRAVELING: "traveling", ACTIVE: "active" } as const;
export type ProbeStatusT = (typeof ProbeStatus)[keyof typeof ProbeStatus];

export interface Probe {
  id: number;
  distanceAu: number;
  status: ProbeStatusT;
  arrivalDay: number;
  builtKg: number;
  children: number;
}

export interface FleetParams {
  seedMassKg: number;
  closureRatio: number;
  eLocalKwhPerKg: number;
  localBuildRateKgPerDay: number;
  arrayAreaM2: number;
  arrayEfficiency: number;
  manufacturingFraction: number;
  startDistanceAu: number;
  nSeedProbes: number;
  dispersalFactor: number;
  maxDistanceAu: number;
  transitDays: number;
  transitJitterFrac: number;
  vitaminPoolKg: number;
  maxProbes: number;
}

export interface FleetState {
  rng: number;
  day: number;
  probes: Probe[];
  vitaminPoolKg: number;
  nextId: number;
}

export interface FleetStep {
  day: number;
  population: number;
  active: number;
  totalBuiltKg: number;
  vitaminPoolKg: number;
  meanDistanceAu: number;
  maxDistanceAu: number;
}

export interface RegimeCount {
  vitaminLimited: boolean;
  powerLimited: boolean;
  capLimited: boolean;
}

export interface FleetResult {
  finalPopulation: number;
  finalActive: number;
  totalChildren: number;
  vitaminsConsumedKg: number;
  vitaminsRemainingKg: number;
  doublingTimeDays: number | null;
  binding: RegimeCount;
  meanDistanceAu: number;
  maxDistanceAu: number;
  steps: FleetStep[];
  finalProbes: Probe[]; // for the fleet scatter viz (not part of Python parity)
}

const DEFAULTS = {
  arrayAreaM2: 9798,
  arrayEfficiency: 0.3,
  manufacturingFraction: 0.7,
  startDistanceAu: 1.0,
  nSeedProbes: 1,
  dispersalFactor: 1.3,
  maxDistanceAu: 40.0,
  transitDays: 365.0,
  transitJitterFrac: 0.0,
  vitaminPoolKg: 1_000_000.0,
  maxProbes: 64,
};

/** Derive the sourced fields from a real BOM (closure-sim); override any by keyword. */
export function paramsFromFactory(factory: Factory, overrides: Partial<FleetParams> = {}): FleetParams {
  const rep = factory.replication;
  if (!rep) throw new RangeError("factory needs replication params");
  const report = computeClosure(factory);
  if (report.local_mass_kg <= 0) throw new RangeError("factory has no locally-producible mass");
  return {
    seedMassKg: rep.seed_mass_kg,
    closureRatio: report.closure_ratio,
    eLocalKwhPerKg: report.local_build_energy_kwh / report.local_mass_kg,
    localBuildRateKgPerDay: rep.local_build_rate_kg_per_day,
    ...DEFAULTS,
    ...overrides,
  };
}

/** Build rate at a distance = min(machinery throughput, energy cap). */
export function buildRateKgPerDay(params: FleetParams, distanceAu: number): number {
  const manufacturingW = solarArrayPowerW({ areaM2: params.arrayAreaM2, efficiency: params.arrayEfficiency }, distanceAu) * params.manufacturingFraction;
  const manufacturingKwhPerDay = (manufacturingW / 1000) * 24;
  const energyCap = manufacturingKwhPerDay / params.eLocalKwhPerKg;
  return Math.min(params.localBuildRateKgPerDay, energyCap);
}

/**
 * Days for one probe to build one copy's worth of local structure at a distance:
 * local_per_child / build_rate. The fleet's fundamental replication cadence, and (at
 * 1 AU) the swarm's per-star manufacturing dwell. Mirrors multi_probe.fleet.
 */
export function timeToBuildOneCopyDays(params: FleetParams, distanceAu: number): number {
  const localPerChild = params.closureRatio * params.seedMassKg;
  const rate = buildRateKgPerDay(params, distanceAu);
  return rate > 0 ? localPerChild / rate : Infinity;
}

export function initialState(params: FleetParams, seed: number): FleetState {
  const probes: Probe[] = [];
  for (let i = 0; i < params.nSeedProbes; i++) {
    probes.push({ id: i, distanceAu: params.startDistanceAu, status: ProbeStatus.ACTIVE, arrivalDay: 0, builtKg: 0, children: 0 });
  }
  return { rng: seedState(seed), day: 0, probes, vitaminPoolKg: params.vitaminPoolKg, nextId: params.nSeedProbes };
}

/** Advance the whole fleet by dt days. Pure - returns a new state, input untouched. */
export function step(state: FleetState, params: FleetParams, dt: number): FleetState {
  const localPerChild = params.closureRatio * params.seedMassKg;
  const vitaminsPerChild = (1 - params.closureRatio) * params.seedMassKg;
  const newDay = state.day + dt;

  let rng = state.rng;
  let pool = state.vitaminPoolKg;
  let nextId = state.nextId;
  let count = state.probes.length;

  const updated: Probe[] = [];
  const newborns: Probe[] = [];

  for (const p of state.probes) {
    if (p.status !== ProbeStatus.ACTIVE) {
      updated.push(p);
      continue;
    }
    let built = p.builtKg + buildRateKgPerDay(params, p.distanceAu) * dt;
    let children = p.children;
    while (built >= localPerChild && count < params.maxProbes && pool >= vitaminsPerChild) {
      built -= localPerChild;
      pool -= vitaminsPerChild;
      count += 1;
      children += 1;
      const childDistance = Math.min(p.distanceAu * params.dispersalFactor, params.maxDistanceAu);
      let transit = params.transitDays;
      if (params.transitJitterFrac > 0) {
        const [u, r] = nextFloat(rng);
        rng = r;
        transit = params.transitDays * (1 + params.transitJitterFrac * (2 * u - 1));
      }
      newborns.push({ id: nextId, distanceAu: childDistance, status: ProbeStatus.TRAVELING, arrivalDay: newDay + transit, builtKg: 0, children: 0 });
      nextId += 1;
    }
    updated.push({ id: p.id, distanceAu: p.distanceAu, status: p.status, arrivalDay: p.arrivalDay, builtKg: built, children });
  }

  const arrived = [...updated, ...newborns].map((p) =>
    p.status === ProbeStatus.TRAVELING && p.arrivalDay <= newDay
      ? { ...p, status: ProbeStatus.ACTIVE }
      : p,
  );

  return { rng, day: newDay, probes: arrived, vitaminPoolKg: pool, nextId };
}

function snapshot(state: FleetState): FleetStep {
  const dists = state.probes.map((p) => p.distanceAu);
  const active = state.probes.filter((p) => p.status === ProbeStatus.ACTIVE).length;
  return {
    day: state.day,
    population: state.probes.length,
    active,
    totalBuiltKg: state.probes.reduce((a, p) => a + p.builtKg, 0),
    vitaminPoolKg: state.vitaminPoolKg,
    meanDistanceAu: dists.length ? dists.reduce((a, d) => a + d, 0) / dists.length : 0,
    maxDistanceAu: dists.length ? Math.max(...dists) : 0,
  };
}

export interface SimulateOpts {
  seed?: number;
  durationDays?: number;
  dtDays?: number;
}

/** Fold step over time from a seed and summarize the run. */
export function simulateFleet(params: FleetParams, opts: SimulateOpts = {}): FleetResult {
  const seed = opts.seed ?? 0x9e3779b9;
  const durationDays = opts.durationDays ?? 3650;
  const dtDays = opts.dtDays ?? 1;
  if (dtDays <= 0) throw new RangeError("dtDays must be positive");

  let state = initialState(params, seed);
  const initialPop = state.probes.length;
  const steps = [snapshot(state)];
  let doublingTime: number | null = null;

  const n = Math.round(durationDays / dtDays);
  for (let i = 0; i < n; i++) {
    state = step(state, params, dtDays);
    const snap = snapshot(state);
    steps.push(snap);
    if (doublingTime === null && snap.population >= 2 * initialPop) doublingTime = snap.day;
  }

  const vitaminsPerChild = (1 - params.closureRatio) * params.seedMassKg;
  const localPerChild = params.closureRatio * params.seedMassKg;
  const dists = state.probes.map((p) => p.distanceAu);
  const activeProbes = state.probes.filter((p) => p.status === ProbeStatus.ACTIVE);

  return {
    finalPopulation: state.probes.length,
    finalActive: activeProbes.length,
    totalChildren: state.probes.reduce((a, p) => a + p.children, 0),
    vitaminsConsumedKg: params.vitaminPoolKg - state.vitaminPoolKg,
    vitaminsRemainingKg: state.vitaminPoolKg,
    doublingTimeDays: doublingTime,
    binding: {
      vitaminLimited: state.vitaminPoolKg < vitaminsPerChild,
      capLimited: state.probes.length >= params.maxProbes,
      powerLimited: activeProbes.some((p) => buildRateKgPerDay(params, p.distanceAu) * durationDays < localPerChild),
    },
    meanDistanceAu: dists.length ? dists.reduce((a, d) => a + d, 0) / dists.length : 0,
    maxDistanceAu: dists.length ? Math.max(...dists) : 0,
    steps,
    finalProbes: state.probes,
  };
}
