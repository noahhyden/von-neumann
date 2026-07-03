/**
 * A faithful TypeScript port of closure-sim's pure math - models.py + closure.py
 * + replication.py, ported 1:1 so the live explainer runs the SAME model the
 * Python CLI does (verified against it in model.test.ts). Nothing here touches
 * pimas or the DOM: these are plain, deterministic functions of their inputs,
 * which is exactly what lets the reactive layer wrap them in signals/memos and
 * lets `speculate` predict hypotheticals exactly. Keep it pure.
 */

// Categories treated as "electronics" for the electronics-wall analysis.
export const ELECTRONICS_CATEGORIES: ReadonlySet<string> = new Set([
  "compute",
  "electronics",
  "semiconductor",
]);

export interface Subsystem {
  name: string;
  mass_kg: number;
  category: string;
  producible_locally: boolean;
  processes: string[];
  energy_to_produce_kwh_per_kg: number;
}

export interface ReplicationParams {
  seed_mass_kg: number;
  local_build_rate_kg_per_day: number;
  vitamin_resupply_mass_kg: number;
  resupply_cadence_days: number;
  available_power_kw: number;
  target_output_kg_per_day: number;
  duration_days: number;
  dt_days: number;
}

export interface Factory {
  name: string;
  subsystems: Subsystem[];
  replication: ReplicationParams | null;
}

// ── cheap aggregates (models.py @property) ─────────────────────────────────
export const isVitamin = (s: Subsystem): boolean => !s.producible_locally;
export const buildEnergyKwh = (s: Subsystem): number =>
  s.mass_kg * s.energy_to_produce_kwh_per_kg;

export const totalMassKg = (f: Factory): number =>
  f.subsystems.reduce((a, s) => a + s.mass_kg, 0);
export const localMassKg = (f: Factory): number =>
  f.subsystems.reduce((a, s) => (s.producible_locally ? a + s.mass_kg : a), 0);
export const vitaminMassKg = (f: Factory): number =>
  f.subsystems.reduce((a, s) => (isVitamin(s) ? a + s.mass_kg : a), 0);

export const resupplyRateKgPerDay = (r: ReplicationParams): number =>
  r.vitamin_resupply_mass_kg / r.resupply_cadence_days;
export const availablePowerKwhPerDay = (r: ReplicationParams): number =>
  r.available_power_kw * 24.0;

// ── closure.py ─────────────────────────────────────────────────────────────
export interface VitaminEntry {
  name: string;
  category: string;
  mass_kg: number;
  mass_share: number;
  processes: string[];
}

export interface ClosureReport {
  factory_name: string;
  total_mass_kg: number;
  local_mass_kg: number;
  vitamin_mass_kg: number;
  closure_ratio: number;
  total_build_energy_kwh: number;
  local_build_energy_kwh: number;
  vitamins: VitaminEntry[];
}

export function computeClosure(factory: Factory): ClosureReport {
  const total = totalMassKg(factory);
  const local = localMassKg(factory);

  const vitamins: VitaminEntry[] = factory.subsystems
    .filter(isVitamin)
    .map((s) => ({
      name: s.name,
      category: s.category,
      mass_kg: s.mass_kg,
      mass_share: total > 0 ? s.mass_kg / total : 0.0,
      processes: [...s.processes],
    }));
  // Heaviest vitamins first - the order an engineer wants to read.
  vitamins.sort((a, b) => b.mass_kg - a.mass_kg);

  const totalEnergy = factory.subsystems.reduce((a, s) => a + buildEnergyKwh(s), 0);
  const localEnergy = factory.subsystems.reduce(
    (a, s) => (s.producible_locally ? a + buildEnergyKwh(s) : a),
    0,
  );

  return {
    factory_name: factory.name,
    total_mass_kg: total,
    local_mass_kg: local,
    vitamin_mass_kg: vitaminMassKg(factory),
    closure_ratio: total > 0 ? local / total : 0.0,
    total_build_energy_kwh: totalEnergy,
    local_build_energy_kwh: localEnergy,
    vitamins,
  };
}

