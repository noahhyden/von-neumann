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
import { lightTimeYears, roundTripYears, rho, classifyRung } from "./coordination.js";
import type { Rung } from "./coordination.js";

/** Everything the coordination readout needs for the one star a human is inspecting. */
export interface HoverInfo {
  star: number;
  isOrigin: boolean;
  distPc: number;
  oneWayYears: number;
  roundTripYears: number;
  rho: number;
  rung: Rung;
}

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
  /** the star the pointer is over (index into the field), or null. §7: the reactive
   * graph scales with the one thing a human looks at, never with nStars. */
  hoverStar: Accessor<number | null>;
  setHoverStar: Setter<number | null>;
  /** the decision timescale τ (years) in ρ = latency/τ — a knob, default 1 yr [ESTIMATE]. */
  decisionTimescale: Accessor<number>;
  setDecisionTimescale: Setter<number>;
  /** light-time / ρ / rung for the hovered star relative to the homeworld, or null. */
  hoverInfo: Accessor<HoverInfo | null>;
}

export function createSwarmModel(): SwarmModel {
  const [nStars, setNStars] = createSignal(1200);
  const [offspring, setOffspring] = createSignal(2);
  const [probeSpeedKmS, setProbeSpeedKmS] = createSignal(9); // N&F powered cruise ≈ 9 km/s
  const [seed, setSeed] = createSignal(1);
  const [scrubYear, setScrubYear] = createSignal(0);
  const [playing, setPlaying] = createSignal(false);
  const [policy, setPolicy] = createSignal<Policy>("powered");
  const [hoverStar, setHoverStar] = createSignal<number | null>(null);
  const [decisionTimescale, setDecisionTimescale] = createSignal(1); // yr, [ESTIMATE] knob

  // All four feed the `result` memo → each `set` re-runs the whole simulateSwarm fold.
  // commitOnRelease: a drag then triggers one re-sim on release, not one per pixel.
  const params: ParamSignal[] = [
    { get: nStars, set: setNStars, min: 50, max: 5000, step: 50, label: "Stars in the field", unit: "", commitOnRelease: true },
    { get: offspring, set: setOffspring, min: 0, max: 6, step: 1, label: "Offspring per settlement", unit: "", commitOnRelease: true },
    { get: probeSpeedKmS, set: setProbeSpeedKmS, min: 1, max: 100, step: 1, label: "Powered speed", unit: "km/s", commitOnRelease: true },
    { get: seed, set: setSeed, min: 1, max: 9999, step: 1, label: "Galaxy seed", unit: "", commitOnRelease: true },
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

  // The coordination readout for the hovered star — reads the fold's position buffers,
  // classifies the light-time to the homeworld into a rung. Recomputes only when the
  // hover, the run, or τ changes; independent of nStars (§7).
  const hoverInfo = createMemo<HoverInfo | null>(() => {
    const i = hoverStar();
    if (i === null) return null;
    const r = result();
    if (i < 0 || i >= r.xs.length) return null;
    const dx = r.xs[i] - r.xs[r.origin];
    const dy = r.ys[i] - r.ys[r.origin];
    const dz = r.zs[i] - r.zs[r.origin];
    const distPc = Math.sqrt(dx * dx + dy * dy + dz * dz);
    const rtt = roundTripYears(distPc);
    return {
      star: i,
      isOrigin: i === r.origin,
      distPc,
      oneWayYears: lightTimeYears(distPc),
      roundTripYears: rtt,
      rho: rho(distPc, decisionTimescale()),
      rung: classifyRung(rtt),
    };
  });

  return {
    params, result, maxYear, scrubYear, setScrubYear, playing, setPlaying, policy, setPolicy, settledAt,
    hoverStar, setHoverStar, decisionTimescale, setDecisionTimescale, hoverInfo,
  };
}
