/**
 * Light-speed coordination limits — the pure, testable core (Layer A, no pimas).
 *
 * A swarm coordinates by sharing state, and state travels no faster than light. What
 * matters is the ratio ρ = (round-trip latency) / (decision timescale), where the
 * latency is fixed by geometry: round-trip = 2·d/c. As ρ climbs, a swarm walks down a
 * *staircase* of coordination modes — real-time closed-loop → move-and-wait →
 * supervisory → delay-tolerant → fully independent colonies — and it does so in jumps,
 * not smoothly (the consensus-stability wall, Olfati-Saber & Murray 2004).
 *
 * This module turns an inter-node distance in parsecs into that classification. Every
 * number is sourced in swarm/REFERENCES.md ("Coordination-horizon visualization"). It is
 * framework-agnostic and imports no pimas — the reactive model (`swarm-model.ts`) and the
 * canvas (`main.tsx`) are the skin over it.
 *
 * The rung *transitions* are sourced from the teleoperation/networking literature; the
 * round-number bucket edges (1 s / 1 min / 1 hr / 1 yr of round-trip latency) are a
 * presentation choice, tagged [ESTIMATE] in REFERENCES.md.
 */
import { C_PC_PER_YEAR } from "./swarm.ts";

/** Julian year in seconds — matches the value C_PC_PER_YEAR is derived from (swarm.ts). */
export const SEC_PER_YEAR = 3.15576e7;

/** One-way light-travel time (years) across a distance in parsecs. */
export function lightTimeYears(distPc: number): number {
  return distPc / C_PC_PER_YEAR;
}

/** Round-trip latency (years): a signal out and its reply back, 2·d/c. */
export function roundTripYears(distPc: number): number {
  return (2 * distPc) / C_PC_PER_YEAR;
}

/**
 * The coordination ratio ρ = round-trip latency / decision timescale (both in years).
 * ρ ≪ 1: news arrives while still current (tight coordination possible). ρ ≳ 1: the world
 * changes faster than word of it arrives (tight coordination physically impossible).
 */
export function rho(distPc: number, decisionTimescaleYears: number): number {
  return roundTripYears(distPc) / decisionTimescaleYears;
}

export interface Rung {
  /** stable machine key, low index = fast/tight coordination. */
  key: "realtime" | "movewait" | "supervisory" | "dtn" | "independent";
  /** rung index 0..4 — monotonic in latency, handy for comparisons. */
  index: number;
  /** the coordination mode this rung permits. */
  label: string;
  /** a real-world analog at roughly this latency (legend anchor). */
  analog: string;
  /** who is actually deciding at this rung. */
  who: string;
  /** hex color for the legend + canvas cue (green→red as coordination degrades). */
  color: string;
  /** upper round-trip-latency bound of this rung, in SECONDS (Infinity for the top rung). */
  maxRoundTripSec: number;
}

/**
 * The staircase, ordered fastest→slowest. Bounds are round-trip latency in seconds; a
 * distance falls in the first rung whose bound it does not exceed. Sourced in
 * swarm/REFERENCES.md.
 */
export const RUNGS: Rung[] = [
  { key: "realtime",    index: 0, label: "Real-time closed-loop", analog: "LEO",           who: "central controller, in the loop", color: "#4ade80", maxRoundTripSec: 1 },
  { key: "movewait",    index: 1, label: "Move-and-wait",         analog: "Earth–Moon",    who: "central, but degraded",           color: "#88c7d6", maxRoundTripSec: 60 },
  { key: "supervisory", index: 2, label: "Supervisory",           analog: "Mars",          who: "home sets goals; node executes",  color: "#e8a33d", maxRoundTripSec: 3600 },
  { key: "dtn",         index: 3, label: "Delay-tolerant",        analog: "Saturn / 10+ AU", who: "node; network reconciles late", color: "#e07b39", maxRoundTripSec: SEC_PER_YEAR },
  { key: "independent", index: 4, label: "Independent colonies",  analog: "Proxima +",     who: "node only; priors set pre-launch", color: "#e0555f", maxRoundTripSec: Infinity },
];

/** Classify a round-trip latency (years) into its coordination rung. */
export function classifyRung(roundTripYearsValue: number): Rung {
  const rttSec = roundTripYearsValue * SEC_PER_YEAR;
  for (const rung of RUNGS) {
    if (rttSec <= rung.maxRoundTripSec) return rung;
  }
  return RUNGS[RUNGS.length - 1];
}

/** Convenience: the rung a distance in parsecs falls into. */
export function rungForDistancePc(distPc: number): Rung {
  return classifyRung(roundTripYears(distPc));
}
