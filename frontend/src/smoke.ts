/**
 * Headless integration smoke: the reactive model + `speculate` must (a) reproduce
 * the electronics-wall numbers through the pimas graph, and (b) leave the real
 * model UNTOUCHED after a preview (free rollback). Bundled with esbuild and run in
 * Node — no DOM. Also exercises the agent bridge's speculate + explain.
 */
import { createWallModel } from "./reactive-model.js";
import { LUNAR_REGOLITH_SEED } from "./scenarios.js";
import { createLaunchEconomicsModel } from "./launch-economics-model.js";
import { createPowerBudgetModel } from "./power-budget-model.js";
import { createProbeModel } from "./probe-sim-model.js";
import { createMissionModel } from "./mission-model.js";
import { createMultiProbeModel } from "./multi-probe-model.js";

let failures = 0;
const ok = (cond: boolean, msg: string) => {
  console.log(`${cond ? "✔" : "✗ FAIL"} ${msg}`);
  if (!cond) failures++;
};
const near = (a: number | null, b: number, eps: number, msg: string) =>
  ok(a !== null && Math.abs((a as number) - b) < eps, `${msg} (got ${a}, want ~${b})`);

const m = createWallModel(LUNAR_REGOLITH_SEED);

// Baseline through the reactive graph matches Python ground truth.
near(m.closureRatio(), 0.970833, 1e-4, "reactive closure = 0.9708");
near(m.sim().time_to_target_days, 10512.2892, 1e-1, "reactive time-to-target = 10512d");
ok(m.chipsAreLocal() === false, "chips start as imported vitamins");
ok(m.lateRegime() === "resupply-limited", "baseline late regime is resupply-limited");

// L3: speculate the electronics wall — exact after-state, nothing committed.
const { before, after } = m.previewChipsLocal();
near(before.time_to_target_days, 10512.2892, 1e-1, "preview.before = 10512d");
near(after.time_to_target_days, 6350.4485, 1e-1, "preview.after = 6350d (chips local wins)");
ok(m.chipsAreLocal() === false, "AFTER preview, real model still untouched (rollback)");
near(m.sim().time_to_target_days, 10512.2892, 1e-1, "AFTER preview, live sim unchanged");

// Commit for real, then the live graph reflects it.
m.commitChipsLocal();
ok(m.chipsAreLocal() === true, "after commit, chips are local");
near(m.sim().time_to_target_days, 6350.4485, 1e-1, "after commit, live sim = 6350d");
m.restoreChips();
near(m.sim().time_to_target_days, 10512.2892, 1e-1, "after restore, back to 10512d");

// Agent bridge: speculate returns exact scalars WITHOUT committing; explain records cause.
const spec = m.bridge.speculate("makeChipsLocal") as Record<string, unknown>;
near(spec.time_to_target_days as number, 6350.4485, 1e-1, "bridge.speculate time-to-target = 6350d");
ok(m.chipsAreLocal() === false, "bridge.speculate did not commit");
m.bridge.call("makeChipsLocal");
const cause = m.bridge.explain();
ok(!!cause && cause.action === "makeChipsLocal", "explain() records the action");
ok(!!cause && cause.writes.some((w) => w.includes("producible_locally")), `explain() names the field writes: ${cause?.writes.join(", ")}`);
ok(!!cause && cause.changed.includes("time_to_target_days"), `explain() names changed outputs: ${cause?.changed.join(", ")}`);

// 1 MW backfire through the graph.
m.restoreChips();
m.params.power.set(1000);
const bf = m.previewChipsLocal();
ok(bf.after.time_to_target_days === null, "at 1 MW, making chips locally never reaches target (backfire)");

m.dispose();

// Launch-economics surface: the reactive model recomputes leverage on a signal change.
const le = createLaunchEconomicsModel();
const lev0 = le.comparison().massLeverage;
le.params[0].set(100); // closure -> 100%
ok(le.comparison().massLeverage > lev0, "raising closure raises launch-mass leverage (reactive)");
near(le.comparison().massLeverage, le.params[1].get() / le.params[2].get(), 1e-6, "at full closure, leverage = target/seed");

// Power-budget surface: throughput responds to the compute-share signal.
const pb = createPowerBudgetModel();
const flops0 = pb.outputs().computeFlops;
pb.params[1].set(40); // compute share 20% -> 40%
ok(pb.outputs().computeFlops > flops0, "raising compute share raises throughput (reactive)");
near(pb.outputs().brainEquivalents, pb.outputs().computeFlops / 1e18, 1e-9, "brain-equivalents = flops / 1e18");

// Probe surface: delivered power falls as 1/d^2 as the probe moves outward.
const pr = createProbeModel();
const p1 = pr.outputs().deliveredPowerW;
pr.params[0].set(2.0); // distance 1 AU -> 2 AU
near(pr.outputs().deliveredPowerW, p1 / 4, 1e-6 * p1, "at 2x distance, delivered power is quartered (reactive)");

// Mission surface: the end-to-end fold reacts to the knobs, and starves when the
// probe is moved far from the Sun (the whole point of the follow-along).
const mi = createMissionModel();
near(mi.outputs().closureRatio, 0.970833, 1e-4, "mission closure = 0.9708 (through the graph)");
ok(mi.outputs().reachesTarget === true, "mission reaches target near Earth (1 AU baseline)");
const near1 = mi.outputs().deliveredPowerW;
mi.params[0].set(2.0); // distance 1 -> 2 AU
near(mi.outputs().deliveredPowerW, near1 / 4, 1e-6 * near1, "mission delivered power quarters at 2x distance (reactive)");
mi.params[0].set(30.0); // far out -> power-starved
ok(mi.outputs().reachesTarget === false, "mission is power-starved and never replicates at 30 AU");
mi.params[0].set(1.0);
mi.params[1].set(90); // all remaining power to compute -> manufacturing starved
ok(mi.outputs().manufacturingW === 0 && mi.outputs().reachesTarget === false, "all power to compute stalls the factory (reactive)");

// Fleet surface: the reactive fold grows a fleet near the Sun, the scrubber selects a
// snapshot, and pushing the start distance out trips the spatial power wall.
const fl = createMultiProbeModel();
ok(fl.result().finalPopulation > 1, "fleet grows past one probe near the Sun (reactive)");
ok(fl.snap().day === fl.durationDays, "scrubber starts at the final day");
fl.scrub.set(0);
ok(fl.snap().population === 1 && fl.snap().day === 0, "scrub to day 0 shows the single seed probe");
fl.params[0].set(30); // start distance 1 -> 30 AU
const farPop = fl.result().finalPopulation;
fl.params[0].set(1);
ok(fl.result().finalPopulation > farPop, "starting far from the Sun yields a smaller fleet (spatial power wall, reactive)");
fl.params[1].set(0); // vitamin pool -> 0 t
ok(fl.result().finalPopulation === 1 && fl.result().binding.vitaminLimited === true, "zero vitamins → no children (electronics wall)");

console.log(failures === 0 ? "\nALL SMOKE CHECKS PASS" : `\n${failures} FAILURES`);
if (failures > 0) process.exit(1);
