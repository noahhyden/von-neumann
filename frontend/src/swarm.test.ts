/**
 * Parity test: the TS swarm port must reproduce the Python `swarm.sim` exactly,
 * including the seeded star field and the settlement trajectory. Ground truth was
 * generated from the Python package. Pure - no pimas (Layer A). The cube-root box size
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

test("slingshot policies reproduce Python ground truth (boost + policy)", () => {
  // Ground truth from the Python swarm (n=300, seed 0x9e3779b9). Verifies the boost
  // (Eq. 4), the star-speed RNG pass, and both target policies match bit-for-bit.
  const sling: { policy: "slingshot_nearest" | "slingshot_maxboost"; e: { settled: number; launched: number; t100: number; maxSpd: number; front: number; nsteps: number; samples: [number, number][] } }[] = [
    {
      policy: "slingshot_nearest",
      e: { settled: 300, launched: 597, t100: 80000, maxSpd: 3306.146761, front: 5.70727, nsteps: 18,
           samples: [[0, 1], [4, 23], [9, 138], [13, 268], [17, 300]] },
    },
    {
      policy: "slingshot_maxboost",
      e: { settled: 300, launched: 597, t100: 265000, maxSpd: 5720.451103, front: 5.70727, nsteps: 55,
           samples: [[0, 1], [13, 149], [27, 239], [41, 276], [54, 300]] },
    },
  ];
  for (const { policy, e } of sling) {
    const r = simulateSwarm({ ...SWARM_DEFAULTS, nStars: 300, policy }, 0x9e3779b9);
    assert.equal(r.finalSettled, e.settled, `${policy}: settled`);
    assert.equal(r.totalProbesLaunched, e.launched, `${policy}: launched`);
    assert.equal(r.t100Years, e.t100, `${policy}: t100`);
    near(r.maxProbeSpeedKmS, e.maxSpd, 1e-6);
    near(r.frontRadiusPc, e.front, 1e-4);
    assert.equal(r.steps.length, e.nsteps, `${policy}: nsteps`);
    assert.equal(r.policy, policy);
    for (const [i, pop] of e.samples) assert.equal(r.steps[i].nSettled, pop, `${policy}: pop@${i}`);
  }
});

test("nearest-slingshot beats max-boost on time (N&F finding), both faster than powered", () => {
  const powered = simulateSwarm({ ...SWARM_DEFAULTS, nStars: 300, policy: "powered" }, 0x9e3779b9);
  const nearest = simulateSwarm({ ...SWARM_DEFAULTS, nStars: 300, policy: "slingshot_nearest" }, 0x9e3779b9);
  const maxboost = simulateSwarm({ ...SWARM_DEFAULTS, nStars: 300, policy: "slingshot_maxboost" }, 0x9e3779b9);
  assert.ok(nearest.t100Years! < powered.t100Years!, "nearest slingshot beats powered");
  assert.ok(nearest.t100Years! < maxboost.t100Years!, "nearest beats max-boost on time");
  assert.ok(maxboost.maxProbeSpeedKmS > nearest.maxProbeSpeedKmS, "max-boost reaches higher speed");
  assert.ok(nearest.maxProbeSpeedKmS > 10 * powered.maxProbeSpeedKmS, "slingshot speed accumulates");
});

test("spatial-hash nearest search is bit-identical to brute force (prove small)", () => {
  // The grid is a pure speedup: for many queries, over evolving settled masks, it must
  // return exactly the brute-force nearest - including the lowest-index tie-break.
  for (const [n, seed] of [[300, 1], [800, 7], [1500, 42]] as [number, number][]) {
    const s = initialState({ ...SWARM_DEFAULTS, nStars: n }, seed);
    // Mark a deterministic ~40% of stars settled to exercise a sparse candidate set.
    for (let i = 0; i < n; i++) if ((i * 2654435761) % 5 < 2) s.settledYear[i] = 1;
    let checked = 0;
    for (let frm = 0; frm < n; frm += 7) {
      const exclude = new Set<number>([(frm + 3) % n, (frm + 11) % n]);
      const g = gridNearestUnsettled(s, frm, exclude, SWARM_DEFAULTS);
      const b = bruteNearestUnsettled(s, frm, exclude, SWARM_DEFAULTS);
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

test("lightspeed coordination reproduces Python ground truth (belief gate + counters)", () => {
  // Ground truth from the Python swarm (n=300, seed 0x9e3779b9, coordination="lightspeed").
  // Verifies the light-cone belief gate, the grid-no-remove path, and the wasted-trip counters
  // match bit-for-bit - including the slingshot regime where the effect lives.
  const cases: { policy: Policy; e: { settled: number; launched: number; t100: number; maxSpd: number; front: number; nsteps: number; totalArr: number; wasted: number; retarget: number; samples: [number, number][] } }[] = [
    {
      policy: "slingshot_nearest",
      e: { settled: 300, launched: 598, t100: 110000, maxSpd: 3807.375281, front: 5.70727, nsteps: 24,
           totalArr: 2341, wasted: 2042, retarget: 1743, samples: [[0, 1], [6, 36], [12, 124], [18, 262], [23, 300]] },
    },
    {
      policy: "powered",
      e: { settled: 300, launched: 597, t100: 1610000, maxSpd: 8.993774, front: 5.70727, nsteps: 531,
           totalArr: 1754, wasted: 1455, retarget: 1157, samples: [[0, 1], [132, 77], [265, 279], [398, 300], [530, 300]] },
    },
  ];
  for (const { policy, e } of cases) {
    const r = simulateSwarm({ ...SWARM_DEFAULTS, nStars: 300, policy, coordination: "lightspeed" }, 0x9e3779b9);
    assert.equal(r.finalSettled, e.settled, `${policy}: settled`);
    assert.equal(r.totalProbesLaunched, e.launched, `${policy}: launched`);
    assert.equal(r.t100Years, e.t100, `${policy}: t100`);
    near(r.maxProbeSpeedKmS, e.maxSpd, 1e-6);
    near(r.frontRadiusPc, e.front, 1e-4);
    assert.equal(r.steps.length, e.nsteps, `${policy}: nsteps`);
    assert.equal(r.totalArrivals, e.totalArr, `${policy}: totalArrivals`);
    assert.equal(r.wastedArrivals, e.wasted, `${policy}: wastedArrivals`);
    assert.equal(r.retargetCount, e.retarget, `${policy}: retargetCount`);
    assert.equal(r.coordination, "lightspeed");
    for (const [i, pop] of e.samples) assert.equal(r.steps[i].nSettled, pop, `${policy}: pop@${i}`);
  }
});

test("lightspeed slows slingshots but leaves powered's timescale unchanged (the finding)", () => {
  const mk = (policy: Policy, coordination: "instant" | "lightspeed") =>
    simulateSwarm({ ...SWARM_DEFAULTS, nStars: 300, policy, coordination }, 0x9e3779b9);
  const si = mk("slingshot_nearest", "instant"), sl = mk("slingshot_nearest", "lightspeed");
  assert.ok(sl.t100Years! > si.t100Years!, "lightspeed slows the slingshot fill");
  assert.ok(sl.wastedArrivals > si.wastedArrivals, "and adds wasted trips");
  const pi = mk("powered", "instant"), pl = mk("powered", "lightspeed");
  assert.equal(pl.t100Years, pi.t100Years, "powered nearest-neighbour fill is immune (local recovery)");
  assert.equal(sl.finalSettled, 300, "a connected field still fills to 100% under lag");
});

test("instant mode is bit-identical to the default (c→∞ reduction)", () => {
  // The keystone: "instant" drops the light-cone term, so it must reproduce the perfect-info
  // run exactly. (SWARM_DEFAULTS is already coordination:"instant", so this pins the explicit form.)
  const explicit = simulateSwarm({ ...SWARM_DEFAULTS, nStars: 300, policy: "slingshot_nearest", coordination: "instant" }, 0x9e3779b9);
  const dflt = simulateSwarm({ ...SWARM_DEFAULTS, nStars: 300, policy: "slingshot_nearest" }, 0x9e3779b9);
  assert.deepEqual(explicit.steps.map((s) => s.nSettled), dflt.steps.map((s) => s.nSettled));
  assert.equal(explicit.t100Years, dflt.t100Years);
});

test("grid ≡ brute under the lightspeed belief gate", () => {
  // The belief gate is a pure per-star predicate, so grid and brute must still agree - now
  // with settled stars kept in the grid (not removed) and news partially propagated.
  const p = { ...SWARM_DEFAULTS, nStars: 800, coordination: "lightspeed" as const };
  const s = initialState(p, 7);
  s.year = 4.0; // let some settlement news have propagated (dist/c ~ a few yr at 1 pc)
  for (let i = 0; i < 800; i++) if ((i * 2654435761) % 5 < 2) s.settledYear[i] = (i % 7) * 0.6;
  let checked = 0;
  for (let frm = 0; frm < 800; frm += 13) {
    const g = gridNearestUnsettled(s, frm, new Set(), p);
    const b = bruteNearestUnsettled(s, frm, new Set(), p);
    assert.equal(g, b, `frm=${frm}: grid ${g} != brute ${b}`);
    checked++;
  }
  assert.ok(checked > 10);
});

test("same seed is bit-identical; a connected field always fills", () => {
  const p: SwarmParams = { ...SWARM_DEFAULTS, nStars: 250 };
  const a = simulateSwarm(p, 5);
  const b = simulateSwarm(p, 5);
  assert.deepEqual(a.steps.map((s) => s.nSettled), b.steps.map((s) => s.nSettled));
  assert.equal(a.finalSettled, 250);
});
