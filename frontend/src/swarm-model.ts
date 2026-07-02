/**
 * The swarm model as a pimas reactive graph — the seventh surface, a live settlement
 * front you can watch fill the galaxy.
 *
 * Knob signals + a memo over the parity-tested TS port (`swarm.ts`) that reruns the
 * deterministic fold, plus a "year" scrubber (and a play flag) that select a moment in
 * the run. The canvas draws the star field at the scrubbed year straight from the
 * result's per-star settlement years — no re-run while scrubbing (§7: rendering reads
 * the fold's buffers). Re-running only happens when a knob changes.
 */
import { createSignal, createMemo } from "pimas";
import type { Accessor, Setter } from "pimas";
import type { ParamSignal } from "./reactive-model.js";
import { simulateSwarm, SWARM_DEFAULTS } from "./swarm.js";
import type { SwarmResult, Policy } from "./swarm.js";

export interface SwarmModel {
  params: ParamSignal[];
  result: Accessor<SwarmResult>;
  maxYear: Accessor<number>;
  scrubYear: Accessor<number>;
  setScrubYear: Setter<number>;
  playing: Accessor<boolean>;
  setPlaying: Setter<boolean>;
  policy: Accessor<Policy>;
  setPolicy: Setter<Policy>;
  /** stars settled at or before the scrubbed year, and the front radius then. */
  settledAt: Accessor<{ count: number; frontPc: number }>;
}

export function createSwarmModel(): SwarmModel {
  const [nStars, setNStars] = createSignal(1200);
  const [offspring, setOffspring] = createSignal(2);
  const [probeSpeedKmS, setProbeSpeedKmS] = createSignal(9); // N&F powered cruise ≈ 9 km/s
  const [seed, setSeed] = createSignal(1);
  const [scrubYear, setScrubYear] = createSignal(0);
  const [playing, setPlaying] = createSignal(false);
  const [policy, setPolicy] = createSignal<Policy>("powered");

  const params: ParamSignal[] = [
    { get: nStars, set: setNStars, min: 50, max: 5000, step: 50, label: "Stars in the field", unit: "" },
    { get: offspring, set: setOffspring, min: 0, max: 6, step: 1, label: "Offspring per settlement", unit: "" },
    { get: probeSpeedKmS, set: setProbeSpeedKmS, min: 1, max: 100, step: 1, label: "Powered speed", unit: "km/s" },
    { get: seed, set: setSeed, min: 1, max: 9999, step: 1, label: "Galaxy seed", unit: "" },
  ];

  const KM_S_TO_C = 1 / 299792.458;
  const result = createMemo<SwarmResult>(() =>
    simulateSwarm(
      { ...SWARM_DEFAULTS, nStars: nStars(), offspringPerSettlement: offspring(), probeSpeedC: probeSpeedKmS() * KM_S_TO_C, policy: policy() },
      seed(),
    ),
  );

  const maxYear = createMemo<number>(() => {
    const steps = result().steps;
    return steps[steps.length - 1].year;
  });

  const settledAt = createMemo<{ count: number; frontPc: number }>(() => {
    const r = result();
    const y = scrubYear();
    let count = 0;
    let front = 0;
    const ox = r.xs[r.origin], oy = r.ys[r.origin], oz = r.zs[r.origin];
    for (let i = 0; i < r.settledYear.length; i++) {
      const sy = r.settledYear[i];
      if (sy >= 0 && sy <= y) {
        count++;
        const dx = r.xs[i] - ox, dy = r.ys[i] - oy, dz = r.zs[i] - oz;
        const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (d > front) front = d;
      }
    }
    return { count, frontPc: front };
  });

  return { params, result, maxYear, scrubYear, setScrubYear, playing, setPlaying, policy, setPolicy, settledAt };
}