// ── replication.py ───────────────────────────────────────────────────────
export type Regime = "material-limited" | "energy-limited" | "resupply-limited";
export const Regime = {
  MATERIAL: "material-limited" as Regime,
  ENERGY: "energy-limited" as Regime,
  RESUPPLY: "resupply-limited" as Regime,
};

export interface SimStep {
  day: number;
  factory_mass_kg: number;
  installed_capacity_kg_per_day: number;
  output_kg_per_day: number;
  growth_rate_kg_per_day: number;
  regime: Regime;
}

export interface RegimeSpan {
  regime: Regime;
  start_day: number;
  end_day: number;
}

export interface SimResult {
  factory_name: string;
  closure_ratio: number;
  productivity_per_day: number; // alpha
  energy_cap_kg_per_day: number;
  resupply_ceiling_kg_per_day: number;
  analytic_doubling_time_days: number | null;
  empirical_doubling_time_days: number | null;
  time_to_target_days: number | null;
  final_factory_mass_kg: number;
  final_output_kg_per_day: number;
  target_output_kg_per_day: number;
  regime_timeline: RegimeSpan[];
  steps: SimStep[];
}

function bindingRate(
  F: number,
  alpha: number,
  closure: number,
  energyCap: number,
  resupplyRate: number,
): [number, Regime] {
  const localProduction = Math.min(alpha * F, energyCap);

  // Vitamin (resupply) path.
  let resupplyPath: number;
  if (closure >= 1.0) resupplyPath = Infinity; // full closure: vitamins never bind
  else if (resupplyRate <= 0.0) resupplyPath = 0.0; // no vitamins arriving
  else resupplyPath = resupplyRate / (1.0 - closure);

  // Local-material path.
  const localPath = closure <= 0.0 ? Infinity : localProduction / closure;

  const rate = Math.min(localPath, resupplyPath);

  let regime: Regime;
  if (resupplyPath < localPath) regime = Regime.RESUPPLY;
  else if (alpha * F <= energyCap) regime = Regime.MATERIAL;
  else regime = Regime.ENERGY;
  return [rate, regime];
}

function compressTimeline(steps: SimStep[]): RegimeSpan[] {
  const spans: RegimeSpan[] = [];
  for (const s of steps) {
    const last = spans[spans.length - 1];
    if (last && last.regime === s.regime) last.end_day = s.day;
    else spans.push({ regime: s.regime, start_day: s.day, end_day: s.day });
  }
  return spans;
}

function interpolateCrossing(
  prevDay: number,
  prevVal: number,
  day: number,
  val: number,
  target: number,
): number {
  if (val === prevVal) return day;
  const frac = (target - prevVal) / (val - prevVal);
  return prevDay + frac * (day - prevDay);
}

/** Run the replication sim. `params` overrides `factory.replication`. */
export function simulate(factory: Factory, params?: ReplicationParams | null): SimResult {
  const rep = params ?? factory.replication;
  if (rep === null || rep === undefined) {
    throw new Error(`factory ${factory.name} has no replication params; pass params`);
  }

  const report = computeClosure(factory);
  const C = report.closure_ratio;
  const localMass = report.local_mass_kg;

  const alpha = rep.local_build_rate_kg_per_day / rep.seed_mass_kg;

  // Energy per kg of *locally produced* material (vitamins arrive pre-made).
  const eLocal = localMass > 0 ? report.local_build_energy_kwh / localMass : Infinity;
  const energyCap = eLocal > 0 ? availablePowerKwhPerDay(rep) / eLocal : Infinity;

  const resupplyRate = resupplyRateKgPerDay(rep);
  const resupplyCeiling = C >= 1.0 ? Infinity : resupplyRate / (1.0 - C);

  const analyticDoubling = C > 0 && alpha > 0 ? (Math.log(2) * C) / alpha : null;

  let F = rep.seed_mass_kg;
  const F0 = F;
  const target = rep.target_output_kg_per_day;

  const steps: SimStep[] = [];
  let timeToTarget: number | null = null;
  let empiricalDoubling: number | null = null;

  const nSteps = Math.ceil(rep.duration_days / rep.dt_days);
  let prevDay = 0.0;
  let prevOutput = Math.min(alpha * F, energyCap);
  let prevMass = F;

  for (let i = 0; i <= nSteps; i++) {
    const day = i * rep.dt_days;
    const [rate, regime] = bindingRate(F, alpha, C, energyCap, resupplyRate);
    const installed = alpha * F;
    const output = Math.min(installed, energyCap);

    steps.push({
      day,
      factory_mass_kg: F,
      installed_capacity_kg_per_day: installed,
      output_kg_per_day: output,
      growth_rate_kg_per_day: rate,
      regime,
    });

    if (timeToTarget === null && output >= target) {
      timeToTarget =
        i === 0 ? 0.0 : interpolateCrossing(prevDay, prevOutput, day, output, target);
    }
    if (empiricalDoubling === null && F >= 2 * F0) {
      empiricalDoubling =
        i === 0 ? 0.0 : interpolateCrossing(prevDay, prevMass, day, F, 2 * F0);
    }

    prevDay = day;
    prevOutput = output;
    prevMass = F;

    // Euler step (forward).
    F = F + rate * rep.dt_days;
  }

  return {
    factory_name: factory.name,
    closure_ratio: C,
    productivity_per_day: alpha,
    energy_cap_kg_per_day: energyCap,
    resupply_ceiling_kg_per_day: resupplyCeiling,
    analytic_doubling_time_days: analyticDoubling,
    empirical_doubling_time_days: empiricalDoubling,
    time_to_target_days: timeToTarget,
    final_factory_mass_kg: F,
    final_output_kg_per_day: Math.min(alpha * F, energyCap),
    target_output_kg_per_day: target,
    regime_timeline: compressTimeline(steps),
    steps,
  };
}

