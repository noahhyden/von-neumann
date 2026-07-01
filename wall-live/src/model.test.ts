/**
 * Parity test: the TS port must reproduce the Python closure-sim exactly.
 * Ground-truth numbers were captured by running the real Python CLI on the
 * lunar_regolith_seed scenario (see git history / the closure-sim package).
 * Run with `node --test` (Node >=23 strips the TS types natively).
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { computeClosure, simulate, electronicsWall } from "./model.ts";
import { LUNAR_REGOLITH_SEED, LOW_CLOSURE_OUTPOST } from "./scenarios.ts";

const near = (a: number | null, b: number, eps = 1e-3) => {
  assert.ok(a !== null, "expected a number, got null");
  assert.ok(Math.abs((a as number) - b) < eps, `expected ~${b}, got ${a}`);
};

test("closure of the lunar seed matches Python (0.970833)", () => {
  const c = computeClosure(LUNAR_REGOLITH_SEED);
  near(c.closure_ratio, 0.970833);
  assert.equal(c.total_mass_kg, 12000);
  assert.equal(c.vitamin_mass_kg, 350);
});

test("simulate() scalars match Python", () => {
  const s = simulate(LUNAR_REGOLITH_SEED);
  near(s.productivity_per_day, 0.0016666667, 1e-8);
  near(s.energy_cap_kg_per_day, 5300.4739, 1e-2);
  near(s.resupply_ceiling_kg_per_day, 57.142857, 1e-4);
  near(s.analytic_doubling_time_days, 403.7582, 1e-2);
  near(s.empirical_doubling_time_days, 404.1046, 1e-2);
  near(s.time_to_target_days, 10512.2892, 1e-2); // ~28.8 years
  near(s.final_factory_mass_kg, 833640.62, 1);
});

test("electronics wall matches Python: 10512d -> 6350d (chips local wins)", () => {
  const w = electronicsWall(LUNAR_REGOLITH_SEED);
  near(w.before.time_to_target_days, 10512.2892, 1e-2); // ~29 years
  near(w.after.time_to_target_days, 6350.4485, 1e-2); // ~17.4 years
  assert.equal(w.electronics_mass_kg, 150);
  near(w.electronics_mass_share, 0.0125, 1e-6);
  assert.ok((w.time_to_target_delta_days ?? 0) > 4000, "chips-local should save >4000 days");
});

test("low-closure outpost matches Python (0.4286, 23.3 yr, resupply-limited)", () => {
  const c = computeClosure(LOW_CLOSURE_OUTPOST);
  near(c.closure_ratio, 0.4286, 1e-3);
  const s = simulate(LOW_CLOSURE_OUTPOST);
  near(s.time_to_target_days, 8500.0, 1); // 23.3 yr
  assert.equal(s.regime_timeline[s.regime_timeline.length - 1].regime, "resupply-limited");
});

test("1 MW backfire: making chips locally never reaches target", () => {
  const rep = { ...LUNAR_REGOLITH_SEED.replication!, available_power_kw: 1000.0 };
  const w = electronicsWall(LUNAR_REGOLITH_SEED, rep);
  assert.equal(w.after.time_to_target_days, null); // runs out of power -> never
});

// ── emergent-behaviour edge cases (from replication.py's docstring) ─────────
test("R = 0 with C < 1: no vitamins -> growth pins to zero (stuck)", () => {
  const rep = { ...LUNAR_REGOLITH_SEED.replication!, vitamin_resupply_mass_kg: 0 };
  const s = simulate(LUNAR_REGOLITH_SEED, rep);
  near(s.final_factory_mass_kg, rep.seed_mass_kg, 1e-6); // never grew
  assert.equal(s.time_to_target_days, null);
});

test("C -> 1 (all local): resupply never binds, growth stays exponential", () => {
  const allLocal = { ...LUNAR_REGOLITH_SEED, subsystems: LUNAR_REGOLITH_SEED.subsystems.map((s) => ({ ...s, producible_locally: true })) };
  const s = simulate(allLocal);
  near(s.closure_ratio, 1.0, 1e-9);
  assert.equal(s.resupply_ceiling_kg_per_day, Infinity); // R/(1-C) -> inf at C=1
  // with 4 MW it should still reach the 1000 kg/day goal
  assert.ok(s.time_to_target_days !== null && s.time_to_target_days < s.steps[s.steps.length - 1].day);
});
