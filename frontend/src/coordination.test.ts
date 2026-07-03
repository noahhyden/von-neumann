/**
 * Layer A (pimas-free) tests for the light-speed coordination core. Asserts the real
 * light-times and that each real-world analog lands in the rung swarm/REFERENCES.md says
 * it should - behavior, not just execution.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  lightTimeYears,
  roundTripYears,
  rho,
  classifyRung,
  rungForDistancePc,
  RUNGS,
  SEC_PER_YEAR,
} from "./coordination.ts";

const KM_PER_PC = 3.0856775814913673e13; // IAU 2015
const KM_PER_AU = 1.495978707e8; // IAU 2012
const pcFromKm = (km: number) => km / KM_PER_PC;
const pcFromAu = (au: number) => (au * KM_PER_AU) / KM_PER_PC;

// The sourced analog distances (swarm/REFERENCES.md → "Coordination-horizon visualization").
const LEO_PC = pcFromKm(550);
const MOON_PC = pcFromKm(384_400);
const MARS_MEAN_PC = pcFromAu(1.5);
const SATURN_PC = pcFromAu(9.5);
const PROXIMA_PC = 1.301;

const near = (a: number, b: number, relEps = 1e-3) =>
  assert.ok(Math.abs(a - b) <= Math.abs(b) * relEps + 1e-12, `expected ~${b}, got ${a}`);

test("1 AU one-way light time is the textbook 499 s (8.32 min)", () => {
  const oneWaySec = lightTimeYears(pcFromAu(1)) * SEC_PER_YEAR;
  near(oneWaySec, 499.0, 2e-3);
});

test("round-trip is exactly twice one-way", () => {
  for (const d of [1e-8, 0.5, 1.301, 42]) {
    near(roundTripYears(d), 2 * lightTimeYears(d), 1e-12);
  }
});

test("Proxima Centauri: one-way ~4.24 yr, round-trip ~8.49 yr", () => {
  near(lightTimeYears(PROXIMA_PC), 4.243, 1e-2);
  near(roundTripYears(PROXIMA_PC), 8.487, 1e-2);
});

test("each real-world analog lands in the rung REFERENCES.md claims", () => {
  assert.equal(rungForDistancePc(LEO_PC).key, "realtime", "LEO → real-time");
  assert.equal(rungForDistancePc(MOON_PC).key, "movewait", "Earth–Moon → move-and-wait");
  assert.equal(rungForDistancePc(MARS_MEAN_PC).key, "supervisory", "Mars → supervisory");
  assert.equal(rungForDistancePc(SATURN_PC).key, "dtn", "Saturn → delay-tolerant");
  assert.equal(rungForDistancePc(PROXIMA_PC).key, "independent", "Proxima → independent colonies");
});

test("Mars stays supervisory across its whole 0.52–2.52 AU range", () => {
  assert.equal(rungForDistancePc(pcFromAu(0.52)).key, "supervisory", "closest approach");
  assert.equal(rungForDistancePc(pcFromAu(2.52)).key, "supervisory", "farthest");
});

test("the sim's own ~1 pc inter-star hop is already 'independent colonies'", () => {
  // The headline finding: at galactic scale every link sits in the top rung.
  assert.equal(rungForDistancePc(1.0).key, "independent");
  near(roundTripYears(1.0), 6.523, 1e-2); // ~6.5 yr round-trip for a 1 pc hop
});

test("rungs are monotonic: farther is never a faster rung", () => {
  let prev = -1;
  for (const d of [LEO_PC, MOON_PC, MARS_MEAN_PC, SATURN_PC, PROXIMA_PC, 5]) {
    const idx = rungForDistancePc(d).index;
    assert.ok(idx >= prev, `index dropped from ${prev} to ${idx} at d=${d} pc`);
    prev = idx;
  }
});

test("ρ scales inversely with the decision timescale, and rung is τ-independent", () => {
  const d = 1.301; // Proxima
  near(rho(d, 1), 2 * rho(d, 2), 1e-12); // halving τ doubles ρ
  // The rung is set by absolute latency, so τ must not change it.
  assert.equal(rungForDistancePc(d).key, classifyRung(roundTripYears(d)).key);
});

test("classifyRung honors the exact sourced boundaries (seconds)", () => {
  // A round-trip of exactly the bound stays in the faster rung (<=), just past it steps down.
  const yr = (sec: number) => sec / SEC_PER_YEAR;
  assert.equal(classifyRung(yr(1)).key, "realtime");
  assert.equal(classifyRung(yr(1.0001)).key, "movewait");
  assert.equal(classifyRung(yr(60)).key, "movewait");
  assert.equal(classifyRung(yr(3600)).key, "supervisory");
  assert.equal(classifyRung(yr(SEC_PER_YEAR)).key, "dtn");
  assert.equal(classifyRung(yr(SEC_PER_YEAR * 1.001)).key, "independent");
});

test("RUNGS table is well-formed (5 rungs, ordered, indexed)", () => {
  assert.equal(RUNGS.length, 5);
  for (let i = 0; i < RUNGS.length; i++) {
    assert.equal(RUNGS[i].index, i);
    if (i > 0) assert.ok(RUNGS[i].maxRoundTripSec > RUNGS[i - 1].maxRoundTripSec);
  }
  assert.equal(RUNGS[RUNGS.length - 1].maxRoundTripSec, Infinity);
});
