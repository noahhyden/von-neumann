/** The multi-probe model as a pimas reactive graph - the sixth surface, a live fleet. */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import { param, type ParamSignal } from "./reactive-model.js";
import { paramsFromFactory, simulateFleet } from "./multi-probe.js";
import type { FleetResult, FleetStep } from "./multi-probe.js";
import { LUNAR_REGOLITH_SEED } from "./scenarios.js";

const DURATION_DAYS = 14600; // 40 years
const DT_DAYS = 20; // 731 steps - fast to re-run, plenty of resolution for a ~582-day cadence
const SEED = 0x9e3779b9;

export interface MultiProbeModel {
  params: ParamSignal[];
  scrub: ParamSignal;
  result: Accessor<FleetResult>;
  snap: Accessor<FleetStep>;
  durationDays: number;
  factoryName: string;
}

export function createMultiProbeModel(): MultiProbeModel {
  const startDistanceAu = param(1.0, { min: 0.3, max: 40, step: 0.1, label: "Start distance", unit: "AU" });
  const vitaminPoolT = param(1000, { min: 0, max: 2000, step: 5, label: "Vitamin pool", unit: "t" }); // tonnes
  const dispersalFactor = param(1.3, { min: 1.0, max: 2.0, step: 0.05, label: "Dispersal", unit: "×/gen" });
  const maxProbes = param(64, { min: 2, max: 200, step: 1, label: "Fleet cap", unit: "probes" });
  const transitDays = param(365, { min: 0, max: 1460, step: 5, label: "Transit time", unit: "d" });
  const jitterPct = param(0, { min: 0, max: 60, step: 1, label: "Transit jitter", unit: "%" });
  const scrubDay = param(DURATION_DAYS, { min: 0, max: DURATION_DAYS, step: DT_DAYS, label: "Day (scrub the mission)", unit: "d" });

  const params: ParamSignal[] = [
    startDistanceAu,
    vitaminPoolT,
    dispersalFactor,
    maxProbes,
    transitDays,
    jitterPct,
  ];

  const scrub: ParamSignal = scrubDay;

  const result = createMemo<FleetResult>(() =>
    simulateFleet(
      paramsFromFactory(LUNAR_REGOLITH_SEED, {
        startDistanceAu: startDistanceAu.get(),
        vitaminPoolKg: vitaminPoolT.get() * 1000,
        dispersalFactor: dispersalFactor.get(),
        maxProbes: maxProbes.get(),
        transitDays: transitDays.get(),
        transitJitterFrac: jitterPct.get() / 100,
      }),
      { seed: SEED, durationDays: DURATION_DAYS, dtDays: DT_DAYS },
    ),
  );

  const snap = createMemo<FleetStep>(() => {
    const steps = result().steps;
    const idx = Math.min(steps.length - 1, Math.max(0, Math.round(scrubDay.get() / DT_DAYS)));
    return steps[idx];
  });

  return { params, scrub, result, snap, durationDays: DURATION_DAYS, factoryName: LUNAR_REGOLITH_SEED.name };
}
