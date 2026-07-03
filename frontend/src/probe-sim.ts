/**
 * TS port of `probe-sim` (environment + autonomy) - pure math, no pimas.
 *
 * The factory-free part of the probe model: solar power vs heliocentric distance,
 * and the compute headroom that power buys (reusing the power-budget port). The
 * operational-range piece needs a real probe factory (an open [GAP] in probe-sim),
 * so it's deferred. Parity-tested against the Python in `probe-sim.test.ts` (Layer
 * A). Sources: ../../probe-sim/REFERENCES.md.
 *
 * Self-contained (like the other ports) so it runs under `node --test`: the two
 * compute helpers mirror the power-budget port - throughput = power × efficiency,
 * brain-equivalents against a ~1e18-FLOPS scale ([ESTIMATE], Sandberg & Bostrom 2008).
 */

// [ESTIMATE] brain-equivalent compute, FLOPS - mirrors the power-budget module.
const BRAIN_COMPUTE_FLOPS_ESTIMATE = 1e18;

// Total Solar Irradiance at 1 AU, W/m^2 (Kopp & Lean 2011).
export const SOLAR_CONSTANT_1AU_W_M2 = 1360.8;
// Fraction of probe mass it can build for itself (Borgue & Hein 2020).
export const REPLICATED_MASS_FRACTION = 0.7;
// Mean heliocentric distances, AU (NASA planetary fact sheet).
export const AU_DISTANCE = { earth: 1.0, mars: 1.524, jupiter: 5.203 } as const;

export function solarIrradianceWM2(distanceAu: number, solarConstant = SOLAR_CONSTANT_1AU_W_M2): number {
  if (distanceAu <= 0) throw new RangeError("distanceAu must be positive");
  return solarConstant / (distanceAu * distanceAu);
}

export interface SolarArray {
  areaM2: number;
  efficiency: number;
}

function validateArray(a: SolarArray): void {
  if (a.areaM2 <= 0) throw new RangeError("areaM2 must be positive");
  if (a.efficiency <= 0 || a.efficiency > 1) throw new RangeError("efficiency must be in (0, 1]");
}

export function solarArrayPowerW(array: SolarArray, distanceAu: number): number {
  validateArray(array);
  return solarIrradianceWM2(distanceAu) * array.areaM2 * array.efficiency;
}

export function maxDistanceAu(array: SolarArray, requiredPowerW: number): number {
  validateArray(array);
  if (requiredPowerW <= 0) throw new RangeError("requiredPowerW must be positive");
  return Math.sqrt((SOLAR_CONSTANT_1AU_W_M2 * array.areaM2 * array.efficiency) / requiredPowerW);
}

export interface ComputeHeadroom {
  distanceAu: number;
  deliveredPowerW: number;
  computePowerW: number;
  computeFlops: number;
  brainEquivalents: number;
}

export interface AutonomyOpts {
  computeFraction: number;
  efficiencyFlopsPerW: number;
}

export function computeHeadroomAt(array: SolarArray, distanceAu: number, opts: AutonomyOpts): ComputeHeadroom {
  if (opts.efficiencyFlopsPerW <= 0) throw new RangeError("efficiencyFlopsPerW must be positive");
  const deliveredPowerW = solarArrayPowerW(array, distanceAu);
  const computePowerW = deliveredPowerW * opts.computeFraction;
  const computeFlops = computePowerW * opts.efficiencyFlopsPerW;
  return { distanceAu, deliveredPowerW, computePowerW, computeFlops, brainEquivalents: computeFlops / BRAIN_COMPUTE_FLOPS_ESTIMATE };
}

export function maxDistanceForCompute(array: SolarArray, requiredFlops: number, opts: AutonomyOpts): number {
  if (requiredFlops <= 0) throw new RangeError("requiredFlops must be positive");
  if (!(opts.computeFraction > 0 && opts.computeFraction <= 1)) throw new RangeError("computeFraction must be in (0, 1]");
  if (opts.efficiencyFlopsPerW <= 0) throw new RangeError("efficiencyFlopsPerW must be positive");
  const requiredTotalW = requiredFlops / opts.efficiencyFlopsPerW / opts.computeFraction;
  return maxDistanceAu(array, requiredTotalW);
}
