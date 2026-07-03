/**
 * The probe-sim model as a pimas reactive graph - the fourth surface.
 *
 * Signals for the probe's array and where it is; a memo over the parity-tested TS
 * port (`probe-sim.ts`) for delivered power and the compute headroom that power
 * buys. Same shape as the other lightweight surfaces: signals + one memo.
 */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import type { ParamSignal } from "./reactive-model.js";
import { computeHeadroomAt, solarArrayPowerW, solarIrradianceWM2 } from "./probe-sim.js";

export interface ProbeOutputs {
  irradianceWM2: number;
  deliveredPowerW: number;
  computePowerW: number;
  computeFlops: number;
  brainEquivalents: number;
}

export interface ProbeModel {
  params: ParamSignal[];
  distanceAu: Accessor<number>;
  outputs: Accessor<ProbeOutputs>;
}

export function createProbeModel(): ProbeModel {
  const [distanceAu, setDistanceAu] = createSignal(1.0);
  const [areaM2, setAreaM2] = createSignal(50);
  const [efficiencyPct, setEfficiencyPct] = createSignal(30);
  const [computePct, setComputePct] = createSignal(20);
  const [gflopsPerW, setGflopsPerW] = createSignal(100);

  const params: ParamSignal[] = [
    { get: distanceAu, set: setDistanceAu, min: 0.3, max: 40, step: 0.1, label: "Heliocentric distance", unit: "AU" },
    { get: areaM2, set: setAreaM2, min: 1, max: 500, step: 1, label: "Array area", unit: "m²" },
    { get: efficiencyPct, set: setEfficiencyPct, min: 5, max: 40, step: 1, label: "Array efficiency", unit: "%" },
    { get: computePct, set: setComputePct, min: 0, max: 100, step: 1, label: "Compute share", unit: "%" },
    { get: gflopsPerW, set: setGflopsPerW, min: 1, max: 1000, step: 1, label: "Compute efficiency", unit: "GFLOP/W" },
  ];

  const outputs = createMemo<ProbeOutputs>(() => {
    const array = { areaM2: areaM2(), efficiency: efficiencyPct() / 100 };
    const headroom = computeHeadroomAt(array, distanceAu(), {
      computeFraction: computePct() / 100,
      efficiencyFlopsPerW: gflopsPerW() * 1e9,
    });
    return {
      irradianceWM2: solarIrradianceWM2(distanceAu()),
      deliveredPowerW: solarArrayPowerW(array, distanceAu()),
      computePowerW: headroom.computePowerW,
      computeFlops: headroom.computeFlops,
      brainEquivalents: headroom.brainEquivalents,
    };
  });

  return { params, distanceAu, outputs };
}
