/**
 * The multi-probe model as a pimas reactive graph - the sixth surface, a live fleet.
 *
 * Knob signals + a memo over the parity-tested TS port (`multi-probe.ts`) that reruns
 * the whole deterministic fold, plus a "day" scrubber signal that selects one snapshot
 * from the run's timeline - drag it to watch the fleet grow and disperse. The fold is
 * cheap (tens of probes, a few hundred steps), so re-running on every knob change is
 * fine; no store/speculate needed (same lightweight shape as the other surfaces).
 */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import type { ParamSignal } from "./reactive-model.js";
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
  const [startDistanceAu, setStartDistanceAu] = createSignal(1.0);
  const [vitaminPoolT, setVitaminPoolT] = createSignal(1000); // tonnes
  const [dispersalFactor, setDispersalFactor] = createSignal(1.3);
  const [maxProbes, setMaxProbes] = createSignal(64);
  const [transitDays, setTransitDays] = createSignal(365);
  const [jitterPct, setJitterPct] = createSignal(0);
  const [scrubDay, setScrubDay] = createSignal(DURATION_DAYS);

  const params: ParamSignal[] = [
    { get: startDistanceAu, set: setStartDistanceAu, min: 0.3, max: 40, step: 0.1, label: "Start distance", unit: "AU" },
    { get: vitaminPoolT, set: setVitaminPoolT, min: 0, max: 2000, step: 5, label: "Vitamin pool", unit: "t" },
    { get: dispersalFactor, set: setDispersalFactor, min: 1.0, max: 2.0, step: 0.05, label: "Dispersal", unit: "×/gen" },
    { get: maxProbes, set: setMaxProbes, min: 2, max: 200, step: 1, label: "Fleet cap", unit: "probes" },
    { get: transitDays, set: setTransitDays, min: 0, max: 1460, step: 5, label: "Transit time", unit: "d" },
    { get: jitterPct, set: setJitterPct, min: 0, max: 60, step: 1, label: "Transit jitter", unit: "%" },
  ];

  const scrub: ParamSignal = {
    get: scrubDay, set: setScrubDay, min: 0, max: DURATION_DAYS, step: DT_DAYS, label: "Day (scrub the mission)", unit: "d",
  };

  const result = createMemo<FleetResult>(() =>
    simulateFleet(
      paramsFromFactory(LUNAR_REGOLITH_SEED, {
        startDistanceAu: startDistanceAu(),
        vitaminPoolKg: vitaminPoolT() * 1000,
        dispersalFactor: dispersalFactor(),
        maxProbes: maxProbes(),
        transitDays: transitDays(),
        transitJitterFrac: jitterPct() / 100,
      }),
      { seed: SEED, durationDays: DURATION_DAYS, dtDays: DT_DAYS },
    ),
  );

  const snap = createMemo<FleetStep>(() => {
    const steps = result().steps;
    const idx = Math.min(steps.length - 1, Math.max(0, Math.round(scrubDay() / DT_DAYS)));
    return steps[idx];
  });

  return { params, scrub, result, snap, durationDays: DURATION_DAYS, factoryName: LUNAR_REGOLITH_SEED.name };
}
