/** Light-speed coordination limits (round-trip = 2d/c) as a pure, pimas-free core (Layer A); sourced in swarm/REFERENCES.md, whose 1 s / 1 min / 1 hr / 1 yr bucket edges are an [ESTIMATE] presentation choice. */
import { C_PC_PER_YEAR } from "./swarm.ts";

/** Julian year in seconds - matches the value C_PC_PER_YEAR is derived from (swarm.ts). */
export const SEC_PER_YEAR = 3.15576e7;

/** One-way light-travel time (years) across a distance in parsecs. */
export function lightTimeYears(distPc: number): number {
  return distPc / C_PC_PER_YEAR;
}

/** Round-trip latency (years): a signal out and its reply back, 2·d/c. */
export function roundTripYears(distPc: number): number {
  return (2 * distPc) / C_PC_PER_YEAR;
}

/** The coordination ratio ρ = round-trip latency / decision timescale (both in years). */
export function rho(distPc: number, decisionTimescaleYears: number): number {
  return roundTripYears(distPc) / decisionTimescaleYears;
}

export interface Rung {
  /** stable machine key, low index = fast/tight coordination. */
  key: "realtime" | "movewait" | "supervisory" | "dtn" | "independent";
  /** rung index 0..4 - monotonic in latency, handy for comparisons. */
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

/** The staircase, ordered fastest→slowest, with round-trip latency bounds in seconds sourced in swarm/REFERENCES.md. */
export const RUNGS: Rung[] = [
  { key: "realtime",    index: 0, label: "Real-time closed-loop", analog: "LEO",           who: "central controller, in the loop", color: "#8cb395", maxRoundTripSec: 1 },
  { key: "movewait",    index: 1, label: "Move-and-wait",         analog: "Earth–Moon",    who: "central, but degraded",           color: "#7fa9b5", maxRoundTripSec: 60 },
  { key: "supervisory", index: 2, label: "Supervisory",           analog: "Mars",          who: "home sets goals; node executes",  color: "#c79a5b", maxRoundTripSec: 3600 },
  { key: "dtn",         index: 3, label: "Delay-tolerant",        analog: "Saturn / 10+ AU", who: "node; network reconciles late", color: "#be8a5a", maxRoundTripSec: SEC_PER_YEAR },
  { key: "independent", index: 4, label: "Independent colonies",  analog: "Proxima +",     who: "node only; priors set pre-launch", color: "#c68278", maxRoundTripSec: Infinity },
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
