/**
 * Parity test: the TS port must reproduce the Python probe-sim exactly.
 * Ground-truth mirrors probe-sim/tests/test_environment.py and test_autonomy.py.
 * Pure - no pimas (Layer A).
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  AU_DISTANCE,
  REPLICATED_MASS_FRACTION,
  SOLAR_CONSTANT_1AU_W_M2,
  computeHeadroomAt,
  maxDistanceAu,
  maxDistanceForCompute,
  solarArrayPowerW,
  solarIrradianceWM2,
} from "./probe-sim.ts";

const near = (a: number, b: number, relEps = 1e-6) =>
  assert.ok(Math.abs(a - b) <= Math.abs(b) * relEps + 1e-12, `expected ~${b}, got ${a}`);

test("solar irradiance: 1 AU is the constant, inverse-square, ~50 W/m^2 at Jupiter", () => {
  near(solarIrradianceWM2(1.0), SOLAR_CONSTANT_1AU_W_M2);
  near(solarIrradianceWM2(2.0), SOLAR_CONSTANT_1AU_W_M2 / 4);
  assert.ok(Math.abs(solarIrradianceWM2(AU_DISTANCE.jupiter) - 50.3) < 1.0);
});

test("solar array power scales with area, efficiency and distance", () => {
  const array = { areaM2: 10, efficiency: 0.3 };
  near(solarArrayPowerW(array, 1.0), SOLAR_CONSTANT_1AU_W_M2 * 10 * 0.3);
  near(solarArrayPowerW(array, 2.0), solarArrayPowerW(array, 1.0) / 4);
});

test("max distance is the inverse of the power demand", () => {
  const array = { areaM2: 5, efficiency: 0.3 };
  const demand = solarArrayPowerW(array, 3.0);
  near(maxDistanceAu(array, demand), 3.0);
});

test("compute headroom composes power, allocation, efficiency (falls as 1/d^2)", () => {
  const array = { areaM2: 10, efficiency: 0.3 };
  const opts = { computeFraction: 0.2, efficiencyFlopsPerW: 1e11 };
  const h = computeHeadroomAt(array, 1.0, opts);
  near(h.deliveredPowerW, solarArrayPowerW(array, 1.0));
  near(h.computePowerW, 0.2 * h.deliveredPowerW);
  near(h.computeFlops, h.computePowerW * 1e11);
  near(h.brainEquivalents, h.computeFlops / 1e18);
  near(computeHeadroomAt(array, 2.0, opts).computeFlops, h.computeFlops / 4);
});

test("max distance for compute roundtrips and scales with demand", () => {
  const array = { areaM2: 10, efficiency: 0.3 };
  const opts = { computeFraction: 0.2, efficiencyFlopsPerW: 1e11 };
  const d = maxDistanceForCompute(array, 1e13, opts);
  near(computeHeadroomAt(array, d, opts).computeFlops, 1e13);
  // 4x the compute demand -> half the reach.
  near(maxDistanceForCompute(array, 4e13, opts), d / 2);
});

test("constants and invalid inputs", () => {
  assert.equal(REPLICATED_MASS_FRACTION, 0.7);
  assert.throws(() => solarIrradianceWM2(0));
  assert.throws(() => maxDistanceForCompute({ areaM2: 10, efficiency: 0.3 }, 0, { computeFraction: 0.2, efficiencyFlopsPerW: 1e11 }));
  assert.throws(() => solarArrayPowerW({ areaM2: 1, efficiency: 1.5 }, 1.0));
});
