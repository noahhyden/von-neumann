/**
 * The power-budget model as a pimas reactive graph — the third surface.
 *
 * Sliders are signals; the compute outputs are a memo over the parity-tested TS port
 * (`power-budget.ts`). Same shape as the launch-economics model: signals + one memo,
 * no store/speculate/bridge needed.
 */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import type { ParamSignal } from "./reactive-model.js";
import { brainEquivalents, computeCapacityFlops, landauerLimitJPerBit } from "./power-budget.js";

export interface PowerBudgetOutputs {
  computeW: number;
  computeFlops: number;
  brainEquivalents: number;
  energyPerFlopJ: number;
  landauerJPerBit: number;
  headroomOverLandauer: number; // energy/FLOP ÷ Landauer J/bit (orders above the floor)
}

export interface PowerBudgetModel {
  params: ParamSignal[];
  outputs: Accessor<PowerBudgetOutputs>;
}

export function createPowerBudgetModel(): PowerBudgetModel {
  const [totalW, setTotalW] = createSignal(4000);
  const [computePct, setComputePct] = createSignal(20);
  const [gflopsPerW, setGflopsPerW] = createSignal(100); // 100 GFLOP/W = 1e11 FLOPS/W
  const [temperatureK, setTemperatureK] = createSignal(300);

  const params: ParamSignal[] = [
    { get: totalW, set: setTotalW, min: 100, max: 20000, step: 100, label: "Total power", unit: "W" },
    { get: computePct, set: setComputePct, min: 0, max: 100, step: 1, label: "Compute share", unit: "%" },
    { get: gflopsPerW, set: setGflopsPerW, min: 1, max: 1000, step: 1, label: "Compute efficiency", unit: "GFLOP/W" },
    { get: temperatureK, set: setTemperatureK, min: 100, max: 500, step: 5, label: "Radiator temperature", unit: "K" },
  ];

  const outputs = createMemo<PowerBudgetOutputs>(() => {
    const computeW = totalW() * (computePct() / 100);
    const efficiencyFlopsPerW = gflopsPerW() * 1e9;
    const computeFlops = computeCapacityFlops(computeW, efficiencyFlopsPerW);
    const energyPerFlopJ = 1 / efficiencyFlopsPerW;
    const landauerJPerBit = landauerLimitJPerBit(temperatureK());
    return {
      computeW,
      computeFlops,
      brainEquivalents: brainEquivalents(computeFlops),
      energyPerFlopJ,
      landauerJPerBit,
      headroomOverLandauer: energyPerFlopJ / landauerJPerBit,
    };
  });

  return { params, outputs };
}
