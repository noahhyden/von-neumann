/** The spine as a pimas reactive graph - the cross-scale surface. */
import { createSignal, createMemo } from "pimas";
import type { Accessor } from "pimas";
import { param, type ParamSignal } from "./reactive-model.js";
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
  const nStars = param(1200, { min: 200, max: 4000, step: 100, label: "Stars in the field", unit: "" });
  const offspring = param(2, { min: 0, max: 4, step: 1, label: "Offspring per settlement", unit: "" });
  const [policy, setPolicy] = createSignal<Policy>("powered");

  const params: ParamSignal[] = [
    nStars,
    offspring,
  ];

  const scenario = () =>
    scenarioFrom(LUNAR_REGOLITH_SEED, {
      nStars: Math.round(nStars.get()),
      offspringPerSettlement: Math.round(offspring.get()),
      policy: policy(),
    });

  const result = createMemo<SpineResult>(() => runSpine(scenario()));

  // Only measure the tax for the fast policies: a brute-force A/B of a ~1.6 yr dwell against ~10^5 yr powered hops is infeasible, so powered reads the analytic fraction instead.
  const dwellTax = createMemo<DwellTax | null>(() =>
    policy() === "powered" ? null : measureDwellTax(scenario())
  );

  return { params, policy, setPolicy, result, dwellTax, factoryName: LUNAR_REGOLITH_SEED.name };
}
