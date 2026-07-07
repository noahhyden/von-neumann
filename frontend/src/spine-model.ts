/**
 * The spine as a pimas reactive graph - the cross-scale surface.
 *
 * Signals for the knobs a viewer changes (star count, offspring, travel policy); one
 * memo over the parity-tested TS port (`spine.ts`) that reruns all three scales on one
 * factory. Same lightweight shape as the other composed surfaces (signals + memos, no
 * store/speculate) - the fold is pure and cheap.
 *
 * The manufacturing dwell tax is measured by an A/B (derived dwell vs zero) that is only
 * practical for the fast slingshot policies - resolving a ~1.6 yr dwell against ~10^5 yr
 * powered hops by brute force is infeasible, which is itself the finding. So `dwellTax`
 * is a memo that computes only for slingshot policies and is null for powered, where the
 * analytic `dwellFractionOfT100` on the result already tells the story.
 */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import type { ParamSignal } from "./reactive-model.js";
import { runSpine, measureDwellTax, scenarioFrom } from "./spine.js";
import type { SpineResult, DwellTax } from "./spine.js";
import type { Policy } from "./swarm.js";
import { LUNAR_REGOLITH_SEED } from "./scenarios.js";

export interface SpineModel {
  params: ParamSignal[];
  policy: Accessor<Policy>;
  setPolicy: (p: Policy) => void;
  result: Accessor<SpineResult>;
  dwellTax: Accessor<DwellTax | null>;
  factoryName: string;
}

export function createSpineModel(): SpineModel {
  const [nStars, setNStars] = createSignal(1200);
  const [offspring, setOffspring] = createSignal(2);
  const [policy, setPolicy] = createSignal<Policy>("powered");

  const params: ParamSignal[] = [
    { get: nStars, set: setNStars, min: 200, max: 4000, step: 100, label: "Stars in the field", unit: "" },
    { get: offspring, set: setOffspring, min: 0, max: 4, step: 1, label: "Offspring per settlement", unit: "" },
  ];

  const scenario = () =>
    scenarioFrom(LUNAR_REGOLITH_SEED, {
      nStars: Math.round(nStars()),
      offspringPerSettlement: Math.round(offspring()),
      policy: policy(),
    });

  const result = createMemo<SpineResult>(() => runSpine(scenario()));

  // Only measure the tax for the fast policies (see the module note). Powered's analytic
  // fraction lives on `result().dwellFractionOfT100`.
  const dwellTax = createMemo<DwellTax | null>(() =>
    policy() === "powered" ? null : measureDwellTax(scenario())
  );

  return { params, policy, setPolicy, result, dwellTax, factoryName: LUNAR_REGOLITH_SEED.name };
}
