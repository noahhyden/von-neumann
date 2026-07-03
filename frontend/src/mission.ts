/**
 * TS port of the `mission` module - the end-to-end probe operation as one pure fold.
 *
 * It writes no new physics: it *composes* the four existing ports (model.ts,
 * probe-sim.ts, power-budget.ts, launch-economics.ts) exactly as the Python
 * `mission.run_mission` composes the four sibling packages. Parity-tested against the
 * Python ground truth in `mission.test.ts` (Layer A - no pimas). Sources live in
 * ../../mission/REFERENCES.md (which points at each sibling's REFERENCES.md).
 *
 * The six stages: launch → closure → arrive (solar power at distance) → split power →
 * replicate (manufacturing share) → think (compute share) → price the payoff.
 */
// NOTE: sibling ports imported with explicit `.ts` so this composed port loads under
// `node --test` (Layer A), which - unlike esbuild - does not rewrite .js→.ts. esbuild
// resolves .ts fine, so the build is unaffected.
import { computeClosure, simulate } from "./model.ts";
import type { Factory } from "./model.ts";
import { comparisonFromClosure, exhaustVelocityMs, propellantFraction } from "./launch-economics.ts";
import { allocate, computeCapacityFlops, brainEquivalents } from "./power-budget.ts";
import { solarArrayPowerW, solarIrradianceWM2, SOLAR_CONSTANT_1AU_W_M2 } from "./probe-sim.ts";

// --- Sourced defaults / flagged scenario choices (see ../../mission/REFERENCES.md) ---
// Array efficiency: [ESTIMATE] 0.30 (probe-sim). Area sized to deliver the closure
// scenario's ~4 MW at 1 AU: 4e6 / (1360.8 * 0.30) ≈ 9798 m^2.
export const DEFAULT_ARRAY_EFFICIENCY = 0.3;
export const DEFAULT_ARRAY_POWER_AT_1AU_W = 4_000_000;
export const DEFAULT_ARRAY_AREA_M2 = Math.round(
  DEFAULT_ARRAY_POWER_AT_1AU_W / (SOLAR_CONSTANT_1AU_W_M2 * DEFAULT_ARRAY_EFFICIENCY),
);
// Compute hardware efficiency: [ESTIMATE] 1e11 FLOPS/W (~100 GFLOP/W, power-budget).
export const DEFAULT_COMPUTE_EFFICIENCY_FLOPS_PER_W = 1e11;
// Launch scalars (launch-economics): Δv surface→LEO ~9400 m/s, Isp 311 s (RP-1),
// $3000/kg (Falcon 9 reusable). Target installed mass: a scenario design choice.
export const DEFAULT_DELTA_V_M_S = 9400;
export const DEFAULT_SPECIFIC_IMPULSE_S = 311;
export const DEFAULT_COST_PER_KG_USD = 3000;
export const DEFAULT_TARGET_INSTALLED_MASS_KG = 1_000_000;
// Power split (design choice, fractions of delivered power).
export const DEFAULT_FRACTION_MANUFACTURING = 0.7;
export const DEFAULT_FRACTION_COMPUTE = 0.2;
export const DEFAULT_FRACTION_HOUSEKEEPING = 0.1;

export interface MissionScenario {
  factory: Factory;
  distanceAu: number;
  arrayAreaM2: number;
  arrayEfficiency: number;
  fractionManufacturing: number;
  fractionCompute: number;
  fractionHousekeeping: number;
  computeEfficiencyFlopsPerW: number;
  deltaVMs: number;
  specificImpulseS: number;
  costPerKgUsd: number;
  targetInstalledMassKg: number;
}

/** A mission scenario over the given factory, with sourced defaults; override any field. */
export function defaultMissionScenario(
  factory: Factory,
  overrides: Partial<MissionScenario> = {},
): MissionScenario {
  return {
    factory,
    distanceAu: 1.0,
    arrayAreaM2: DEFAULT_ARRAY_AREA_M2,
    arrayEfficiency: DEFAULT_ARRAY_EFFICIENCY,
    fractionManufacturing: DEFAULT_FRACTION_MANUFACTURING,
    fractionCompute: DEFAULT_FRACTION_COMPUTE,
    fractionHousekeeping: DEFAULT_FRACTION_HOUSEKEEPING,
    computeEfficiencyFlopsPerW: DEFAULT_COMPUTE_EFFICIENCY_FLOPS_PER_W,
    deltaVMs: DEFAULT_DELTA_V_M_S,
    specificImpulseS: DEFAULT_SPECIFIC_IMPULSE_S,
    costPerKgUsd: DEFAULT_COST_PER_KG_USD,
    targetInstalledMassKg: DEFAULT_TARGET_INSTALLED_MASS_KG,
    ...overrides,
  };
}

