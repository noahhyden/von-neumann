/**
 * Differential test, half 1 of 2: generate N random factories + replication
 * params, run them through the TS port, and dump {input, ts-results} to JSON.
 * `diff_check.py` then recomputes each with the real Python closure-sim and
 * asserts the two agree. This is the strongest correctness proof - it pins the
 * port against the reference across the whole input space, not just two scenarios.
 *
 *   node scripts/gen-diff.mjs && (cd ../closure-sim && uv run python ../frontend/scripts/diff_check.py)
 *
 * Deterministic: a seeded PRNG (no Math.random) so cases are reproducible.
 */
import { writeFileSync } from "node:fs";
import { computeClosure, simulate } from "../src/model.ts";

// tiny seeded PRNG (mulberry32)
let seed = 0x9e3779b9;
const rnd = () => {
  seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const pick = (a) => a[Math.floor(rnd() * a.length)];
const rangeF = (lo, hi) => lo + rnd() * (hi - lo);
const rangeI = (lo, hi) => Math.floor(rangeF(lo, hi + 1));

const CATS = ["structure", "power", "thermal", "actuators", "sensors", "compute", "electronics"];

function randomFactory() {
  const n = rangeI(4, 9);
  const subsystems = [];
  for (let i = 0; i < n; i++) {
    const category = pick(CATS);
    const isElec = category === "compute" || category === "electronics";
    subsystems.push({
      name: `part-${i}`,
      mass_kg: Math.round(rangeF(50, 5000)),
      category,
      // electronics are usually vitamins; others usually local
      producible_locally: isElec ? rnd() < 0.3 : rnd() < 0.85,
      processes: [],
      energy_to_produce_kwh_per_kg: isElec ? Math.round(rangeF(1500, 9000)) : Math.round(rangeF(2, 120)),
    });
  }
  // guarantee at least one local subsystem so local_mass > 0 in most cases
  if (!subsystems.some((s) => s.producible_locally)) subsystems[0].producible_locally = true;
  return { name: "rand", subsystems, replication: null };
}

function randomRep() {
  return {
    seed_mass_kg: Math.round(rangeF(2000, 40000)),
    local_build_rate_kg_per_day: Math.round(rangeF(2, 100)),
    vitamin_resupply_mass_kg: Math.round(rangeF(0, 300)),
    resupply_cadence_days: Math.round(rangeF(7, 120)),
    available_power_kw: Math.round(rangeF(250, 12000)),
    target_output_kg_per_day: Math.round(rangeF(50, 3000)),
    duration_days: 3650, // keep the Python side fast across many cases
    dt_days: 1.0,
  };
}

const N = 60;
const cases = [];
for (let i = 0; i < N; i++) {
  const factory = randomFactory();
  const rep = randomRep();
  const c = computeClosure(factory);
  const s = simulate(factory, rep);
  cases.push({
    factory,
    rep,
    ts: {
      closure_ratio: c.closure_ratio,
      productivity_per_day: s.productivity_per_day,
      energy_cap_kg_per_day: s.energy_cap_kg_per_day,
      resupply_ceiling_kg_per_day: s.resupply_ceiling_kg_per_day,
      time_to_target_days: s.time_to_target_days,
      empirical_doubling_time_days: s.empirical_doubling_time_days,
      final_factory_mass_kg: s.final_factory_mass_kg,
      final_output_kg_per_day: s.final_output_kg_per_day,
      late_regime: s.regime_timeline[s.regime_timeline.length - 1].regime,
    },
  });
}

// JSON can't carry Infinity/NaN (they become null) - encode as sentinels the
// Python side decodes, so a genuine inf==inf comparison isn't lost in transport.
const enc = (_k, v) =>
  typeof v === "number" && !Number.isFinite(v)
    ? Number.isNaN(v)
      ? "__nan__"
      : v > 0
        ? "__inf__"
        : "__-inf__"
    : v;

const out = "/tmp/frontend-diff-cases.json";
writeFileSync(out, JSON.stringify(cases, enc));
console.log(`wrote ${N} cases -> ${out}`);
