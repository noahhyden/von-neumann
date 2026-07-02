/**
 * Parity test: the TS port must reproduce the Python launch-economics exactly.
 * Ground-truth numbers mirror launch-economics/tests/*. Pure — no pimas (Layer A).
 * Run with `node --test` (Node strips the TS types natively).
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  G0_M_S2,
  comparisonFromClosure,
  exhaustVelocityMs,
  launchCostUsd,
  propellantFraction,
  replicationLaunchComparison,
  rocketEquationMassRatio,
  vitaminMassForBuild,
} from "./launch-economics.ts";

const near = (a: number, b: number, eps = 1e-6) =>
  assert.ok(Math.abs(a - b) < eps, `expected ~${b}, got ${a}`);

test("rocket equation matches Python", () => {
  near(exhaustVelocityMs(350), 350 * G0_M_S2);
  const ve = exhaustVelocityMs(350);
  near(rocketEquationMassRatio(9400, ve), Math.exp(9400 / ve));
  assert.ok(Math.abs(rocketEquationMassRatio(9400, ve) - 15.5) < 0.2);
  assert.ok(Math.abs(propellantFraction(9400, ve) - 0.935) < 0.01);
  near(propellantFraction(0, ve), 0);
});

test("launch cost is linear", () => {
  near(launchCostUsd(1000, 3000), 3_000_000);
  near(launchCostUsd(0, 3000), 0);
});

test("replication comparison matches Python make_case", () => {
  const c = replicationLaunchComparison({
    targetInstalledMassKg: 1_000_000,
    seedMassKg: 10_000,
    vitaminMassTotalKg: 3_000,
    costPerKgUsd: 3_000,
  });
  near(c.launchedMassKg, 13_000);
  near(c.directLaunchCostUsd, 1_000_000 * 3_000);
  near(c.replicationLaunchCostUsd, 13_000 * 3_000);
  assert.ok(Math.abs(c.massLeverage - 76.92307) < 1e-3);
  near(c.costRatio, 1 / c.massLeverage);
  near(c.costSavingsUsd, (1_000_000 - 13_000) * 3_000);
});

test("vitamin mass for build (mass balance) matches Python", () => {
  near(vitaminMassForBuild(1.0, 1000), 0);
  near(vitaminMassForBuild(0.0, 1000), 1000);
  near(vitaminMassForBuild(0.7, 1000), 300);
});

test("comparison from closure matches Python", () => {
  const full = comparisonFromClosure({
    closureRatio: 1.0,
    targetInstalledMassKg: 1_000_000,
    seedMassKg: 10_000,
    costPerKgUsd: 3_000,
  });
  near(full.massLeverage, 100); // full closure launches only the seed

  const partial = comparisonFromClosure({
    closureRatio: 0.7,
    targetInstalledMassKg: 1_000_000,
    seedMassKg: 10_000,
    costPerKgUsd: 3_000,
  });
  const built = 1_000_000 - 10_000;
  const launched = 10_000 + 0.3 * built;
  near(partial.massLeverage, 1_000_000 / launched);
  assert.ok(partial.massLeverage < full.massLeverage);
});

test("invalid inputs throw", () => {
  assert.throws(() => exhaustVelocityMs(0));
  assert.throws(() => rocketEquationMassRatio(1000, 0));
  assert.throws(() => vitaminMassForBuild(1.5, 1000));
  assert.throws(() =>
    replicationLaunchComparison({
      targetInstalledMassKg: 0,
      seedMassKg: 1,
      vitaminMassTotalKg: 0,
      costPerKgUsd: 1,
    }),
  );
});