export interface MissionResult {
  closureRatio: number;

  seedMassKg: number;
  targetInstalledMassKg: number;
  vitaminMassKg: number;
  launchedMassKg: number;
  massLeverage: number;
  directLaunchCostUsd: number;
  replicationLaunchCostUsd: number;
  costSavingsUsd: number;
  costRatio: number;
  propellantFraction: number;
  deltaVMs: number;
  specificImpulseS: number;

  distanceAu: number;
  irradianceWM2: number;
  deliveredPowerW: number;

  manufacturingW: number;
  computeW: number;
  housekeepingW: number;

  computeFlops: number;
  brainEquivalents: number;

  reachesTarget: boolean;
  timeToTargetDays: number | null;
  finalOutputKgPerDay: number;
  doublingTimeDays: number | null;
  bindingRegime: string | null;
}

/** Run the whole chain once - the pure fold the follow-along surface renders. */
export function runMission(s: MissionScenario): MissionResult {
  const rep = s.factory.replication;
  if (!rep) throw new RangeError("mission factory needs replication params");
  const seedMassKg = rep.seed_mass_kg;

  // 1. CLOSURE
  const closureRatio = computeClosure(s.factory).closure_ratio;

  // 0 / 6. LAUNCH + PAYOFF - vitamins from closure; seed from the factory itself.
  const comparison = comparisonFromClosure({
    closureRatio,
    targetInstalledMassKg: s.targetInstalledMassKg,
    seedMassKg,
    costPerKgUsd: s.costPerKgUsd,
  });
  const propFrac = propellantFraction(s.deltaVMs, exhaustVelocityMs(s.specificImpulseS));

  // 2. ARRIVE - inverse-square solar power at the heliocentric distance.
  const array = { areaM2: s.arrayAreaM2, efficiency: s.arrayEfficiency };
  const deliveredPowerW = solarArrayPowerW(array, s.distanceAu);
  const irradianceWM2 = solarIrradianceWM2(s.distanceAu);

  // 3. SPLIT - one split, routed to the two consumers below.
  const budget = allocate({
    totalW: deliveredPowerW,
    fractionManufacturing: s.fractionManufacturing,
    fractionCompute: s.fractionCompute,
    fractionHousekeeping: s.fractionHousekeeping,
  });

  // 5. THINK - the compute the compute-share buys.
  const computeFlops = computeCapacityFlops(budget.computeW, s.computeEfficiencyFlopsPerW);

  // 4. REPLICATE - feed the manufacturing share (kW) into the replication sim. No
  // manufacturing power → the factory can't build; report a stall rather than
  // simulating at zero power (ReplicationParams requires available_power_kw > 0).
  const manufacturingKw = budget.manufacturingW / 1000;
  let reachesTarget = false;
  let timeToTargetDays: number | null = null;
  let finalOutputKgPerDay = 0;
  let doublingTimeDays: number | null = null;
  let bindingRegime: string | null = null;
  if (manufacturingKw > 0) {
    const sim = simulate(s.factory, { ...rep, available_power_kw: manufacturingKw });
    reachesTarget = sim.time_to_target_days !== null;
    timeToTargetDays = sim.time_to_target_days;
    finalOutputKgPerDay = sim.final_output_kg_per_day;
    doublingTimeDays = sim.empirical_doubling_time_days;
    bindingRegime = sim.regime_timeline.length ? sim.regime_timeline[sim.regime_timeline.length - 1].regime : null;
  }

  return {
    closureRatio,
    seedMassKg,
    targetInstalledMassKg: s.targetInstalledMassKg,
    vitaminMassKg: comparison.launchedMassKg - seedMassKg,
    launchedMassKg: comparison.launchedMassKg,
    massLeverage: comparison.massLeverage,
    directLaunchCostUsd: comparison.directLaunchCostUsd,
    replicationLaunchCostUsd: comparison.replicationLaunchCostUsd,
    costSavingsUsd: comparison.costSavingsUsd,
    costRatio: comparison.costRatio,
    propellantFraction: propFrac,
    deltaVMs: s.deltaVMs,
    specificImpulseS: s.specificImpulseS,
    distanceAu: s.distanceAu,
    irradianceWM2,
    deliveredPowerW,
    manufacturingW: budget.manufacturingW,
    computeW: budget.computeW,
    housekeepingW: budget.housekeepingW,
    computeFlops,
    brainEquivalents: brainEquivalents(computeFlops),
    reachesTarget,
    timeToTargetDays,
    finalOutputKgPerDay,
    doublingTimeDays,
    bindingRegime,
  };
}
