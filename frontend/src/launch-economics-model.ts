/**
 * The launch-economics model as a pimas reactive graph - the second surface.
 *
 * Sliders are signals; the launch comparison is a memo over the pure, parity-tested
 * TS port (`launch-economics.ts`). Same pattern as `reactive-model.ts`, minus the
 * store/speculate/agent-bridge machinery this simpler model doesn't need.
 */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import type { ParamSignal } from "./reactive-model.js";
import { comparisonFromClosure } from "./launch-economics.js";
import type { ReplicationLaunchComparison } from "./launch-economics.js";

export interface LaunchModel {
  params: ParamSignal[];
  comparison: Accessor<ReplicationLaunchComparison>;
  closurePct: Accessor<number>;
}

export function createLaunchEconomicsModel(): LaunchModel {
  const [closurePct, setClosurePct] = createSignal(70);
  const [targetTonnes, setTargetTonnes] = createSignal(1000);
  const [seedTonnes, setSeedTonnes] = createSignal(10);
  const [costPerKg, setCostPerKg] = createSignal(3000);

  const params: ParamSignal[] = [
    { get: closurePct, set: setClosurePct, min: 0, max: 100, step: 1, label: "Mass closure", unit: "%" },
    { get: targetTonnes, set: setTargetTonnes, min: 10, max: 5000, step: 10, label: "Target installed mass", unit: "t" },
    { get: seedTonnes, set: setSeedTonnes, min: 1, max: 200, step: 1, label: "Seed mass (landed)", unit: "t" },
    { get: costPerKg, set: setCostPerKg, min: 100, max: 5000, step: 50, label: "Launch cost", unit: "$/kg" },
  ];

  const comparison = createMemo(() =>
    comparisonFromClosure({
      closureRatio: closurePct() / 100,
      targetInstalledMassKg: targetTonnes() * 1000,
      seedMassKg: seedTonnes() * 1000,
      costPerKgUsd: costPerKg(),
    }),
  );

  return { params, comparison, closurePct };
}
