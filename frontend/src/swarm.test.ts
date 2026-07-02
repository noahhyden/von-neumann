/**
 * Parity test: the TS swarm port must reproduce the Python `swarm.sim` exactly,
 * including the seeded star field and the settlement trajectory. Ground truth was
 * generated from the Python package. Pure — no pimas (Layer A). The cube-root box size
 * (N/ρ)^(1/3) matches bit-for-bit between Python and JS, so full runs agree.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { simulateSwarm, SWARM_DEFAULTS, C_PC_PER_YEAR, initialState, bruteNearestUnsettled, gridNearestUnsettled } from "./swarm.ts";
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

test("spatial-hash nearest search is bit-identical to brute force (prove small)", () => {
  // The grid is a pure speedup: for many queries, over evolving settled masks, it must
  // return exactly the brute-force nearest — including the lowest-index tie-break.
  for (const [n, seed] of [[300, 1], [800, 7], [1500, 42]] as [number, number][]) {
    const s = initialState({ ...SWARM_DEFAULTS, nStars: n }, seed);
    // Mark a deterministic ~40% of stars settled to exercise a sparse candidate set.
    for (let i = 0; i < n; i++) if ((i * 2654435761) % 5 < 2) s.settledYear[i] = 1;
    let checked = 0;
    for (let frm = 0; frm < n; frm += 7) {
      const exclude = new Set<number>([(frm + 3) % n, (frm + 11) % n]);
      const g = gridNearestUnsettled(s, frm, exclude);
      const b = bruteNearestUnsettled(s, frm, exclude);
      assert.equal(g, b, `n=${n} seed=${seed} frm=${frm}: grid ${g} != brute ${b}`);
      checked++;
    }
    assert.ok(checked > 10, "ran a meaningful number of queries");
  }
});

test("grid scales to a large field and still fills it (build large)", () => {
  // 8000 stars would be ~6.4e7 ops for the brute O(N^2) settlement; the grid keeps it fast.
  const r = simulateSwarm({ ...SWARM_DEFAULTS, nStars: 8000 }, 123);
  assert.equal(r.finalSettled, 8000);
  assert.ok(r.t100Years !== null && r.t100Years > 0);
});

test("same seed is bit-identical; a connected field always fills", () => {
  const p: SwarmParams = { ...SWARM_DEFAULTS, nStars: 250 };
  const a = simulateSwarm(p, 5);
  const b = simulateSwarm(p, 5);
  assert.deepEqual(a.steps.map((s) => s.nSettled), b.steps.map((s) => s.nSettled));
  assert.equal(a.finalSettled, 250);
});
