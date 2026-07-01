/**
 * The closure-sim model, expressed as a pimas reactive graph.
 *
 * This is the whole point of the exercise: the factory's bill-of-materials is a
 * `createStore` (so a hypothetical "make the chips locally" edit is a copy-on-write
 * shadow write), the replication assumptions are signals (the sliders), and every
 * result — closure, doubling time, the binding regime, the growth trajectory — is
 * a `createMemo` over the SAME pure functions the Python CLI runs. Given that, the
 * three agent-native powers fall out for free:
 *
 *   • SUBSCRIBE  — the DOM reads the memos directly; drag a slider, only the outputs
 *                  that actually depend on it re-render.
 *   • SPECULATE  — `previewChipsLocal()` runs the electronics-wall what-if against a
 *                  SHADOW of the graph (`speculate`): the exact after-state, computed
 *                  by re-running the real model, with NOTHING committed. Free rollback.
 *   • EXPLAIN    — `explainRegime()` reads the live model to say WHY growth is capped
 *                  (which of the three ceilings binds), and the agent bridge records
 *                  the field-level causal chain of a committed action.
 */
import { createSignal, createMemo, speculate, untrack } from "pimas";
import type { Accessor, Setter } from "pimas";
import { createStore, onStoreWrite } from "pimas/store";
import { createAgentBridge } from "pimas/agent";
import type { AgentBridge } from "pimas/agent";
import {
  ELECTRONICS_CATEGORIES,
  Regime,
  computeClosure,
  simulate,
} from "./model.js";
import type { Factory, ReplicationParams, Regime as RegimeT, SimResult, Subsystem } from "./model.js";

export interface ParamSignal {
  get: Accessor<number>;
  set: Setter<number>;
  min: number;
  max: number;
  step: number;
  label: string;
  unit: string;
}

export interface WallModel {
  factoryName: string;
  subsystems: Accessor<readonly Subsystem[]>;
  params: Record<string, ParamSignal>;
  closureRatio: Accessor<number>;
  sim: Accessor<SimResult>;
  lateRegime: Accessor<RegimeT>;
  chipsAreLocal: Accessor<boolean>;
  electronicsMassShare: number;
  /** L3: the electronics-wall what-if against a shadow graph — nothing commits. */
  previewChipsLocal: () => { before: SimResult; after: SimResult };
  /** Commit the toggle for real (a store write the UI then re-renders from). */
  commitChipsLocal: () => void;
  restoreChips: () => void;
  reset: () => void;
  /** A causal, model-derived sentence: why growth is capped where it is. */
  explainRegime: (s: SimResult) => string;
  bridge: AgentBridge;
  dispose: () => void;
}

const lateRegimeOf = (s: SimResult): RegimeT =>
  s.regime_timeline.length
    ? s.regime_timeline[s.regime_timeline.length - 1].regime
    : Regime.MATERIAL;

const fmtDays = (d: number | null): string =>
  d === null ? "never" : `${(d / 365).toFixed(1)} yr`;

