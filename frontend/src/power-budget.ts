/**
 * TS port of the `power-budget` module - pure math, no pimas.
 *
 * The model a frontend surface will render: split a power budget among making and
 * thinking, convert compute-watts to throughput, floored by the Landauer limit and
 * anchored to the ~20 W brain. Parity-tested against the Python in
 * `power-budget.test.ts` (Layer A). Sources: ../../power-budget/REFERENCES.md.
 */

// Boltzmann constant, J/K - exact by the 2019 SI redefinition.
export const BOLTZMANN_J_PER_K = 1.380649e-23;
// Resting human brain power, W (Raichle & Gusnard 2002).
export const HUMAN_BRAIN_POWER_W = 20.0;
// [ESTIMATE] brain-equivalent compute, FLOPS (Sandberg & Bostrom 2008; ~±2 orders).
export const BRAIN_COMPUTE_FLOPS_ESTIMATE = 1e18;

export function landauerLimitJPerBit(temperatureK = 300): number {
  if (temperatureK <= 0) throw new RangeError("temperatureK must be positive");
  return BOLTZMANN_J_PER_K * temperatureK * Math.LN2;
}

export function maxBitOperationsPerJoule(temperatureK = 300): number {
  return 1 / landauerLimitJPerBit(temperatureK);
}

export function brainEquivalents(flops: number, brainFlops = BRAIN_COMPUTE_FLOPS_ESTIMATE): number {
  if (brainFlops <= 0) throw new RangeError("brainFlops must be positive");
  return flops / brainFlops;
}

export function computeCapacityFlops(powerW: number, efficiencyFlopsPerW: number): number {
  if (powerW < 0) throw new RangeError("powerW must be non-negative");
  if (efficiencyFlopsPerW <= 0) throw new RangeError("efficiencyFlopsPerW must be positive");
  return powerW * efficiencyFlopsPerW;
}

export interface PowerAllocation {
  totalW: number;
  fractionManufacturing?: number;
  fractionCompute?: number;
  fractionHousekeeping?: number;
}

export interface AllocatedBudget {
  manufacturingW: number;
  computeW: number;
  housekeepingW: number;
  unallocatedW: number;
}

export function allocate(a: PowerAllocation): AllocatedBudget {
  if (a.totalW <= 0) throw new RangeError("totalW must be positive");
  const fm = a.fractionManufacturing ?? 0;
  const fc = a.fractionCompute ?? 0;
  const fh = a.fractionHousekeeping ?? 0;
  for (const f of [fm, fc, fh]) if (f < 0 || f > 1) throw new RangeError("fractions must be in [0, 1]");
  const sum = fm + fc + fh;
  if (sum > 1 + 1e-9) throw new RangeError("power fractions sum > 1 (over-allocated)");
  return {
    manufacturingW: a.totalW * fm,
    computeW: a.totalW * fc,
    housekeepingW: a.totalW * fh,
    unallocatedW: a.totalW * (1 - sum),
  };
}
