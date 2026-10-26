/**
 * The probe-sim model as a pimas reactive graph - the fourth surface.
 *
 * Signals for the probe's array and where it is; a memo over the parity-tested TS
 * port (`probe-sim.ts`) for delivered power and the compute headroom that power
 * buys. Same shape as the other lightweight surfaces: signals + one memo.
 */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import { param, type ParamSignal } from "./reactive-model.js";
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
  const distanceAu = param(1.0, { min: 0.3, max: 40, step: 0.1, label: "Heliocentric distance", unit: "AU" });
  const areaM2 = param(50, { min: 1, max: 500, step: 1, label: "Array area", unit: "m²" });
  const efficiencyPct = param(30, { min: 5, max: 40, step: 1, label: "Array efficiency", unit: "%" });
  const computePct = param(20, { min: 0, max: 100, step: 1, label: "Compute share", unit: "%" });
  const gflopsPerW = param(100, { min: 1, max: 1000, step: 1, label: "Compute efficiency", unit: "GFLOP/W" });

  const params: ParamSignal[] = [
    distanceAu,
    areaM2,
    efficiencyPct,
    computePct,
    gflopsPerW,
  ];

  const outputs = createMemo<ProbeOutputs>(() => {
    const array = { areaM2: areaM2.get(), efficiency: efficiencyPct.get() / 100 };
    const headroom = computeHeadroomAt(array, distanceAu.get(), {
      computeFraction: computePct.get() / 100,
      efficiencyFlopsPerW: gflopsPerW.get() * 1e9,
    });
    return {
      irradianceWM2: solarIrradianceWM2(distanceAu.get()),
      deliveredPowerW: solarArrayPowerW(array, distanceAu.get()),
      computePowerW: headroom.computePowerW,
      computeFlops: headroom.computeFlops,
      brainEquivalents: headroom.brainEquivalents,
    };
  });

  return { params, distanceAu: distanceAu.get, outputs };
}
