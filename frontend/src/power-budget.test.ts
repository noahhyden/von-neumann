/**
 * Parity test: the TS port must reproduce the Python power-budget exactly.
 * Ground-truth mirrors power-budget/tests/*. Pure - no pimas (Layer A).
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  BOLTZMANN_J_PER_K,
  BRAIN_COMPUTE_FLOPS_ESTIMATE,
  HUMAN_BRAIN_POWER_W,
  allocate,
  brainEquivalents,
  computeCapacityFlops,
  landauerLimitJPerBit,
  maxBitOperationsPerJoule,
} from "./power-budget.ts";

const near = (a: number, b: number, relEps = 1e-3) =>
  assert.ok(Math.abs(a - b) <= Math.abs(b) * relEps, `expected ~${b}, got ${a}`);

test("Landauer limit matches Python", () => {
  near(landauerLimitJPerBit(300), 2.871e-21);
  // derived, not hardcoded
  assert.equal(landauerLimitJPerBit(77), BOLTZMANN_J_PER_K * 77 * Math.LN2);
  // linear in temperature
  near(landauerLimitJPerBit(600), 2 * landauerLimitJPerBit(300), 1e-9);
});

test("max bit-ops per joule is the inverse of Landauer", () => {
  near(maxBitOperationsPerJoule(300), 1 / landauerLimitJPerBit(300), 1e-9);
  near(maxBitOperationsPerJoule(300), 3.48e20, 1e-2);
});

test("brain scale and equivalents match Python", () => {
  assert.equal(HUMAN_BRAIN_POWER_W, 20);
  near(brainEquivalents(BRAIN_COMPUTE_FLOPS_ESTIMATE), 1, 1e-12);
  near(brainEquivalents(5 * BRAIN_COMPUTE_FLOPS_ESTIMATE), 5, 1e-12);
});

test("compute capacity is linear in power and efficiency", () => {
  near(computeCapacityFlops(250, 1e11), 2.5e13, 1e-9);
  near(computeCapacityFlops(500, 1e11), 2 * computeCapacityFlops(250, 1e11), 1e-9);
});

test("allocation splits and conserves the total", () => {
  const b = allocate({ totalW: 1000, fractionManufacturing: 0.6, fractionCompute: 0.25, fractionHousekeeping: 0.1 });
  near(b.manufacturingW, 600, 1e-9);
  near(b.computeW, 250, 1e-9);
  near(b.housekeepingW, 100, 1e-9);
  near(b.unallocatedW, 50, 1e-9);
  const parts = b.manufacturingW + b.computeW + b.housekeepingW + b.unallocatedW;
  near(parts, 1000, 1e-9);
});

test("invalid inputs throw", () => {
  assert.throws(() => landauerLimitJPerBit(0));
  assert.throws(() => computeCapacityFlops(100, 0));
  assert.throws(() => allocate({ totalW: 0 }));
  assert.throws(() => allocate({ totalW: 1000, fractionManufacturing: 0.7, fractionCompute: 0.5 }));
});
