/**
 * TS port of the `launch-economics` module — pure math, no pimas.
 *
 * This is the model a frontend surface will render (drag closure -> watch launch-mass
 * leverage and mission cost). It is a faithful port of the Python package and is
 * parity-tested against it in `launch-economics.test.ts` (Layer A — no pimas). SI
 * units: m/s, kg, seconds, USD. Sources live in ../../launch-economics/REFERENCES.md.
 */

// Standard gravity, m/s^2 — defined constant (BIPM/SI).
export const G0_M_S2 = 9.80665;

export function exhaustVelocityMs(specificImpulseS: number): number {
  if (specificImpulseS <= 0) throw new RangeError("specificImpulseS must be positive");
  return specificImpulseS * G0_M_S2;
}

/** Tsiolkovsky mass ratio m0/mf = exp(Δv / v_e). */
export function rocketEquationMassRatio(deltaVMs: number, exhaustVelocityMs: number): number {
  if (deltaVMs < 0) throw new RangeError("deltaVMs must be non-negative");
  if (exhaustVelocityMs <= 0) throw new RangeError("exhaustVelocityMs must be positive");
  return Math.exp(deltaVMs / exhaustVelocityMs);
}

export function propellantFraction(deltaVMs: number, exhaustVelocityMs: number): number {
  return 1 - 1 / rocketEquationMassRatio(deltaVMs, exhaustVelocityMs);
}

export function launchCostUsd(massKg: number, costPerKgUsd: number): number {
  if (massKg < 0) throw new RangeError("massKg must be non-negative");
  if (costPerKgUsd < 0) throw new RangeError("costPerKgUsd must be non-negative");
  return massKg * costPerKgUsd;
}

export interface ReplicationLaunchInput {
  targetInstalledMassKg: number;
  seedMassKg: number;
  vitaminMassTotalKg: number;
  costPerKgUsd: number;
}

export interface ReplicationLaunchComparison {
  launchedMassKg: number;
  directLaunchCostUsd: number;
  replicationLaunchCostUsd: number;
  massLeverage: number; // installed kg per launched kg
  costRatio: number; // replication cost / direct cost
  costSavingsUsd: number;
}

export function replicationLaunchComparison(input: ReplicationLaunchInput): ReplicationLaunchComparison {
  const { targetInstalledMassKg, seedMassKg, vitaminMassTotalKg, costPerKgUsd } = input;
  if (targetInstalledMassKg <= 0) throw new RangeError("targetInstalledMassKg must be positive");
  if (seedMassKg <= 0) throw new RangeError("seedMassKg must be positive");
  if (vitaminMassTotalKg < 0) throw new RangeError("vitaminMassTotalKg must be non-negative");
  if (costPerKgUsd <= 0) throw new RangeError("costPerKgUsd must be positive");

  const launchedMassKg = seedMassKg + vitaminMassTotalKg;
  const directLaunchCostUsd = targetInstalledMassKg * costPerKgUsd;
  const replicationLaunchCostUsd = launchedMassKg * costPerKgUsd;
  return {
    launchedMassKg,
    directLaunchCostUsd,
    replicationLaunchCostUsd,
    massLeverage: targetInstalledMassKg / launchedMassKg,
    costRatio: replicationLaunchCostUsd / directLaunchCostUsd,
    costSavingsUsd: directLaunchCostUsd - replicationLaunchCostUsd,
  };
}

/** Imported vitamin mass to locally build `builtMassKg` at a given closure: (1 - C) per kg. */
export function vitaminMassForBuild(closureRatio: number, builtMassKg: number): number {
  if (closureRatio < 0 || closureRatio > 1) throw new RangeError("closureRatio must be in [0, 1]");
  if (builtMassKg < 0) throw new RangeError("builtMassKg must be non-negative");
  return (1 - closureRatio) * builtMassKg;
}

export interface FromClosureInput {
  closureRatio: number;
  targetInstalledMassKg: number;
  seedMassKg: number;
  costPerKgUsd: number;
}

/** Launch comparison whose vitamin mass is derived from a factory's closure ratio. */
export function comparisonFromClosure(input: FromClosureInput): ReplicationLaunchComparison {
  const builtMassKg = Math.max(0, input.targetInstalledMassKg - input.seedMassKg);
  const vitaminMassTotalKg = vitaminMassForBuild(input.closureRatio, builtMassKg);
  return replicationLaunchComparison({
    targetInstalledMassKg: input.targetInstalledMassKg,
    seedMassKg: input.seedMassKg,
    vitaminMassTotalKg,
    costPerKgUsd: input.costPerKgUsd,
  });
}
