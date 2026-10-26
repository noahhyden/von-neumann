/**
 * The launch-economics model as a pimas reactive graph - the second surface.
 *
 * Sliders are signals; the launch comparison is a memo over the pure, parity-tested
 * TS port (`launch-economics.ts`). Same pattern as `reactive-model.ts`, minus the
 * store/speculate/agent-bridge machinery this simpler model doesn't need.
 */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import { param, type ParamSignal } from "./reactive-model.js";
import { comparisonFromClosure } from "./launch-economics.js";
import type { ReplicationLaunchComparison } from "./launch-economics.js";

export interface LaunchModel {
  params: ParamSignal[];
  comparison: Accessor<ReplicationLaunchComparison>;
  closurePct: Accessor<number>;
}

export function createLaunchEconomicsModel(): LaunchModel {
  const closurePct = param(70, { min: 0, max: 100, step: 1, label: "Mass closure", unit: "%" });
  const targetTonnes = param(1000, { min: 10, max: 5000, step: 10, label: "Target installed mass", unit: "t" });
  const seedTonnes = param(10, { min: 1, max: 200, step: 1, label: "Seed mass (landed)", unit: "t" });
  const costPerKg = param(3000, { min: 100, max: 5000, step: 50, label: "Launch cost", unit: "$/kg" });

  const params: ParamSignal[] = [
    closurePct,
    targetTonnes,
    seedTonnes,
    costPerKg,
  ];

  const comparison = createMemo(() =>
    comparisonFromClosure({
      closureRatio: closurePct.get() / 100,
      targetInstalledMassKg: targetTonnes.get() * 1000,
      seedMassKg: seedTonnes.get() * 1000,
      costPerKgUsd: costPerKg.get(),
    }),
  );

  return { params, comparison, closurePct: closurePct.get };
}
