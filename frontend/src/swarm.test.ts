/**
 * Parity test: the TS swarm port must reproduce the Python `swarm.sim` exactly,
 * including the seeded star field and the settlement trajectory. Ground truth was
 * generated from the Python package. Pure — no pimas (Layer A). The cube-root box size
 * (N/ρ)^(1/3) matches bit-for-bit between Python and JS, so full runs agree.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { simulateSwarm, SWARM_DEFAULTS, C_PC_PER_YEAR } from "./swarm.ts";
import type { SwarmParams } from "./swarm.ts";

const near = (a: number, b: number, relEps = 1e-9) =>
  assert.ok(Math.abs(a - b) <= Math.abs(b) * relEps + 1e-9, `expected ~${b}, got ${a}`);

test("light-speed constant matches the Python (~0.3066 pc/yr)", () => {
  near(C_PC_PER_YEAR, 0.3066, 1e-3);
});

interface Case {
  nStars: number;
  offspring: number;
  seed: number;
  expect: {
    finalSettled: number;
    totalProbesLaunched: number;
    t50: number | null;
    t90: number | null;
    t100: number | null;
    frontRadiusPc: number;
    nsteps: number;
    popSamples: [number, number][];
  };
}

const CASES: Case[] = [
  {
    nStars: 300, offspring: 2, seed: 0x9e3779b9,
    expect: {
      finalSettled: 300, totalProbesLaunched: 597, t50: 875_000, t90: 1_265_000, t100: 1_610_000,
      frontRadiusPc: 5.707269547365495, nsteps: 531,
      popSamples: [[0, 1], [132, 79], [265, 278], [398, 300], [530, 300]],
    },
  },
  {
    nStars: 200, offspring: 3, seed: 42,
    expect: {
      finalSettled: 200, totalProbesLaunched: 594, t50: 550_000, t90: 760_000, t100: 970_000,
      frontRadiusPc: 4.936284928649846, nsteps: 362,
      popSamples: [[0, 1], [90, 61], [181, 198], [271, 200], [361, 200]],
    },
  },
];

test("swarm port reproduces Python ground truth (field + trajectory)", () => {
  for (const c of CASES) {
    const params: SwarmParams = { ...SWARM_DEFAULTS, nStars: c.nStars, offspringPerSettlement: c.offspring };
    const r = simulateSwarm(params, c.seed);
    const e = c.expect;
    assert.equal(r.finalSettled, e.finalSettled, `n=${c.nStars}: finalSettled`);
    assert.equal(r.totalProbesLaunched, e.totalProbesLaunched, `n=${c.nStars}: launched`);
    assert.equal(r.t50Years, e.t50, `n=${c.nStars}: t50`);
    assert.equal(r.t90Years, e.t90, `n=${c.nStars}: t90`);
    assert.equal(r.t100Years, e.t100, `n=${c.nStars}: t100`);
    near(r.frontRadiusPc, e.frontRadiusPc, 1e-9);
    assert.equal(r.steps.length, e.nsteps, `n=${c.nStars}: nsteps`);
    for (const [i, pop] of e.popSamples) assert.equal(r.steps[i].nSettled, pop, `n=${c.nStars}: pop@${i}`);
  }
});

test("same seed is bit-identical; a connected field always fills", () => {
  const p: SwarmParams = { ...SWARM_DEFAULTS, nStars: 250 };
  const a = simulateSwarm(p, 5);
  const b = simulateSwarm(p, 5);
  assert.deepEqual(a.steps.map((s) => s.nSettled), b.steps.map((s) => s.nSettled));
  assert.equal(a.finalSettled, 250);
});