// ── analysis.py: the electronics wall ──────────────────────────────────────
export interface WallSide {
  closure_ratio: number;
  resupply_ceiling_kg_per_day: number;
  energy_cap_kg_per_day: number;
  empirical_doubling_time_days: number | null;
  time_to_target_days: number | null;
  final_output_kg_per_day: number;
}

export interface ElectronicsWallReport {
  factory_name: string;
  electronics_mass_kg: number;
  electronics_mass_share: number;
  before: WallSide;
  after: WallSide;
  time_to_target_delta_days: number | null;
  sim_before: SimResult;
  sim_after: SimResult;
}

const wallSide = (r: SimResult): WallSide => ({
  closure_ratio: r.closure_ratio,
  resupply_ceiling_kg_per_day: r.resupply_ceiling_kg_per_day,
  energy_cap_kg_per_day: r.energy_cap_kg_per_day,
  empirical_doubling_time_days: r.empirical_doubling_time_days,
  time_to_target_days: r.time_to_target_days,
  final_output_kg_per_day: r.final_output_kg_per_day,
});

/** Toggle a factory's electronics subsystems to locally producible. Pure. */
export function makeElectronicsLocal(
  factory: Factory,
  categories: ReadonlySet<string> = ELECTRONICS_CATEGORIES,
): Factory {
  return {
    ...factory,
    subsystems: factory.subsystems.map((s) =>
      categories.has(s.category) ? { ...s, producible_locally: true } : { ...s },
    ),
  };
}

/** Compare replication with electronics as vitamins vs produced locally. */
export function electronicsWall(
  factory: Factory,
  params?: ReplicationParams | null,
  categories: ReadonlySet<string> = ELECTRONICS_CATEGORIES,
): ElectronicsWallReport {
  const rep = params ?? factory.replication;
  if (!rep) throw new Error(`factory ${factory.name} has no replication params`);

  const beforeResult = simulate(factory, rep);
  const toggled = makeElectronicsLocal(factory, categories);
  const afterResult = simulate(toggled, rep);

  let elecMass = 0.0;
  for (const s of factory.subsystems) if (categories.has(s.category)) elecMass += s.mass_kg;

  const before = wallSide(beforeResult);
  const after = wallSide(afterResult);
  const delta =
    before.time_to_target_days !== null && after.time_to_target_days !== null
      ? before.time_to_target_days - after.time_to_target_days
      : null;

  const total = totalMassKg(factory);
  return {
    factory_name: factory.name,
    electronics_mass_kg: elecMass,
    electronics_mass_share: total ? elecMass / total : 0.0,
    before,
    after,
    time_to_target_delta_days: delta,
    sim_before: beforeResult,
    sim_after: afterResult,
  };
}
