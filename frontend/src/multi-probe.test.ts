/**
 * Parity test: the TS multi-probe port must reproduce the Python `multi_probe.fleet`
 * exactly, including the seeded mulberry32 sequence (jitter case). Ground truth was
 * generated from the Python package. Pure — no pimas (Layer A). If the Python model
 * changes, regenerate these numbers.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { nextFloat, seedState, paramsFromFactory, simulateFleet } from "./multi-probe.ts";
import type { FleetParams } from "./multi-probe.ts";
import { LUNAR_REGOLITH_SEED } from "./scenarios.ts";

const near = (a: number, b: number, relEps = 1e-9) =>
  assert.ok(Math.abs(a - b) <= Math.abs(b) * relEps + 1e-9, `expected ~${b}, got ${a}`);

test("mulberry32 threaded RNG matches the reference sequence (seed 0x9e3779b9)", () => {
  let s = seedState(0x9e3779b9);
  const got: number[] = [];
  for (let i = 0; i < 5; i++) {
    const [v, ns] = nextFloat(s);
    got.push(v);
    s = ns;
  }
  const want = [0.358889980241656, 0.105903261341155, 0.675290479324758, 0.917934558819979, 0.101577150402591];
  got.forEach((v, i) => near(v, want[i], 1e-12));
});

interface Case {
  label: string;
  overrides: Partial<FleetParams>;
  seed: number;
  durationDays: number;
  dtDays: number;
  expect: {
    finalPopulation: number;
    totalChildren: number;
    doublingTimeDays: number | null;
    vitaminsConsumedKg: number;
    meanDistanceAu: number;
    maxDistanceAu: number;
    binding: { vitaminLimited: boolean; powerLimited: boolean; capLimited: boolean };
    nsteps: number;
    popSamples: [number, number][]; // [stepIndex, population]
  };
}

// Ground truth from the Python package (multi_probe, lunar-regolith factory).
const CASES: Case[] = [
  {
    label: "near default (1 AU)",
    overrides: {}, seed: 0x9e3779b9, durationDays: 3650, dtDays: 10,
    expect: {
      finalPopulation: 22, totalChildren: 21, doublingTimeDays: 590, vitaminsConsumedKg: 7350,
      meanDistanceAu: 1.697459, maxDistanceAu: 2.8561,
      binding: { vitaminLimited: false, powerLimited: false, capLimited: false }, nsteps: 366,
      popSamples: [[0, 1], [91, 2], [183, 5], [274, 12], [365, 22]],
    },
  },
  {
    label: "vitamin-limited (electronics wall)",
    overrides: { vitaminPoolKg: 1750.5, maxProbes: 256 }, seed: 0x9e3779b9, durationDays: 14600, dtDays: 10,
    expect: {
      finalPopulation: 6, totalChildren: 5, doublingTimeDays: 590, vitaminsConsumedKg: 1750.0000000000005,
      meanDistanceAu: 1.38, maxDistanceAu: 1.69,
      binding: { vitaminLimited: true, powerLimited: false, capLimited: false }, nsteps: 1461,
      popSamples: [[0, 1], [365, 6], [730, 6], [1095, 6], [1460, 6]],
    },
  },
  {
    label: "far (30 AU) — spatial power wall",
    overrides: { startDistanceAu: 30.0, maxProbes: 256 }, seed: 0x9e3779b9, durationDays: 3650, dtDays: 10,
    expect: {
      finalPopulation: 2, totalChildren: 1, doublingTimeDays: 2830, vitaminsConsumedKg: 350,
      meanDistanceAu: 34.5, maxDistanceAu: 39.0,
      binding: { vitaminLimited: false, powerLimited: true, capLimited: false }, nsteps: 366,
      popSamples: [[0, 1], [91, 1], [183, 1], [274, 1], [365, 2]],
    },
  },
  {
    label: "seeded transit jitter",
    overrides: { transitJitterFrac: 0.3 }, seed: 12345, durationDays: 3650, dtDays: 10,
    expect: {
      finalPopulation: 23, totalChildren: 22, doublingTimeDays: 590, vitaminsConsumedKg: 7700,
      meanDistanceAu: 1.719178, maxDistanceAu: 2.8561,
      binding: { vitaminLimited: false, powerLimited: false, capLimited: false }, nsteps: 366,
      popSamples: [[0, 1], [91, 2], [183, 5], [274, 10], [365, 23]],
    },
  },
];

test("multi-probe port reproduces Python ground truth across scenarios", () => {
  for (const c of CASES) {
    const r = simulateFleet(paramsFromFactory(LUNAR_REGOLITH_SEED, c.overrides), {
      seed: c.seed, durationDays: c.durationDays, dtDays: c.dtDays,
    });
    const e = c.expect;
    assert.equal(r.finalPopulation, e.finalPopulation, `${c.label}: finalPopulation`);
    assert.equal(r.totalChildren, e.totalChildren, `${c.label}: totalChildren`);
    assert.equal(r.doublingTimeDays, e.doublingTimeDays, `${c.label}: doublingTimeDays`);
    near(r.vitaminsConsumedKg, e.vitaminsConsumedKg);
    near(r.meanDistanceAu, e.meanDistanceAu, 1e-5);
    near(r.maxDistanceAu, e.maxDistanceAu, 1e-5);
    assert.deepEqual(r.binding, e.binding, `${c.label}: binding`);
    assert.equal(r.steps.length, e.nsteps, `${c.label}: nsteps`);
    for (const [i, pop] of e.popSamples) {
      assert.equal(r.steps[i].population, pop, `${c.label}: pop@${i}`);
    }
  }
});

test("no-jitter run is independent of seed (RNG never consumed)", () => {
  const p = paramsFromFactory(LUNAR_REGOLITH_SEED);
  const a = simulateFleet(p, { seed: 1, durationDays: 3650, dtDays: 10 });
  const b = simulateFleet(p, { seed: 999999, durationDays: 3650, dtDays: 10 });
  assert.deepEqual(a.steps.map((s) => s.population), b.steps.map((s) => s.population));
});
