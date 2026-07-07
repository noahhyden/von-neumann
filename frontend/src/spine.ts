/**
 * The cross-scale spine: a faithful TS port of `spine/run.py`.
 *
 * Threads one closure-sim `Factory` through three scales - the single factory
 * (closure + replication, `model.ts`), the local fleet (`multi-probe.ts`), and the
 * galaxy (`swarm.ts`) - deriving the swarm's per-star manufacturing dwell
 * (`settleTimeYears`, once an ungrounded 0.0) from the same build physics the fleet
 * uses. Introduces no new numbers; every quantity traces to a module already ported and
 * parity-tested. Parity-guarded against the Python by `spine.test.ts` (Layer A).
 */
import { computeClosure, simulate, type Factory } from "./model.ts";
import { paramsFromFactory, simulateFleet, timeToBuildOneCopyDays } from "./multi-probe.ts";
import { simulateSwarm, SWARM_DEFAULTS, type Policy, type SwarmResult } from "./swarm.ts";

// 1 Julian year = 365.25 d = 3.15576e7 s - the same year basis the swarm uses for
// C_PC_PER_YEAR, so build-days -> years shares the swarm's clock. (3.15576e7 / 86400.)
export const DAYS_PER_JULIAN_YEAR = 365.25;

export interface SpineScenario {
  factory: Factory;
  nStars: number;
  offspringPerSettlement: number;
  policy: Policy;
  swarmDtYears: number;
  taxNStars: number;
  taxDtYears: number;
  seed: number;
}

export const SPINE_DEFAULTS = {
  nStars: 1200,
  offspringPerSettlement: 2,
  policy: "powered" as Policy,
  swarmDtYears: 5000,
  taxNStars: 400,
  taxDtYears: 1.0,
  seed: 0x9e3779b9,
};

export function scenarioFrom(factory: Factory, overrides: Partial<SpineScenario> = {}): SpineScenario {
  return { factory, ...SPINE_DEFAULTS, ...overrides };
}

export interface SpineResult {
  closureRatio: number;
  singleFactoryTimeToTargetDays: number | null;
  copyTimeDays: number;
  settleTimeYears: number;
  fleetDoublingDays: number | null;
  fleetFinalPopulation: number;
  fleetBinding: string;
  policy: Policy;
  nStars: number;
  finalSettled: number;
  swarmT100Years: number | null;
  dwellFractionOfT100: number | null;
  verdict: string;
}

export interface DwellTax {
  policy: Policy;
  nStars: number;
  dtYears: number;
  settleTimeYears: number;
  t100WithDwell: number | null;
  t100ZeroDwell: number | null;
  taxFraction: number | null;
}

/** The swarm's per-star dwell, derived from the factory's 1-AU copy cadence (in years). */
export function deriveSettleTimeYears(scenario: SpineScenario): number {
  const fp = paramsFromFactory(scenario.factory);
  return timeToBuildOneCopyDays(fp, 1.0) / DAYS_PER_JULIAN_YEAR;
}

function fleetBindingLabel(b: { vitaminLimited: boolean; powerLimited: boolean; capLimited: boolean }): string {
  if (b.vitaminLimited) return "vitamin-limited (the electronics wall: the imported-parts pool ran out)";
  if (b.powerLimited) return "power-limited (dispersed probes build too slowly to copy - the spatial power wall)";
  if (b.capLimited) return "cap-limited (hit the fleet-size cap - a scope bound, not physics)";
  return "still growing at the horizon (no ceiling reached in the window)";
}

function buildVerdict(settleTimeYears: number, fleetDoublingDays: number | null, policy: Policy, t100: number | null, dwellFrac: number | null): string {
  const dwellDays = settleTimeYears * DAYS_PER_JULIAN_YEAR;
  const parts = [`One copy takes ~${dwellDays.toFixed(0)} days (~${settleTimeYears.toFixed(2)} yr) to build.`];
  if (fleetDoublingDays !== null)
    parts.push(`At fleet scale that build time IS the clock - the fleet doubles in ~${fleetDoublingDays.toFixed(0)} days, set by how fast a probe makes a copy.`);
  if (t100 !== null && dwellFrac !== null)
    parts.push(`At galactic scale (${policy}) the same dwell is ~${dwellFrac.toExponential(1)} of the ~${Math.round(t100).toLocaleString("en-US")}-yr fill - interstellar transit dominates, so manufacturing time is a negligible tax on exploration.`);
  return parts.join(" ");
}

function swarmParamsFor(scenario: SpineScenario, settleTimeYears: number, nStars: number, dtYears: number) {
  return {
    ...SWARM_DEFAULTS,
    nStars,
    offspringPerSettlement: scenario.offspringPerSettlement,
    settleTimeYears,
    policy: scenario.policy,
    dtYears,
  };
}

export function runSpine(scenario: SpineScenario): SpineResult {
  const { factory } = scenario;
  if (!factory.replication) throw new RangeError("spine factory needs replication params");

  const closureRatio = computeClosure(factory).closure_ratio;
  const single = simulate(factory, factory.replication);

  const fp = paramsFromFactory(factory);
  const copyTimeDays = timeToBuildOneCopyDays(fp, 1.0);
  const settleTimeYears = copyTimeDays / DAYS_PER_JULIAN_YEAR;

  const fleet = simulateFleet(fp);

  const swarm: SwarmResult = simulateSwarm(swarmParamsFor(scenario, settleTimeYears, scenario.nStars, scenario.swarmDtYears), scenario.seed);
  const t100 = swarm.t100Years;
  const dwellFrac = t100 && t100 > 0 ? settleTimeYears / t100 : null;

  return {
    closureRatio,
    singleFactoryTimeToTargetDays: single.time_to_target_days,
    copyTimeDays,
    settleTimeYears,
    fleetDoublingDays: fleet.doublingTimeDays,
    fleetFinalPopulation: fleet.finalPopulation,
    fleetBinding: fleetBindingLabel(fleet.binding),
    policy: scenario.policy,
    nStars: scenario.nStars,
    finalSettled: swarm.finalSettled,
    swarmT100Years: t100,
    dwellFractionOfT100: dwellFrac,
    verdict: buildVerdict(settleTimeYears, fleet.doublingTimeDays, scenario.policy, t100, dwellFrac),
  };
}

/** A/B the dwell's galactic cost (fine dt, small field). Meant for fast (slingshot) policies. */
export function measureDwellTax(scenario: SpineScenario): DwellTax {
  const settleTimeYears = deriveSettleTimeYears(scenario);
  const t100 = (dwell: number) => simulateSwarm(swarmParamsFor(scenario, dwell, scenario.taxNStars, scenario.taxDtYears), scenario.seed).t100Years;
  const withDwell = t100(settleTimeYears);
  const zeroDwell = t100(0.0);
  const taxFraction = withDwell !== null && zeroDwell !== null && zeroDwell !== 0 ? (withDwell - zeroDwell) / zeroDwell : null;
  return { policy: scenario.policy, nStars: scenario.taxNStars, dtYears: scenario.taxDtYears, settleTimeYears, t100WithDwell: withDwell, t100ZeroDwell: zeroDwell, taxFraction };
}
