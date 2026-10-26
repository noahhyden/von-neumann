/**
 * The mission model as a pimas reactive graph - the fifth surface, the end-to-end
 * follow-along.
 *
 * Signals for the five knobs a viewer drags; one memo over the parity-tested TS port
 * (`mission.ts`) that recomputes the whole chain. Same lightweight shape as the other
 * composed surfaces (signals + one memo) - no store/speculate needed; the fold is
 * pure and cheap to re-run on every drag.
 *
 * The power split is derived so it can never over-allocate: housekeeping is fixed at
 * 10%, a single "power to compute" slider takes 0–90%, and manufacturing gets the
 * rest. Dragging compute up literally starves the factory - the point of the surface.
 */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import { param, type ParamSignal } from "./reactive-model.js";
import { defaultMissionScenario, runMission, DEFAULT_ARRAY_AREA_M2 } from "./mission.js";
import type { MissionResult } from "./mission.js";
import { LUNAR_REGOLITH_SEED } from "./scenarios.js";

const HOUSEKEEPING_PCT = 10; // fixed housekeeping share (thermal/comms/attitude)

export interface MissionModel {
  params: ParamSignal[];
  outputs: Accessor<MissionResult>;
  factoryName: string;
}

export function createMissionModel(): MissionModel {
  const distanceAu = param(1.0, { min: 0.3, max: 40, step: 0.1, label: "Heliocentric distance", unit: "AU" });
  const computeSharePct = param(20, { min: 0, max: 90, step: 1, label: "Power to compute", unit: "%" });
  const arrayAreaM2 = param(DEFAULT_ARRAY_AREA_M2, { min: 1000, max: 20000, step: 100, label: "Solar array area", unit: "m²" });
  const targetTonnes = param(1000, { min: 100, max: 5000, step: 10, label: "Target installed mass", unit: "t" });
  const costPerKgUsd = param(3000, { min: 100, max: 5000, step: 50, label: "Launch cost", unit: "$/kg" });

  const params: ParamSignal[] = [
    distanceAu,
    computeSharePct,
    arrayAreaM2,
    targetTonnes,
    costPerKgUsd,
  ];

  const outputs = createMemo<MissionResult>(() => {
    const compute = computeSharePct.get();
    const scenario = defaultMissionScenario(LUNAR_REGOLITH_SEED, {
      distanceAu: distanceAu.get(),
      arrayAreaM2: arrayAreaM2.get(),
      fractionCompute: compute / 100,
      fractionManufacturing: (100 - HOUSEKEEPING_PCT - compute) / 100,
      fractionHousekeeping: HOUSEKEEPING_PCT / 100,
      targetInstalledMassKg: targetTonnes.get() * 1000,
      costPerKgUsd: costPerKgUsd.get(),
    });
    return runMission(scenario);
  });

  return { params, outputs, factoryName: LUNAR_REGOLITH_SEED.name };
}