export function createWallModel(initialFactory: Factory): WallModel {
  const rep0 = initialFactory.replication;
  if (!rep0) throw new Error("scenario has no replication params");

  // Bill of materials in a store — the copy-on-write speculation surface.
  const [store, setStore] = createStore<{ subsystems: Subsystem[] }>({
    subsystems: initialFactory.subsystems.map((s) => ({ ...s, processes: [...s.processes] })),
  });

  // Replication assumptions as signals — the sliders.
  const mk = (v: number): [Accessor<number>, Setter<number>] => createSignal(v);
  const [power, setPower] = mk(rep0.available_power_kw);
  const [buildRate, setBuildRate] = mk(rep0.local_build_rate_kg_per_day);
  const [resupplyMass, setResupplyMass] = mk(rep0.vitamin_resupply_mass_kg);
  const [cadence, setCadence] = mk(rep0.resupply_cadence_days);
  const [target, setTarget] = mk(rep0.target_output_kg_per_day);
  const [seedMass, setSeedMass] = mk(rep0.seed_mass_kg);

  const params: Record<string, ParamSignal> = {
    power: { get: power, set: setPower, min: 250, max: 12000, step: 250, label: "Available power", unit: "kW" },
    resupplyMass: { get: resupplyMass, set: setResupplyMass, min: 0, max: 500, step: 10, label: "Vitamin resupply / delivery", unit: "kg" },
    cadence: { get: cadence, set: setCadence, min: 7, max: 180, step: 1, label: "Resupply cadence", unit: "days" },
    buildRate: { get: buildRate, set: setBuildRate, min: 2, max: 100, step: 1, label: "Seed build rate", unit: "kg/day" },
    seedMass: { get: seedMass, set: setSeedMass, min: 2000, max: 40000, step: 500, label: "Seed mass (landed)", unit: "kg" },
    target: { get: target, set: setTarget, min: 50, max: 3000, step: 50, label: "Output goal", unit: "kg/day" },
  };

  const repParams = createMemo<ReplicationParams>(() => ({
    seed_mass_kg: seedMass(),
    local_build_rate_kg_per_day: buildRate(),
    vitamin_resupply_mass_kg: resupplyMass(),
    resupply_cadence_days: cadence(),
    available_power_kw: power(),
    target_output_kg_per_day: target(),
    duration_days: rep0.duration_days,
    dt_days: rep0.dt_days,
  }));

  // Assemble the factory from the live store (field reads inside simulate/closure
  // are what actually get tracked by the memos below).
  const currentFactory = (): Factory => ({
    name: initialFactory.name,
    subsystems: store.subsystems as unknown as Subsystem[],
    replication: null,
  });

  const closureMemo = createMemo(() => computeClosure(currentFactory()));
  const sim = createMemo(() => simulate(currentFactory(), repParams()));
  const closureRatio = createMemo(() => closureMemo().closure_ratio);
  const lateRegime = createMemo(() => lateRegimeOf(sim()));

  // Which subsystems are electronics (static — categories don't change).
  const elecIndices = initialFactory.subsystems
    .map((s, i) => ({ s, i }))
    .filter(({ s }) => ELECTRONICS_CATEGORIES.has(s.category))
    .map(({ i }) => i);
  const elecOriginal = new Map(elecIndices.map((i) => [i, initialFactory.subsystems[i].producible_locally]));
  const elecMass = elecIndices.reduce((a, i) => a + initialFactory.subsystems[i].mass_kg, 0);
  const totalMass = initialFactory.subsystems.reduce((a, s) => a + s.mass_kg, 0);

  const chipsAreLocal = createMemo(() =>
    elecIndices.every((i) => (store.subsystems[i] as Subsystem).producible_locally),
  );

  const setChips = (local: boolean) =>
    elecIndices.forEach((i) => setStore("subsystems", i, "producible_locally", local));

  // L3 — the electronics wall, run as a SHADOW what-if. `before` is the live
  // committed model; `after` is computed by applying the toggle inside speculate
  // and re-reading the sim memo against the shadow graph. On return the real
  // store is untouched (chipsAreLocal() is still whatever it was).
  const previewChipsLocal = (): { before: SimResult; after: SimResult } => {
    const before = untrack(() => sim());
    const after = speculate(
      () => setChips(true),
      () => sim(),
    );
    return { before, after };
  };

  const commitChipsLocal = () => setChips(true);
  const restoreChips = () => elecIndices.forEach((i) => setStore("subsystems", i, "producible_locally", elecOriginal.get(i)!));

  const reset = () => {
    setPower(rep0.available_power_kw);
    setBuildRate(rep0.local_build_rate_kg_per_day);
    setResupplyMass(rep0.vitamin_resupply_mass_kg);
    setCadence(rep0.resupply_cadence_days);
    setTarget(rep0.target_output_kg_per_day);
    setSeedMass(rep0.seed_mass_kg);
    restoreChips();
  };

  const explainRegime = (s: SimResult): string => {
    const regime = lateRegimeOf(s);
    const C = s.closure_ratio;
    if (regime === Regime.RESUPPLY) {
      return `Resupply-limited. Vitamins arrive at a fixed trickle, so at ${(C * 100).toFixed(1)}% closure growth is capped at R/(1−C) = ${s.resupply_ceiling_kg_per_day.toFixed(0)} kg/day. Push closure toward 100% and this ceiling climbs toward infinity — that is the only escape.`;
    }
    if (regime === Regime.ENERGY) {
      return `Energy-limited. Making its own chips raised the energy cost per kg so far that ${s.energy_cap_kg_per_day.toFixed(0)} kg/day is all the available power can produce locally. The factory runs out of electricity before it runs out of parts — the backfire.`;
    }
    return `Material-limited (still exponential). Local production α·F is the binding path and hasn't yet hit a fixed ceiling — the factory is compounding. Doubling time ≈ ${s.empirical_doubling_time_days ? s.empirical_doubling_time_days.toFixed(0) + " days" : "n/a"}.`;
  };

  // The SAME model, projected as an agent-facing surface (the pivot's thesis made
  // literal): scalar outputs are exposed/subscribable, actions are callable, and
  // `bridge.speculate`/`bridge.explain` give an agent exact what-if + field-level
  // causal provenance — with zero bespoke wiring beyond this block.
  const bridge = createAgentBridge(
    (r) => {
      r.expose("closure_ratio", () => sim().closure_ratio, { description: "mass fraction the factory can build locally" });
      r.expose("time_to_target_days", () => sim().time_to_target_days, { description: "days to reach the output goal (null = never)" });
      r.expose("empirical_doubling_days", () => sim().empirical_doubling_time_days);
      r.expose("final_output_kg_per_day", () => sim().final_output_kg_per_day);
      r.expose("binding_regime", () => lateRegimeOf(sim()), { description: "which ceiling caps growth: material/energy/resupply" });
      r.expose("resupply_ceiling_kg_per_day", () => sim().resupply_ceiling_kg_per_day);
      r.expose("energy_cap_kg_per_day", () => sim().energy_cap_kg_per_day);
      r.expose("chips_are_local", () => chipsAreLocal());
      r.action("makeChipsLocal", () => commitChipsLocal(), { params: [], readOnly: false, description: "Toggle every electronics subsystem to locally producible" });
      r.action("restoreChips", () => restoreChips(), { params: [], readOnly: false, description: "Revert electronics to imported vitamins" });
      r.action("setPowerKw", (kw) => setPower(Number(kw)), { params: ["kw"], description: "Set available power in kW" });
    },
    { writeTap: (record) => onStoreWrite((e) => record(e.path.join("."))) },
  );

  return {
    factoryName: initialFactory.name,
    subsystems: () => store.subsystems as unknown as readonly Subsystem[],
    params,
    closureRatio,
    sim,
    lateRegime,
    chipsAreLocal,
    electronicsMassShare: totalMass ? elecMass / totalMass : 0,
    previewChipsLocal,
    commitChipsLocal,
    restoreChips,
    reset,
    explainRegime,
    bridge,
    dispose: () => bridge.dispose(),
  };
}

export { fmtDays };
