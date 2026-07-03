/**
 * Parity test: the composed TS mission port must reproduce the Python
 * `mission.run_mission` exactly. Ground truth was generated from the Python package
 * (uv run python -c ... asdict(run_mission(default_mission_scenario(**overrides)))).
 * Pure - no pimas (Layer A). If the Python model changes, regenerate these numbers.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { runMission, defaultMissionScenario } from "./mission.ts";
import type { MissionScenario } from "./mission.ts";
import { LUNAR_REGOLITH_SEED } from "./scenarios.ts";

const near = (a: number, b: number, relEps = 1e-6) =>
  assert.ok(Math.abs(a - b) <= Math.abs(b) * relEps + 1e-9, `expected ~${b}, got ${a}`);

interface Case {
  label: string;
  overrides: Partial<MissionScenario>;
  expect: {
    closureRatio: number;
    vitaminMassKg: number;
    launchedMassKg: number;
    massLeverage: number;
    costSavingsUsd: number;
    costRatio: number;
    propellantFraction: number;
    deliveredPowerW: number;
    manufacturingW: number;
    computeW: number;
    computeFlops: number;
    brainEquivalents: number;
    reachesTarget: boolean;
    timeToTargetDays: number | null;
    finalOutputKgPerDay: number;
    bindingRegime: string | null;
  };
}

// Ground truth from the Python package (see mission/ tests + REFERENCES.md).
const CASES: Case[] = [
  {
    label: "baseline (1 AU, 70/20/10, Falcon 9)",
    overrides: {},
    expect: {
      closureRatio: 0.9708333333333333, vitaminMassKg: 28816.666666666675,
      launchedMassKg: 40816.66666666667, massLeverage: 24.499795835034703,
      costSavingsUsd: 2877550000.0, costRatio: 0.040816666666666675,
      propellantFraction: 0.9541371771956907, deliveredPowerW: 3999935.52,
      manufacturingW: 2799954.864, computeW: 799987.104, computeFlops: 7.99987104e16,
      brainEquivalents: 0.0799987104, reachesTarget: true,
      timeToTargetDays: 10512.289221590328, finalOutputKgPerDay: 1389.4010265150935,
      bindingRegime: "resupply-limited",
    },
  },
  {
    label: "Jupiter (5.203 AU) - power-starved, never reaches target",
    overrides: { distanceAu: 5.203 },
    expect: {
      closureRatio: 0.9708333333333333, vitaminMassKg: 28816.666666666675,
      launchedMassKg: 40816.66666666667, massLeverage: 24.499795835034703,
      costSavingsUsd: 2877550000.0, costRatio: 0.040816666666666675,
      propellantFraction: 0.9541371771956907, deliveredPowerW: 147756.07251231372,
      manufacturingW: 103429.2507586196, computeW: 29551.214502462746,
      computeFlops: 2955121450246274.5, brainEquivalents: 0.0029551214502462745,
      reachesTarget: false, timeToTargetDays: null, finalOutputKgPerDay: 137.05601190573478,
      bindingRegime: "resupply-limited",
    },
  },
  {
    label: "all power to compute - factory stalls, compute maxed",
    overrides: { fractionManufacturing: 0, fractionCompute: 1, fractionHousekeeping: 0 },
    expect: {
      closureRatio: 0.9708333333333333, vitaminMassKg: 28816.666666666675,
      launchedMassKg: 40816.66666666667, massLeverage: 24.499795835034703,
      costSavingsUsd: 2877550000.0, costRatio: 0.040816666666666675,
      propellantFraction: 0.9541371771956907, deliveredPowerW: 3999935.52,
      manufacturingW: 0, computeW: 3999935.52, computeFlops: 3.99993552e17,
      brainEquivalents: 0.39999355199999997, reachesTarget: false,
      timeToTargetDays: null, finalOutputKgPerDay: 0, bindingRegime: null,
    },
  },
];

test("mission port reproduces Python ground truth across scenarios", () => {
  for (const c of CASES) {
    const r = runMission(defaultMissionScenario(LUNAR_REGOLITH_SEED, c.overrides));
    const e = c.expect;
    near(r.closureRatio, e.closureRatio);
    near(r.vitaminMassKg, e.vitaminMassKg);
    near(r.launchedMassKg, e.launchedMassKg);
    near(r.massLeverage, e.massLeverage);
    near(r.costSavingsUsd, e.costSavingsUsd);
    near(r.costRatio, e.costRatio);
    near(r.propellantFraction, e.propellantFraction);
    near(r.deliveredPowerW, e.deliveredPowerW);
    near(r.manufacturingW, e.manufacturingW);
    near(r.computeW, e.computeW);
    near(r.computeFlops, e.computeFlops);
    near(r.brainEquivalents, e.brainEquivalents);
    assert.equal(r.reachesTarget, e.reachesTarget, `${c.label}: reachesTarget`);
    if (e.timeToTargetDays === null) assert.equal(r.timeToTargetDays, null, `${c.label}: ttt null`);
    else near(r.timeToTargetDays as number, e.timeToTargetDays);
    near(r.finalOutputKgPerDay, e.finalOutputKgPerDay);
    assert.equal(r.bindingRegime, e.bindingRegime, `${c.label}: regime`);
  }
});

test("inverse-square: doubling distance quarters delivered power", () => {
  const near1 = runMission(defaultMissionScenario(LUNAR_REGOLITH_SEED, { distanceAu: 1 })).deliveredPowerW;
  const far2 = runMission(defaultMissionScenario(LUNAR_REGOLITH_SEED, { distanceAu: 2 })).deliveredPowerW;
  near(near1 / far2, 4);
});

test("seed mass comes from the factory, not a second unlinked number", () => {
  const r = runMission(defaultMissionScenario(LUNAR_REGOLITH_SEED));
  assert.equal(r.seedMassKg, LUNAR_REGOLITH_SEED.replication!.seed_mass_kg);
  assert.equal(r.seedMassKg, 12000);
});
