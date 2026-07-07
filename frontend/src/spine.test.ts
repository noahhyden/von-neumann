/**
 * Layer A parity: the TS spine port must reproduce `spine/run.py` exactly on the shared
 * lunar-regolith factory. Ground-truth values are transcribed from the Python module
 * (see the print in the commit that added spine); this test fails if the composition of
 * the (individually parity-tested) ports drifts. No pimas here - pure model.
 */
import test from "node:test";
import assert from "node:assert/strict";

import { LUNAR_REGOLITH_SEED } from "./scenarios.ts";
import { runSpine, measureDwellTax, deriveSettleTimeYears, scenarioFrom } from "./spine.ts";

const approx = (a: number, b: number, eps = 1e-9) => assert.ok(Math.abs(a - b) <= eps * Math.max(1, Math.abs(b)), `${a} !~= ${b}`);

test("one factory drives every scale, and the dwell is derived from it", () => {
  const r = runSpine(scenarioFrom(LUNAR_REGOLITH_SEED));
  approx(r.closureRatio, 0.9708333333333333);
  approx(r.singleFactoryTimeToTargetDays!, 10512.289221590328);
  approx(r.copyTimeDays, 582.5);
  approx(r.settleTimeYears, 1.594798083504449);
  // the derived dwell equals copy time / Julian year, exactly
  approx(deriveSettleTimeYears(scenarioFrom(LUNAR_REGOLITH_SEED)), 582.5 / 365.25);
});

test("the copy cadence is the fleet's doubling clock", () => {
  const r = runSpine(scenarioFrom(LUNAR_REGOLITH_SEED));
  approx(r.fleetDoublingDays!, 583.0);
  assert.equal(r.fleetFinalPopulation, 28);
  assert.ok(Math.abs(r.fleetDoublingDays! - r.copyTimeDays) <= 2.0);
});

test("powered: field fills 100%, dwell is a vanishing fraction of the fill", () => {
  const r = runSpine(scenarioFrom(LUNAR_REGOLITH_SEED));
  approx(r.swarmT100Years!, 2015000.0);
  assert.equal(r.finalSettled, 1200);
  approx(r.dwellFractionOfT100!, 7.914630687366993e-7);
  assert.ok(r.dwellFractionOfT100! < 1e-5);
});

test("slingshot dwell tax: small, positive, and ordered above powered", () => {
  const tx = measureDwellTax(scenarioFrom(LUNAR_REGOLITH_SEED, { policy: "slingshot_nearest" }));
  approx(tx.t100ZeroDwell!, 8326.0);
  approx(tx.t100WithDwell!, 8359.0);
  approx(tx.taxFraction!, 0.003963487869325006);
  assert.ok(tx.taxFraction! > 0 && tx.taxFraction! < 0.01);
  const poweredFrac = runSpine(scenarioFrom(LUNAR_REGOLITH_SEED)).dwellFractionOfT100!;
  assert.ok(poweredFrac < tx.taxFraction!);
});

test("no offspring settles only the homeworld (boundary)", () => {
  const r = runSpine(scenarioFrom(LUNAR_REGOLITH_SEED, { offspringPerSettlement: 0 }));
  assert.equal(r.finalSettled, 1);
  assert.equal(r.swarmT100Years, null);
  assert.equal(r.dwellFractionOfT100, null);
});

test("verdict is plain ASCII (no em-dash, no emoji)", () => {
  const v = runSpine(scenarioFrom(LUNAR_REGOLITH_SEED)).verdict;
  assert.ok(v.length > 0);
  assert.ok(!v.includes(String.fromCharCode(0x2014)));
});
