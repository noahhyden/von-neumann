/** The Electronics Wall, live. */
import { createSignal, createMemo, createEffect, onCleanup } from "pimas";
import { render } from "pimas/dom";
import { Show, For } from "pimas/flow";
import { createWallModel, fmtDays } from "./reactive-model.js";
import type { WallModel, ParamSignal } from "./reactive-model.js";
import { SCENARIOS } from "./scenarios.js";
import { GrowthChart } from "./chart.js";
import type { SimResult } from "./model.js";
import { createLaunchEconomicsModel } from "./launch-economics-model.js";
import type { LaunchModel } from "./launch-economics-model.js";
import { createPowerBudgetModel } from "./power-budget-model.js";
import type { PowerBudgetModel } from "./power-budget-model.js";
import { createProbeModel } from "./probe-sim-model.js";
import type { ProbeModel } from "./probe-sim-model.js";
import { createMissionModel } from "./mission-model.js";
import type { MissionModel } from "./mission-model.js";
import { createMultiProbeModel } from "./multi-probe-model.js";
import type { MultiProbeModel } from "./multi-probe-model.js";
import { createSwarmModel } from "./swarm-model.js";
import type { SwarmModel } from "./swarm-model.js";
import { createSpineModel } from "./spine-model.js";
import type { SpineModel } from "./spine-model.js";
import { RUNGS } from "./coordination.js";
import { SOURCES, sourceById, sourceNumber, sourceCategories, STRENGTH_LABEL } from "./sources.js";
import type { Source } from "./sources.js";
import type { Tone } from "./ui.js";
import { PageShell, Shell, Band, Lab, Panel, Figure, ActionRow, Action, Stat, Explain, Note, Slider, Cite, Accordion } from "./ui.js";
import { Nav } from "./chrome.js";
import { token } from "./tokens.js";
import { PAPERS } from "./papers-index.js";
import type { PaperMeta } from "./papers-index.js";
// Generated at build time from git history (a version = every commit touching papers/<slug>/); see papers/scripts/gen-versions.mjs.
import { PAPER_VERSIONS } from "./papers-versions.js";
import type { VersionMeta } from "./papers-versions.js";
import { VALID_SURFACES, SURFACE_TITLE, DEFAULT_SCENARIO, pathForSurface, parsePath, pathFromLegacyHash, isKnownPath } from "./routes.js";
import type { Surface } from "./routes.js";

const fmtNum = (n: number, d = 0) => n.toLocaleString(undefined, { maximumFractionDigits: d });
const usdCompact = (d: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", minimumFractionDigits: d, maximumFractionDigits: d });
const USD_B = usdCompact(2);
const USD_M = usdCompact(1);
const fmtUsd = (n: number): string => {
  const abs = Math.abs(n);
  const sign = n < 0 ? "$-" : "$"; // keep the legacy "$-3.3M" sign placement
  if (abs >= 1e9) return USD_B.format(abs).replace("$", sign);
  if (abs >= 1e6) return USD_M.format(abs).replace("$", sign);
  return `$${fmtNum(n)}`;
};
const fmtSci = (n: number, d = 2) => n.toExponential(d);
const FLOPS_UNITS: [string, number][] = [["EFLOPS", 1e18], ["PFLOPS", 1e15], ["TFLOPS", 1e12], ["GFLOPS", 1e9], ["MFLOPS", 1e6], ["kFLOPS", 1e3]];
const fmtFlops = (n: number): string => {
  for (const [u, v] of FLOPS_UNITS) if (n >= v) return `${(n / v).toFixed(2)} ${u}`;
  return `${fmtNum(n)} FLOPS`;
};
const fmtPower = (w: number): string => (w >= 1000 ? `${fmtNum(w / 1000, w >= 1e5 ? 0 : 1)} kW` : `${fmtNum(w)} W`);
const fmtBrains = (be: number): string => (be >= 0.01 ? `${be.toFixed(2)}×` : `${fmtSci(be, 1)}×`);
const regimeClass = (r: string) => (r === "material-limited" ? "rg-material" : r === "energy-limited" ? "rg-energy" : "rg-resupply");
const regimeWord = (r: string) => r.replace("-limited", "");

function RegimeTimeline(props: { model: WallModel }) {
  const spans = createMemo(() => {
    const s = props.model.sim();
    const total = s.steps[s.steps.length - 1].day || 1;
    return s.regime_timeline.map((sp) => ({
      regime: sp.regime,
      pct: ((sp.end_day - sp.start_day) / total) * 100,
    }));
  });
  return (
    <div>
      <div class="regime">
        <For each={spans}>
          {(sp: { regime: string; pct: number }) => <span class={regimeClass(sp.regime)} style={`width:${sp.pct}%`} title={sp.regime} />}
        </For>
      </div>
      <div class="legend">
        <span><b class="rg-material" />material</span>
        <span><b class="rg-energy" />energy</span>
        <span><b class="rg-resupply" />resupply</span>
      </div>
    </div>
  );
}

function AgentPanel(props: { model: WallModel; explain: () => ReturnType<WallModel["bridge"]["explain"]> }) {
  const m = props.model;
  const [spec, setSpec] = createSignal<Record<string, unknown> | null>(null);
  const descriptor = createMemo(() => {
    m.sim(); // depend on the model so exposed values refresh
    const d = m.bridge.descriptor();
    const state = Object.entries(d.state)
      .map(([k, v]) => `  ${k}: ${JSON.stringify(v.value, (_k, x) => (typeof x === "number" ? Number(x.toPrecision(4)) : x))}`)
      .join("\n");
    const acts = Object.keys(d.actions).map((a) => `  ${a}()`).join("\n");
    return `state {\n${state}\n}\nactions {\n${acts}\n}`;
  });
  const askAgent = () => setSpec(m.bridge.speculate("makeChipsLocal") as Record<string, unknown>);
  return (
    <Panel kind="plain" head="State and actions">
      <Note>
        An agent can read these values, call these actions, preview one without committing it, or ask why a committed one changed what it did.
      </Note>
      <pre class="desc">{descriptor}</pre>
      <ActionRow>
        <Action onClick={askAgent}>agent asks: speculate makeChipsLocal()</Action>
        <Show when={() => spec() !== null}>{() => <Action kind="ghost" onClick={() => setSpec(null)}>clear</Action>}</Show>
      </ActionRow>
      <Show when={() => spec() !== null}>
        {() => (
          <div class="preview">
            <p class="ph">predicted state · not committed</p>
            <div class="cause">
              <div><span class="k">time_to_target_days:</span> <span class="c">{() => fmtDays((spec()!.time_to_target_days as number | null))}</span></div>
              <div><span class="k">binding_regime:</span> <span class="c">{() => String(spec()!.binding_regime)}</span></div>
              <div><span class="k">final_output_kg_per_day:</span> <span class="c">{() => fmtNum(spec()!.final_output_kg_per_day as number)}</span></div>
              <div><span class="k">chips_are_local (real, still):</span> <span class="w">{() => String(m.chipsAreLocal())}</span></div>
            </div>
          </div>
        )}
      </Show>
      <Show when={() => props.explain() !== null}>
        {() => (
          <div>
            <p class="panel-head">last committed action · explain()</p>
            <div class="cause">
              <div><span class="k">action:</span> {() => props.explain()!.action}</div>
              <div><span class="k">wrote fields:</span> <span class="w">{() => props.explain()!.writes.join(", ") || "-"}</span></div>
              <div><span class="k">changed outputs:</span> <span class="c">{() => props.explain()!.changed.join(", ") || "-"}</span></div>
            </div>
          </div>
        )}
      </Show>
    </Panel>
  );
}

function App(props: { model: WallModel; scenarioKey: string; onScenario: (k: string) => void }) {
  const m = props.model;
  const [preview, setPreview] = createSignal<{ before: SimResult; after: SimResult } | null>(null);
  const [explain, setExplain] = createSignal<ReturnType<WallModel["bridge"]["explain"]>>(null);

  const doPreview = () => setPreview(m.previewChipsLocal());
  const doCommit = () => { m.bridge.call("makeChipsLocal"); setExplain(m.bridge.explain()); setPreview(null); };
  const doRestore = () => { m.bridge.call("restoreChips"); setExplain(m.bridge.explain()); setPreview(null); };
  const doReset = () => { m.reset(); setPreview(null); setExplain(null); };

  const tttCls = () => (m.sim().time_to_target_days === null ? "bad" : "good");

  return (
    <PageShell title="One factory makes two. Two make four. Then it hits a wall." lede={<>A single robotic factory on the Moon copies itself from local rock until it stalls on chips, the one part it can't make.</>} hero={<>

          <Figure caption="FIG.1 - factory output vs time, straight from the model. As built (solid line). Bronze, when previewing: if it made its own chips.">
            <GrowthChart model={m} preview={preview} />
          </Figure>
      </>} footer={<>The model is closure-sim (NASA CP-2255, 1980; Freitas &amp; Merkle, 2004)<Cite ids={["nasa-cp-2255-1980", "freitas-merkle-2004"]} />. Figures are order-of-magnitude estimates, not predictions.</>}>

      <Band>
          <Lab>
            <Panel kind="controls" head="Assumptions">
              <For each={() => Object.values(m.params)}>
                {(p: ParamSignal) => <Slider p={p} />}
              </For>
              <ActionRow>
                <Action kind="ghost" onClick={doReset}>reset {props.scenarioKey === "lunar" ? "lunar seed" : "outpost"}</Action>
                <For each={() => Object.keys(SCENARIOS)}>
                  {(k: string) => (
                    <button class={() => `act ${k === props.scenarioKey ? "act-primary" : "act-default"}`} onClick={() => props.onScenario(k)}>{k}</button>
                  )}
                </For>
              </ActionRow>
            </Panel>

            <Panel kind="readouts" head="Live results">
              <Stat what="Closure" sub="mass built locally" value={() => `${(m.closureRatio() * 100).toFixed(1)}%`} tone={() => "metal"} />
              <Stat what="Time to reach target" value={() => fmtDays(m.sim().time_to_target_days)} tone={tttCls} />
              <Stat what="Doubling time" sub="first mass doubling" value={() => fmtDays(m.sim().empirical_doubling_time_days)} />
              <Stat what="Final output" sub={`after ${fmtNum(m.sim().steps[m.sim().steps.length - 1].day / 365)} yr`} value={() => `${fmtNum(m.sim().final_output_kg_per_day)} kg/day`} />
              <Stat what="What limits growth" sub="material, energy or resupply" value={() => regimeWord(m.lateRegime())} tone={() => (m.lateRegime() === "energy-limited" ? "bad" : m.lateRegime() === "resupply-limited" ? "chip" : "metal")} />
              <div>
                <p class="panel-head">Regime over time</p>
                <RegimeTimeline model={m} />
              </div>
              <Explain>{() => m.explainRegime(m.sim())}</Explain>
            </Panel>
          </Lab>
      </Band>

      <Band title="Making its own chips helps only if you can power it.">
          <p>
            Chips are the one part the factory can't make, and making them locally costs thousands of kWh per kg. <strong>Speculate</strong> it: pimas re-runs the model on a shadow of the reactive graph and returns the exact result, <em>without touching the live model</em>. Commit only if you like it.
          </p>
          <ActionRow>
            <Show when={() => !m.chipsAreLocal()} fallback={() => <Action kind="ghost" onClick={doRestore}>revert to imported chips</Action>}>
              {() => <Action kind="primary" onClick={doPreview}>speculate: make its own chips</Action>}
            </Show>
            <Show when={() => preview() !== null}>
              {() => (
                <>
                  <Action kind="commit" onClick={doCommit}>commit this change</Action>
                  <Action kind="ghost" onClick={() => setPreview(null)}>discard</Action>
                </>
              )}
            </Show>
          </ActionRow>

          <Show when={() => preview() !== null}>
            {() => (
            <div class="preview">
              <p class="ph">speculation · shadow graph · nothing committed yet</p>
              <div class="diff">
                <div class="d">
                  <span>time to target</span>
                  <b><span class="val val-chip">{() => fmtDays(preview()!.before.time_to_target_days)}</span> <span class="arrow">→</span> <span class="val val-metal">{() => fmtDays(preview()!.after.time_to_target_days)}</span></b>
                </div>
                <div class="d">
                  <span>closure</span>
                  <b><span class="val val-chip">{() => (preview()!.before.closure_ratio * 100).toFixed(1)}%</span> <span class="arrow">→</span> <span class="val val-metal">{() => (preview()!.after.closure_ratio * 100).toFixed(1)}%</span></b>
                </div>
                <div class="d">
                  <span>what limits growth</span>
                  <b><span class="val val-chip">{() => regimeWord(preview()!.before.regime_timeline.at(-1)!.regime)}</span> <span class="arrow">→</span> <span class="val val-metal">{() => regimeWord(preview()!.after.regime_timeline.at(-1)!.regime)}</span></b>
                </div>
              </div>
              <Note>
                {() => {
                  const b = preview()!.before.time_to_target_days;
                  const a = preview()!.after.time_to_target_days;
                  if (a === null) return "Backfire: it runs out of power before reaching the target.";
                  if (b === null) return "Making chips locally is what unlocks the target at all.";
                  const saved = (b - a) / 365;
                  return saved > 0 ? `Making chips locally reaches the target ${saved.toFixed(1)} years sooner.` : `Making chips locally is ${(-saved).toFixed(1)} years slower here - not worth the energy.`;
                }}
              </Note>
            </div>
            )}
          </Show>
      </Band>

      <Band title="Under the hood">
          <details>
            <summary>For developers: the same model as an agent surface</summary>
            <AgentPanel model={m} explain={explain} />
          </details>
      </Band>
    </PageShell>
  );
}

// ── the launch-economics surface ───────────────────────────────────────────
const explainLeverage = (m: LaunchModel): string => {
  const c = m.comparison();
  const pct = m.closurePct().toFixed(0);
  if (c.massLeverage <= 1) {
    return `At ${pct}% closure you launch about as much as you install.`;
  }
  return `At ${pct}% closure, ${(100 - m.closurePct()).toFixed(0)}% of the factory's mass is imported parts and the rest is built locally.`;
};

function LaunchSurface(props: { model: LaunchModel }) {
  const m = props.model;
  const c = () => m.comparison();
  return (
    <PageShell title="Don't launch the factory. Launch a seed that builds it." lede={<>Every kilogram to orbit is expensive. Self-replication trades launched mass for local mass: the more of itself a factory builds (its <strong>closure</strong>), the less you launch.</>} footer={<>Leverage = target mass ÷ (seed + imported parts), where closure sets the imported share: (1−C) kg per kg built. $/kg figures are research-grounded (SpaceX published capabilities<Cite ids="spacex-capabilities" />; standard Δv tables<Cite ids="tsiolkovsky-1903" />), not predictions.</>}>

      <Band>
          <Lab>
            <Panel kind="controls" head="Assumptions">
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
            </Panel>
            <Panel kind="readouts" head="Live results">
              <Stat what="Launch-mass leverage" sub="installed kg per launched kg" value={() => `${c().massLeverage.toFixed(1)}×`} tone={() => "metal"} />
              <Stat what="Mass launched" sub="seed + imported parts" value={() => `${fmtNum(c().launchedMassKg / 1000)} t`} />
              <Stat what="Launch it all" sub="direct cost" value={() => fmtUsd(c().directLaunchCostUsd)} tone={() => "bad"} />
              <Stat what="Launch a seed" value={() => fmtUsd(c().replicationLaunchCostUsd)} tone={() => "metal"} />
              <Stat what="Savings" sub="launch it all minus launch a seed" value={() => fmtUsd(c().costSavingsUsd)} tone={() => "good"} />
              <Explain>{() => explainLeverage(m)}</Explain>
            </Panel>
          </Lab>
      </Band>
    </PageShell>
  );
}

// ── the power-budget surface ────────────────────────────────────────────────
const explainPower = (m: PowerBudgetModel): string => {
  const o = m.outputs();
  const orders = Math.round(Math.log10(o.headroomOverLandauer));
  return `Each FLOP burns ~${fmtSci(o.energyPerFlopJ, 1)} J - roughly ${orders} orders of magnitude above the single-bit Landauer floor, so the ceiling is hardware and waste heat, not thermodynamics.`;
};

function PowerBudgetSurface(props: { model: PowerBudgetModel }) {
  const m = props.model;
  const o = () => m.outputs();
  return (
    <PageShell title="How much can a factory think, if it also has to build?" lede={<>An autonomous factory light-minutes from Earth spends some of its power making things and some <em>thinking</em>. The split sets how much compute it buys, against the ~20 W human brain and the thermodynamic floor.</>} footer={<>Throughput = compute-watts × efficiency; the <strong>Landauer floor</strong> is k·T·ln2 (~2.9e-21 J/bit at 300 K). The brain scale (~20 W<Cite ids="raichle-gusnard-2002" />, ~1e18 FLOPS<Cite ids="sandberg-bostrom-2008" />) and Landauer limit<Cite ids="landauer-1961" /> are sourced; brain-FLOPS is an order-of-magnitude estimate.</>}>

      <Band>
          <Lab>
            <Panel kind="controls" head="Assumptions">
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
            </Panel>
            <Panel kind="readouts" head="Live results">
              <Stat what="Compute power" sub="share of the budget" value={() => `${fmtNum(o().computeW)} W`} tone={() => "metal"} />
              <Stat what="Compute throughput" value={() => fmtFlops(o().computeFlops)} tone={() => "metal"} />
              <Stat what="Brain-equivalents" sub="≈1e18 FLOPS each · [ESTIMATE]" value={() => fmtBrains(o().brainEquivalents)} tone={() => (o().brainEquivalents >= 1 ? "good" : "chip")} />
              <Stat what="Energy per FLOP" value={() => `${fmtSci(o().energyPerFlopJ, 2)} J`} />
              <Stat what="Landauer floor" cite="landauer-1961" sub="k·T·ln2 at the radiator temp" value={() => `${fmtSci(o().landauerJPerBit, 2)} J/bit`} />
              <Stat what="Above the floor" sub="energy per FLOP vs the Landauer floor" value={() => `${fmtSci(o().headroomOverLandauer, 1)}×`} />
              <Explain>{() => explainPower(m)}</Explain>
            </Panel>
          </Lab>
      </Band>
    </PageShell>
  );
}

// ── the probe surface ───────────────────────────────────────────────────────
function ProbeSurface(props: { model: ProbeModel }) {
  const m = props.model;
  const o = () => m.outputs();
  return (
    <PageShell title="How far out can a self-powered probe still work - and still think?" lede="A self-replicating probe runs on sunlight, and sunlight falls as the inverse square of distance." footer={<>Irradiance = solar constant ÷ distance² (1360.8 W/m² at 1 AU, Kopp &amp; Lean 2011<Cite ids="kopp-lean-2011" />); delivered power = irradiance × area × efficiency. After Borgue &amp; Hein (2020)<Cite ids="borgue-hein-2020" />. The probe's full replication range awaits a sourced per-module mass breakdown.</>}>

      <Band>
          <Lab>
            <Panel kind="controls" head="Assumptions">
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
            </Panel>
            <Panel kind="readouts" head="Live results">
              <Stat what="Sunlight here" cite="kopp-lean-2011" sub="irradiance, inverse-square" value={() => `${fmtNum(o().irradianceWM2)} W/m²`} />
              <Stat what="Delivered power" value={() => fmtPower(o().deliveredPowerW)} tone={() => "metal"} />
              <Stat what="Compute power" sub="share for thinking" value={() => fmtPower(o().computePowerW)} />
              <Stat what="Compute throughput" value={() => fmtFlops(o().computeFlops)} tone={() => "metal"} />
              <Stat what="Brain-equivalents" sub="≈1e18 FLOPS each · [ESTIMATE]" value={() => fmtBrains(o().brainEquivalents)} tone={() => (o().brainEquivalents >= 1 ? "good" : "chip")} />
              <Explain>{() => "Power and compute both fall as 1/d²: at twice the distance, a quarter."}</Explain>
            </Panel>
          </Lab>
      </Band>
    </PageShell>
  );
}

// Mission surface quick-jump destinations (heliocentric distance, AU): mean distances from the NASA planetary fact sheet.
const DESTINATIONS: [string, number][] = [["Earth orbit", 1.0], ["Mars", 1.524], ["Asteroid belt", 2.7], ["Jupiter", 5.203], ["Deep", 20]];

const explainMission = (m: MissionModel): string => {
  const r = m.outputs();
  const lev = r.massLeverage;
  if (!r.reachesTarget) {
    if (r.manufacturingW <= 0) {
      return `All the power goes to thinking, so the factory never builds and stalls at the seed. Give manufacturing some power.`;
    }
    return `At ${r.distanceAu.toFixed(1)} AU the array delivers only ${fmtPower(r.deliveredPowerW)}, and the ${fmtPower(r.manufacturingW)} left for building isn't enough to reach target output. Move closer to the Sun, or grow the array.`;
  }
  return `It works: a ${fmtNum(r.launchedMassKg / 1000)} t launch grows into a ${fmtNum(r.targetInstalledMassKg / 1000)} t factory, ${lev.toFixed(1)}× leverage.`;
};

function MissionStage(props: { n: string; title: string; value: () => string; tone?: () => Tone; note: () => string }) {
  return (
    <Panel kind="plain">
      <Stat what={<><span class="step-n">{props.n}</span> {props.title}</>} value={props.value} tone={props.tone} />
      <Explain>{props.note}</Explain>
    </Panel>
  );
}

function MissionSurface(props: { model: MissionModel }) {
  const m = props.model;
  const r = () => m.outputs();
  const okCls = () => (r().reachesTarget ? "good" : "bad");
  return (
    <PageShell title="Launch a seed. Fly it to the Sun's light. Watch it build a factory." lede={<>One run over the <strong>launch</strong> bill, <strong>closure</strong>, <strong>solar power</strong>, the build/think <strong>split</strong> and <strong>replication</strong>.</>} hero={<>

          <Panel kind="plain">
            <p class="panel-head">Does the operation succeed?</p>
            <Explain>{() => explainMission(m)}</Explain>
          </Panel>
      </>} footer={<>Built from the launch, closure, probe and power models<Cite ids={["nasa-cp-2255-1980", "kopp-lean-2011", "landauer-1961", "tsiolkovsky-1903"]} />. Launch figures are representative sourced values.
            <br /><br />
            There is no sourced per-module mass breakdown for the Borgue &amp; Hein probe<Cite ids="borgue-hein-2020" />, so the factory here is closure-sim's lunar-regolith seed scenario as a stand-in.</>}>

      <Band>
          <Lab>
            <Panel kind="controls" head="Mission parameters">
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
              <ActionRow>
                <span class="note">jump to:</span>
                <For each={() => DESTINATIONS}>
                  {(d: [string, number]) => (
                    <button
                      class={() => `act ${Math.abs(m.params[0].get() - d[1]) < 0.05 ? "act-primary" : "act-ghost"}`}
                      onClick={() => m.params[0].set(d[1])}
                    >{d[0]}</button>
                  )}
                </For>
              </ActionRow>
            </Panel>
            <Panel kind="readouts" head="Headline">
              <Stat what="Reaches target output?" value={() => (r().reachesTarget ? "yes" : "no")} tone={okCls} />
              <Stat what="Launch-mass leverage" sub="installed kg per launched kg" value={() => `${r().massLeverage.toFixed(1)}×`} tone={() => "metal"} />
              <Stat what="Savings vs launch-it-all" value={() => fmtUsd(r().costSavingsUsd)} tone={() => "good"} />
              <Stat what="Time to target output" value={() => fmtDays(r().timeToTargetDays)} tone={okCls} />
              <Stat what="Delivered power here" sub="inverse-square" value={() => fmtPower(r().deliveredPowerW)} tone={() => "metal"} />
              <Stat what="Compute afforded" sub="brain-equivalents · [ESTIMATE]" value={() => fmtBrains(r().brainEquivalents)} tone={() => "chip"} />
            </Panel>
          </Lab>
      </Band>

      <Band title="The chain, stage by stage">
          <MissionStage n="00" title="Launch - put the seed in space"
            value={() => `${fmtNum(r().launchedMassKg / 1000)} t launched`}
            tone={() => "metal"}
            note={() => `You launch the ${fmtNum(r().seedMassKg / 1000)} t seed plus ${fmtNum(r().vitaminMassKg / 1000)} t of imported parts (what it can't make). Reaching orbit is ${(r().propellantFraction * 100).toFixed(0)}% propellant by mass (Δv ${fmtNum(r().deltaVMs)} m/s, Isp ${fmtNum(r().specificImpulseS)} s) - that exponential penalty is why launching the finished factory is unthinkable.`} />
          <MissionStage n="01" title="Closure - how much it makes for itself"
            value={() => `${(r().closureRatio * 100).toFixed(1)}% closed`}
            tone={() => "metal"}
            note={() => `The seed factory can build ${(r().closureRatio * 100).toFixed(1)}% of its own mass from local material; the remaining ${((1 - r().closureRatio) * 100).toFixed(1)}% must be imported as parts. That single fraction sets both the launch bill above and the payoff below.`} />
          <MissionStage n="02" title="Arrive - solar power at distance"
            value={() => fmtPower(r().deliveredPowerW)}
            tone={() => "metal"}
            note={() => `At ${r().distanceAu.toFixed(1)} AU sunlight is ${fmtNum(r().irradianceWM2)} W/m²; the ${fmtNum(m.params[2].get())} m² array converts it to ${fmtPower(r().deliveredPowerW)}. Double the distance and this quarters - the inverse-square law is the whole constraint on where a solar probe can work.`} />
          <MissionStage n="03" title="Split - build vs. think"
            value={() => `${fmtPower(r().manufacturingW)} build · ${fmtPower(r().computeW)} think`}
            note={() => `Housekeeping takes the rest. This is the one dial the models didn't share - here it's decided once and routed to the two stages below.`} />
          <MissionStage n="04" title="Replicate - does it grow?"
            value={() => (r().reachesTarget ? `reaches target in ${fmtDays(r().timeToTargetDays)}` : "never reaches target")}
            tone={okCls}
            note={() => (r().reachesTarget
              ? `Fed ${fmtPower(r().manufacturingW)}, the factory doubles about every ${fmtDays(r().doublingTimeDays)} and climbs to target output, ending ${regimeWord(r().bindingRegime ?? "")}-limited.`
              : `With only ${fmtPower(r().manufacturingW)} for manufacturing, growth never reaches the target output rate - the operation is power-starved at this distance and split.`)} />
          <MissionStage n="05" title="Payoff - what you saved"
            value={() => `${r().massLeverage.toFixed(1)}× · ${fmtUsd(r().costSavingsUsd)}`}
            tone={() => "good"}
            note={() => `Launching a ${fmtNum(r().launchedMassKg / 1000)} t seed instead of a ${fmtNum(r().targetInstalledMassKg / 1000)} t factory costs ${fmtUsd(r().replicationLaunchCostUsd)} instead of ${fmtUsd(r().directLaunchCostUsd)}.`} />
      </Band>
    </PageShell>
  );
}

// ── the multi-probe surface: a small, deterministic, dispersing fleet ────────
function FleetChart(props: { model: MultiProbeModel }) {
  const W = 900, H = 230, PADL = 52, PADR = 54, PADT = 18, PADB = 34;
  const geo = createMemo(() => {
    const steps = props.model.result().steps;
    const xmaxYr = Math.max(1e-6, steps[steps.length - 1].day / 365);
    const maxPop = Math.max(2, ...steps.map((s) => s.population));
    const maxDist = Math.max(1, ...steps.map((s) => s.maxDistanceAu));
    const X = (yr: number) => PADL + (yr / xmaxYr) * (W - PADL - PADR);
    const Yp = (v: number) => PADT + (H - PADT - PADB) * (1 - v / maxPop);
    const Yd = (v: number) => PADT + (H - PADT - PADB) * (1 - v / maxDist);
    const stride = Math.max(1, Math.floor(steps.length / 240));
    const pop: string[] = [], front: string[] = [];
    for (let i = 0; i < steps.length; i += stride) {
      pop.push(`${X(steps[i].day / 365).toFixed(1)},${Yp(steps[i].population).toFixed(1)}`);
      front.push(`${X(steps[i].day / 365).toFixed(1)},${Yd(steps[i].maxDistanceAu).toFixed(1)}`);
    }
    const last = steps[steps.length - 1];
    pop.push(`${X(last.day / 365).toFixed(1)},${Yp(last.population).toFixed(1)}`);
    front.push(`${X(last.day / 365).toFixed(1)},${Yd(last.maxDistanceAu).toFixed(1)}`);
    return { xmaxYr, maxPop, maxDist, X, Yp, Yd, pop: pop.join(" "), front: front.join(" ") };
  });
  const cursorX = () => geo().X(props.model.snap().day / 365);

  const content = () => {
    const g = geo();
    const els: unknown[] = [];
    for (const f of [0, 0.5, 1]) {
      const y = PADT + (H - PADT - PADB) * (1 - f);
      els.push(<line x1={PADL} y1={y} x2={W - PADR} y2={y} stroke="var(--line)" stroke-width="1" />);
      els.push(<text x={PADL - 8} y={y + 4} text-anchor="end" fill="var(--chip)" class="axis-text">{fmtNum(g.maxPop * f)}</text>);
      els.push(<text x={W - PADR + 8} y={y + 4} fill="var(--metal)" class="axis-text">{fmtNum(g.maxDist * f, 1)}</text>);
    }
    els.push(<text x={PADL} y={PADT - 6} fill="var(--chip)" class="axis-text">PROBES</text>);
    els.push(<text x={W - PADR + 8} y={PADT - 6} text-anchor="end" fill="var(--metal)" class="axis-text">FRONTIER AU</text>);
    els.push(<text x={(PADL + W - PADR) / 2} y={H - 6} text-anchor="middle" fill="var(--muted)" class="axis-text">YEARS →</text>);
    els.push(<polyline points={g.front} fill="none" stroke="var(--metal)" stroke-width="2" stroke-dasharray="6 5" stroke-linejoin="round" />);
    els.push(<polyline points={g.pop} fill="none" stroke="var(--chip)" stroke-width="2.5" stroke-linejoin="round" />);
    els.push(<line x1={cursorX} y1={PADT} x2={cursorX} y2={H - PADB} stroke="var(--text)" stroke-width="1.5" stroke-dasharray="3 3" />);
    return els;
  };
  return (
    <svg class="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Fleet population and dispersal frontier over time">{content}</svg>
  );
}

function FleetScatter(props: { model: MultiProbeModel }) {
  const W = 900, H = 118, PADL = 44, PADR = 44, MID = 60;
  const geo = createMemo(() => {
    const probes = props.model.result().finalProbes;
    const maxD = Math.max(1.2, ...probes.map((p) => p.distanceAu));
    const X = (d: number) => PADL + (d / maxD) * (W - PADL - PADR);
    const dots = probes.map((p, i) => ({ x: X(p.distanceAu), y: MID + ((i % 9) - 4) * 8, active: p.status === "active" }));
    const ticks = [1, 2, 5, 10, 20, 40].filter((d) => d <= maxD * 1.02).map((d) => ({ x: X(d), label: String(d) }));
    return { X, dots, ticks, maxD };
  });
  const content = () => {
    const g = geo();
    const els: unknown[] = [];
    els.push(<line x1={PADL} y1={MID} x2={W - PADR} y2={MID} stroke="var(--muted)" stroke-opacity="0.5" stroke-width="1" />);
    els.push(<circle cx={PADL} cy={MID} r="7" fill="var(--metal)" />);
    els.push(<text x={PADL} y={MID - 12} text-anchor="middle" fill="var(--muted)" class="axis-text">Sun</text>);
    for (const t of g.ticks) {
      els.push(<line x1={t.x} y1={MID - 4} x2={t.x} y2={MID + 4} stroke="var(--muted)" stroke-width="1" />);
      els.push(<text x={t.x} y={H - 6} text-anchor="middle" fill="var(--muted)" class="axis-text">{t.label}</text>);
    }
    els.push(<text x={W - PADR} y={16} text-anchor="end" fill="var(--muted)" class="axis-text">HELIOCENTRIC DISTANCE (AU) →</text>);
    for (const d of g.dots) {
      els.push(<circle cx={d.x} cy={d.y} r="4" fill={d.active ? "var(--good)" : "var(--muted)"} opacity={d.active ? "0.95" : "0.6"} />);
    }
    return els;
  };
  return (
    <svg class="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Final fleet, each probe placed by its distance from the Sun">{content}</svg>
  );
}

const explainFleet = (m: MultiProbeModel): string => {
  const r = m.result();
  const walls: string[] = [];
  if (r.binding.vitaminLimited) walls.push("it runs out of imported parts - the electronics wall, now at fleet scale");
  if (r.binding.powerLimited) walls.push("its probes drift too far from the Sun to keep building - a spatial power wall");
  if (r.binding.capLimited) walls.push("it reaches the fleet cap you set");
  const why = walls.length ? walls.join("; and ") : "the mission window simply ends";
  return `Growth stops because ${why}.`;
};

function MultiProbeSurface(props: { model: MultiProbeModel }) {
  const m = props.model;
  const r = () => m.result();
  const s = () => m.snap();
  return (
    <PageShell title="One probe becomes a fleet - until it hits the same two walls." lede={<>Give one self-replicating probe local sunlight and imported parts and it copies itself; the copies disperse and copy again. This is a simulation of a handful of probes, not a swarm.</>} hero={<>

          <Figure caption="FIG.1 - fleet size (left axis) and how far the farthest probe has spread (bronze, right axis) over 40 years. The dashed line is the day you're scrubbed to.">
            <FleetChart model={m} />
          </Figure>
      </>} footer={<>Each probe builds at the slower of its machinery and energy limits (<strong>closure-sim</strong>), with power falling as 1/d² (<strong>probe-sim</strong>); a finite pool of imported parts and 1/d² dispersal are the two ceilings. Physics and figures trace to the cited sources<Cite ids={["nasa-cp-2255-1980", "kopp-lean-2011", "borgue-hein-2020"]} />; the factory is the lunar-regolith seed scenario used as a stand-in (the probe parts-list gap persists).</>}>

      <Band>
          <Lab>
            <Panel kind="controls" head="Fleet parameters">
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
              <div>
                <Slider p={m.scrub} />
              </div>
            </Panel>
            <Panel kind="readouts" head="At this day">
              <Stat what="Mission day" sub={() => `year ${(s().day / 365).toFixed(1)}`} value={() => `${fmtNum(s().day)} d`} />
              <Stat what="Probes alive" sub="traveling + active" value={() => fmtNum(s().population)} tone={() => "chip"} />
              <Stat what="Active (building)" value={() => fmtNum(s().active)} tone={() => "good"} />
              <Stat what="Dispersal frontier" sub="farthest probe" value={() => `${s().maxDistanceAu.toFixed(1)} AU`} tone={() => "metal"} />
              <Stat what="Mean distance" value={() => `${s().meanDistanceAu.toFixed(1)} AU`} />
              <Stat what="Imported parts left" value={() => `${fmtNum(s().vitaminPoolKg / 1000)} t`} />
              <Explain>{() => explainFleet(m)}</Explain>
            </Panel>
          </Lab>
      </Band>

      <Band title="Where the fleet ends up">
          <Figure caption="FIG.2 - the final fleet, each probe placed by its distance from the Sun. Green: still building. Grey: in transit.">
            <FleetScatter model={m} />
          </Figure>
      </Band>
    </PageShell>
  );
}

// ── the swarm surface: a settlement front filling the galaxy, live on a canvas ─
const CANVAS_W = 900, CANVAS_H = 520, CANVAS_PAD = 26;

const tc = (name: string, a = 1): string => {
  const h = token(name), m = /^#([0-9a-f]{6})$/i.exec(h);
  return m ? `rgba(${parseInt(m[1].slice(0, 2), 16)},${parseInt(m[1].slice(2, 4), 16)},${parseInt(m[1].slice(4), 16)},${a})` : h || "transparent"; // "" without a document
};

function drawSwarm(cv: HTMLCanvasElement, m: SwarmModel): void {
  const ctx = cv.getContext("2d");
  if (!ctx) return;
  const r = m.result();
  const year = m.scrubYear();
  const L = r.boxSidePc;
  const s = (CANVAS_H - 2 * CANVAS_PAD) / L; // square scale (pc → px)
  const offx = (CANVAS_W - L * s) / 2;
  const px = (x: number) => offx + x * s;
  const py = (y: number) => CANVAS_PAD + y * s;

  // Deep-space background + a soft vignette.
  ctx.globalCompositeOperation = "source-over";
  ctx.fillStyle = tc("ground");
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
  const vg = ctx.createRadialGradient(CANVAS_W / 2, CANVAS_H / 2, 0, CANVAS_W / 2, CANVAS_H / 2, CANVAS_W * 0.6);
  vg.addColorStop(0, tc("chip", 0.1));
  vg.addColorStop(1, tc("chip", 0));
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

  // Stars, drawn additively so settled clusters bloom into a glowing front.
  const flash = Math.max(1, m.maxYear() * 0.03);
  const coolSpan = Math.max(1, m.maxYear() * 0.6);
  ctx.globalCompositeOperation = "lighter";
  for (let i = 0; i < r.xs.length; i++) {
    const sy = r.settledYear[i];
    const x = px(r.xs[i]), y = py(r.ys[i]);
    if (sy >= 0 && sy <= year) {
      const age = year - sy;
      if (age < flash) {
        ctx.fillStyle = tc("text", 0.92); // just settled - a soft flash
      } else {
        const t = Math.min(1, age / coolSpan); // fades from full to half chip-blue with age
        ctx.fillStyle = tc("chip", 0.9 - 0.45 * t);
      }
      ctx.beginPath();
      ctx.arc(x, y, age < flash ? 2.8 : 2.0, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.fillStyle = tc("muted", 0.22);
      ctx.beginPath();
      ctx.arc(x, y, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  ctx.globalCompositeOperation = "source-over";
  // The wavefront: a ring at the current front radius, centred on the homeworld.
  const front = m.settledAt().frontPc;
  const ox = px(r.xs[r.origin]), oy = py(r.ys[r.origin]);
  ctx.strokeStyle = tc("metal", 0.5);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(ox, oy, front * s, 0, Math.PI * 2);
  ctx.stroke();

  // The homeworld - a warm bronze core with a soft halo.
  const halo = ctx.createRadialGradient(ox, oy, 0, ox, oy, 12);
  halo.addColorStop(0, tc("metal", 0.85));
  halo.addColorStop(1, tc("metal", 0));
  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(ox, oy, 12, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = tc("metal");
  ctx.beginPath();
  ctx.arc(ox, oy, 4, 0, Math.PI * 2);
  ctx.fill();

  // Coordination cue: the link from the homeworld to the hovered star, drawn in the rung's colour, plus a ring on the star.
  const hv = m.hoverStar();
  const info = m.hoverInfo();
  if (hv !== null && info !== null && hv < r.xs.length) {
    const hx = px(r.xs[hv]), hy = py(r.ys[hv]);
    const col = info.rung.color;
    ctx.strokeStyle = col;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(ox, oy);
    ctx.lineTo(hx, hy);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(hx, hy, 7, 0, Math.PI * 2);
    ctx.stroke();
  }
}

/** Map a canvas-space point to the nearest star index (within ~8 px), or null. */
function pickStar(m: SwarmModel, mx: number, my: number): number | null {
  const r = m.result();
  const L = r.boxSidePc;
  const s = (CANVAS_H - 2 * CANVAS_PAD) / L;
  const offx = (CANVAS_W - L * s) / 2;
  let best = -1, bestD2 = Infinity;
  for (let i = 0; i < r.xs.length; i++) {
    const x = offx + r.xs[i] * s, y = CANVAS_PAD + r.ys[i] * s;
    const d2 = (x - mx) * (x - mx) + (y - my) * (y - my);
    if (d2 < bestD2) { bestD2 = d2; best = i; }
  }
  return bestD2 <= 8 * 8 ? best : null;
}

const POLICY_LABELS: Record<string, string> = {
  powered: "Powered",
  slingshot_nearest: "Slingshot · nearest",
  slingshot_maxboost: "Slingshot · max-boost",
};

const explainSwarm = (m: SwarmModel): string => {
  const r = m.result();
  // Myr with adaptive precision - slingshot fills are sub-Myr and rounded to "0" at 0 dp.
  const myr = (y: number) => { const m = y / 1e6; return fmtNum(m, m >= 10 ? 0 : m >= 1 ? 1 : m >= 0.01 ? 2 : 3); };
  if (r.t100Years === null) {
    return `With ${m.params[1].get()} copies per settled star the front can't fill the field - raise it above zero and the reachable galaxy fills exponentially.`;
  }
  if (r.policy === "powered") {
    const probeSpeedPcPerYr = (m.params[2].get() * 3.15576e7) / 3.0856775814913673e13;
    const frontSpeedFrac = (r.frontRadiusPc / r.t100Years) / probeSpeedPcPerYr * 100;
    return `Powered flight: from one homeworld the front settles all ${r.nStars} stars in ${myr(r.t100Years)} Myr, the wavefront advancing at only ~${frontSpeedFrac.toFixed(0)}% of a probe's speed.`;
  }
  const tail = r.policy === "slingshot_maxboost"
    ? "Chasing the biggest boost reaches higher speeds but wastes travel, so it's actually slower than nearest-star - as Nicholson & Forgan found."
    : "Nearest-star slingshots stay the most time-effective policy (Nicholson & Forgan's headline).";
  return `Slingshots: probes steal speed from the stars' galactic motion, peaking at ${fmtNum(r.maxProbeSpeedKmS)} km/s (from a ${fmtNum(m.params[2].get())} km/s powered cruise). ${tail}`;
};

const SEC_PER_YEAR = 3.15576e7;
/** A light-time / latency in years, shown in whatever unit reads cleanly. */
const fmtLatency = (years: number): string => {
  const sec = years * SEC_PER_YEAR;
  if (sec < 1) return `${(sec * 1000).toFixed(sec < 0.01 ? 2 : 1)} ms`;
  if (sec < 60) return `${sec.toFixed(2)} s`;
  if (sec < 3600) return `${(sec / 60).toFixed(1)} min`;
  if (sec < 86400) return `${(sec / 3600).toFixed(1)} hr`;
  if (years < 1) return `${(years * 365.25).toFixed(0)} d`;
  return `${fmtNum(years, years < 100 ? 1 : 0)} yr`;
};

// The coordination-mode readout for the hovered star.
const explainCoord = (m: SwarmModel): string => {
  const info = m.hoverInfo();
  if (info === null)
    return "Coordination is set by ρ = round-trip light-time ÷ decision timescale: when ρ ≪ 1 news arrives while it's still current and tight control is possible; when ρ ≳ 1 the world changes faster than word of it arrives. Every ~1 pc hop in this galaxy already means light-years of lag, so each settled system must run as an autonomous colony, with its behaviour set before launch.";
  if (info.isOrigin) return "That's the homeworld - zero lag to itself. Hover another star to see the light-speed gap open up.";
  return `This star is ${info.distPc.toFixed(2)} pc from home. A signal takes ${fmtLatency(info.oneWayYears)} one way, ${fmtLatency(info.roundTripYears)} round-trip - that's ρ ≈ ${info.rho < 0.001 ? fmtSci(info.rho, 1) : fmtNum(info.rho, 2)} against a ${fmtNum(m.decisionTimescale(), 2)}-yr decision cadence. Coordination mode: ${info.rung.label} (${info.rung.who}), the ${info.rung.analog} regime.`;
};

function RungLegend(props: { model: SwarmModel }) {
  const m = props.model;
  const activeKey = () => m.hoverInfo()?.rung.key ?? null;
  return (
    <ActionRow>
      <For each={() => RUNGS}>
        {(rung) => (
          <span
            class={() => `note rung-chip ${activeKey() === rung.key ? "rung-active" : activeKey() === null ? "" : "rung-dim"}`}
          >
            <span class="rung-dot" style={`background:${rung.color}`} />
            {rung.label} <span class="rung-analog">· {rung.analog}</span>
          </span>
        )}
      </For>
    </ActionRow>
  );
}

function SwarmSurface(props: { model: SwarmModel }) {
  const m = props.model;
  const [canvas, setCanvas] = createSignal<HTMLCanvasElement | null>(null);

  // Draw whenever the field (knobs/seed) or the scrubbed year changes - a single effect reading the fold's buffers (§7), never a DOM node per star.
  createEffect(() => {
    const cv = canvas();
    if (cv) drawSwarm(cv, m);
  });

  // Play: advance the scrubber toward the end over ~240 frames; stop at the end.
  createEffect(() => {
    if (!m.playing()) return;
    let raf = 0;
    const tick = () => {
      const mx = m.maxYear();
      const cur = m.scrubYear();
      if (cur >= mx) { m.setPlaying(false); return; }
      m.setScrubYear(Math.min(mx, cur + mx / 240));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    onCleanup(() => cancelAnimationFrame(raf));
  });

  const togglePlay = () => {
    if (m.scrubYear() >= m.maxYear()) m.setScrubYear(0);
    m.setPlaying(!m.playing());
  };
  const pct = () => (m.result().nStars ? (m.settledAt().count / m.result().nStars) * 100 : 0);
  // % slowdown of the fill-100% timescale vs the perfect-info baseline (only in lightspeed).
  const slowdownPct = (): number | null => {
    const b = m.instantBaseline();
    const r = m.result();
    if (!b || !b.t100Years || !r.t100Years) return null;
    return ((r.t100Years - b.t100Years) / b.t100Years) * 100;
  };
  const wastedPct = () => { const r = m.result(); return r.totalArrivals ? (r.wastedArrivals / r.totalArrivals) * 100 : 0; };

  return (
    <PageShell title="One probe. Then the galaxy fills in." lede={<>Give a self-replicating probe a galaxy and it settles a star, builds copies and sends them to the next nearest stars. This is that front as a simulation.</>} hero={<>

          <Figure caption={<>FIG.1 - the star field. Bronze: the homeworld. Settled stars: those reached by the scrubbed year (pale flash = just settled). Grey: not yet reached. The bronze ring is the settlement wavefront. <b>Hover any star</b> to read its light-speed coordination lag from home.</>}>
            <canvas
              ref={setCanvas}
              width={CANVAS_W}
              height={CANVAS_H}
              class="swarm-canvas"
              onMouseMove={(e: MouseEvent) => {
                const cv = e.currentTarget as HTMLCanvasElement;
                const rect = cv.getBoundingClientRect();
                const mx = (e.clientX - rect.left) * (cv.width / rect.width);
                const my = (e.clientY - rect.top) * (cv.height / rect.height);
                m.setHoverStar(pickStar(m, mx, my));
              }}
              onMouseLeave={() => m.setHoverStar(null)}
            />
          </Figure>
          <ActionRow>
            <Action kind="primary" onClick={togglePlay}>{() => (m.playing() ? "⏸ pause" : "▶ play")}</Action>
            <input
              type="range"
              aria-label="Mission year (scrub the settlement front)"
              min={0}
              max={() => m.maxYear()}
              step={() => Math.max(1, m.maxYear() / 400)}
              value={() => m.scrubYear()}
              onInput={(e: Event) => { m.setPlaying(false); m.setScrubYear(Number((e.target as HTMLInputElement).value)); }}
              class="scrub"
            />
            <span class="ctl-val scrub-readout">{() => fmtNum(m.scrubYear())} yr</span>
          </ActionRow>
          <ActionRow>
            <span class="note">travel policy:</span>
            <For each={() => ["powered", "slingshot_nearest", "slingshot_maxboost"] as const}>
              {(pol: "powered" | "slingshot_nearest" | "slingshot_maxboost") => (
                <button
                  class={() => `act ${m.policy() === pol ? "act-primary" : "act-ghost"}`}
                  onClick={() => { m.setPolicy(pol); m.setPlaying(false); m.setScrubYear(m.maxYear()); }}
                >{POLICY_LABELS[pol]}</button>
              )}
            </For>
          </ActionRow>
          <ActionRow>
            <span class="note">coordination:</span>
            <For each={() => ["instant", "lightspeed"] as const}>
              {(mode: "instant" | "lightspeed") => (
                <button
                  class={() => `act ${m.coordination() === mode ? "act-primary" : "act-ghost"}`}
                  onClick={() => { m.setCoordination(mode); m.setPlaying(false); m.setScrubYear(m.maxYear()); }}
                >{mode === "instant" ? "Perfect info" : "Light-speed lag"}</button>
              )}
            </For>
          </ActionRow>
      </>} footer={<>Three travel policies (powered, and two gravitational-slingshot policies that steal speed from stellar motion) after Nicholson &amp; Forgan (2013)<Cite ids="nicholson-forgan-2013" />; powered speed (3×10⁻⁵c ≈ 9 km/s), density (1 star/pc³), and the slingshot boost (their Eq. 4, u_esc ≈ 617.5 km/s solar) are the paper's parameters, with rotation/dispersion tagged [ESTIMATE]. The coordination-lag overlay turns each link's light-lag into a coordination mode after Olfati-Saber &amp; Murray (2004), Ferrell (1965) and RFC 4838<Cite ids={["olfati-saber-murray-2004", "ferrell-1965", "rfc-4838"]} />; mode edges tagged [ESTIMATE]. Not built: a 200k-star WebGL renderer.</>}>

      <Band>
          <Lab>
            <Panel kind="controls" head="Parameters">
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
            </Panel>
            <Panel kind="readouts" head="At this year">
              <Stat what="Year" value={() => `${fmtNum(m.scrubYear())} yr`} />
              <Stat what="Stars settled" sub={() => `of ${fmtNum(m.result().nStars)}`} value={() => `${fmtNum(m.settledAt().count)} (${pct().toFixed(0)}%)`} tone={() => "chip"} />
              <Stat what="Wavefront radius" value={() => `${m.settledAt().frontPc.toFixed(1)} pc`} tone={() => "metal"} />
              <Stat what="Fill 50% / 90%" sub="exploration timescale" value={() => `${fmtNum(m.result().t50Years ?? 0)} / ${fmtNum(m.result().t90Years ?? 0)} yr`} />
              <Stat what="Fill 100%" value={() => (m.result().t100Years === null ? "never" : `${fmtNum(m.result().t100Years!)} yr`)} tone={() => (m.result().t100Years === null ? "bad" : "good")} />
              <Stat what="Probes launched" value={() => fmtNum(m.result().totalProbesLaunched)} />
              <Stat what="Peak probe speed" cite="nicholson-forgan-2013" sub="powered = the cruise; slingshots accumulate" value={() => `${fmtNum(m.result().maxProbeSpeedKmS)} km/s`} tone={() => (m.result().policy === "powered" ? "plain" : "good")} />
              <Stat what="Wasted trips" sub="arrivals at an already-settled star" value={() => `${fmtNum(m.result().wastedArrivals)} (${wastedPct().toFixed(0)}%)`} tone={() => (m.coordination() === "lightspeed" ? "chip" : "plain")} />
              <Stat what="Slowdown vs perfect info" sub="the cost of light-speed lag" value={() => (slowdownPct() === null ? "-" : `+${slowdownPct()!.toFixed(0)}%`)} tone={() => { const s = slowdownPct(); return s === null ? "plain" : s > 5 ? "bad" : "good"; }} />
              <Explain>{() => explainSwarm(m)}</Explain>
            </Panel>
          </Lab>
      </Band>

      <Band title="At interstellar distances, light-lag decides how the swarm coordinates">
          <Lab>
            <Panel kind="controls" head="The coordination ratio">
              <Note>
                ρ = round-trip light-time ÷ decision timescale. The coordination mode of a link is fixed by its <em>absolute</em> light-lag (sourced from teleoperation and delay-tolerant networking regimes); ρ is a tunable lens - set the decision cadence you care about.
              </Note>
              <div class="ctl">
                <div class="ctl-top">
                  <span class="ctl-label">Decision timescale <span class="note">τ · [ESTIMATE]</span></span>
                  <span class="ctl-val">{() => `${fmtNum(m.decisionTimescale(), 2)} yr`}</span>
                </div>
                <input
                  type="range"
                  aria-label="Decision timescale (years)"
                  min={0.01}
                  max={100}
                  step={0.01}
                  value={() => m.decisionTimescale()}
                  onInput={(e: Event) => m.setDecisionTimescale(Number((e.target as HTMLInputElement).value))}
                  class="tau-slider"
                />
              </div>
              <p class="panel-head">Coordination modes</p>
              <RungLegend model={m} />
            </Panel>
            <Panel kind="readouts" head="The hovered star">
              <Stat what="Distance from home" value={() => (m.hoverInfo() ? `${m.hoverInfo()!.distPc.toFixed(2)} pc` : "-")} tone={() => "metal"} />
              <Stat what="One-way light time" value={() => (m.hoverInfo() ? fmtLatency(m.hoverInfo()!.oneWayYears) : "-")} />
              <Stat what="Round-trip latency" sub="a message and its reply" value={() => (m.hoverInfo() ? fmtLatency(m.hoverInfo()!.roundTripYears) : "-")} tone={() => "metal"} />
              <Stat what="ρ = latency ÷ τ" value={() => { const i = m.hoverInfo(); return i ? (i.rho < 0.001 ? `${fmtSci(i.rho, 1)}×` : `${fmtNum(i.rho, 2)}×`) : "-"; }} tone={() => { const i = m.hoverInfo(); return i && i.rho >= 1 ? "bad" : i ? "good" : "plain"; }} />
              <Stat what="Coordination mode" sub={() => (m.hoverInfo() ? m.hoverInfo()!.rung.analog + " regime" : "hover a star")} value={() => (m.hoverInfo() ? m.hoverInfo()!.rung.label : "-")} tone={() => { const i = m.hoverInfo(); return i && i.rung.index >= 3 ? "bad" : i && i.rung.index >= 2 ? "chip" : i ? "good" : "plain"; }} />
              <Explain>{() => explainCoord(m)}</Explain>
            </Panel>
          </Lab>
      </Band>
    </PageShell>
  );
}

// ── the spine surface: one factory threaded through all three scales ─────────
function SpineSurface(props: { model: SpineModel }) {
  const m = props.model;
  const r = () => m.result();
  // The dwell's galactic cost, in words: measured A/B for the fast policies, the analytic fraction for powered (where a brute-force A/B is infeasible - itself the finding).
  const taxLabel = () => {
    const t = m.dwellTax();
    if (t && t.taxFraction !== null && t.t100ZeroDwell !== null && t.t100WithDwell !== null)
      return `+${(t.taxFraction * 100).toFixed(2)}% (${fmtNum(t.t100ZeroDwell)} → ${fmtNum(t.t100WithDwell)} yr)`;
    const f = r().dwellFractionOfT100;
    return f === null ? "-" : `~${fmtSci(f, 1)} of fill`;
  };
  return (
    <PageShell title="One factory. Three scales. The same build time, weighed at each." lede={<>The project models self-replication at three scales: a <strong>single factory</strong>, a <strong>local fleet</strong> and a <strong>galaxy</strong>. This model threads <strong>one</strong> factory through all three. The galaxy model's per-star dwell (the time a settled star spends building before its next probes launch) was an unsourced <em>zero</em>; here it is derived from the fleet's factory build physics, and it is a negligible tax because interstellar travel dwarfs it.</>} hero={<>

          <Panel kind="plain">
            <p class="panel-head">The cross-scale reading</p>
            <Explain>{() => r().verdict}</Explain>
          </Panel>
      </>} footer={<>The galactic dwell is derived from the factory's 1-AU copy time (closure and machinery from NASA CP-2255 (1980)<Cite ids="nasa-cp-2255-1980" /> and Borgue &amp; Hein (2020)<Cite ids="borgue-hein-2020" />; the exploration timescale from Nicholson &amp; Forgan (2013)<Cite ids="nicholson-forgan-2013" />).</>}>

      <Band>
          <Lab>
            <Panel kind="controls" head="The galaxy">
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
              <ActionRow>
                <span class="note">travel policy:</span>
                <For each={() => ["powered", "slingshot_nearest", "slingshot_maxboost"] as const}>
                  {(pol: "powered" | "slingshot_nearest" | "slingshot_maxboost") => (
                    <button class={() => `act ${m.policy() === pol ? "act-primary" : "act-ghost"}`} onClick={() => m.setPolicy(pol)}>{POLICY_LABELS[pol]}</button>
                  )}
                </For>
              </ActionRow>
              <Note>The dwell tax is measured directly (re-running the fill with the derived dwell and with zero) only for the slingshot policies; for powered, resolving a roughly one-year dwell against hundred-thousand-year hops by brute force is impractical - so the analytic fraction is shown instead.</Note>
            </Panel>
            <Panel kind="readouts" head="The shared factory, and what it derives">
              <Stat what="Closure ratio" cite="nasa-cp-2255-1980" sub="one factory, read once, used by every scale" value={() => `${(r().closureRatio * 100).toFixed(1)}%`} tone={() => "metal"} />
              <Stat what="Time to build one copy" cite="borgue-hein-2020" sub="derived at 1 AU · the cross-scale handoff" value={() => fmtDays(r().copyTimeDays)} tone={() => "chip"} />
              <Stat what="Galactic dwell (was)" sub="the old unsourced estimate" value={() => "0 yr (instant)"} tone={() => "bad"} />
              <Stat what="Galactic dwell (now)" sub="derived, not guessed" value={() => `${fmtNum(r().settleTimeYears, 1)} yr`} tone={() => "good"} />
              <Stat what="Manufacturing tax on the fill" cite="nicholson-forgan-2013" sub="cost of a real dwell vs. instant" value={taxLabel} tone={() => (m.policy() === "powered" ? "plain" : "chip")} />
            </Panel>
          </Lab>
      </Band>

      <Band title="The same build time, at three scales">
          <MissionStage n="01" title="One factory - the build cadence is set"
            value={() => `${fmtDays(r().copyTimeDays)} per copy`}
            tone={() => "chip"}
            note={() => `The seed factory is ${(r().closureRatio * 100).toFixed(1)}% closed and reaches full output in ${fmtDays(r().singleFactoryTimeToTargetDays)}. The number that travels up the scales is the time to build one copy's worth of local structure at 1 AU, ${fmtDays(r().copyTimeDays)}. Every scale below reuses it.`} />
          <MissionStage n="02" title="Local fleet - here the build time is the clock"
            value={() => `doubles in ${fmtDays(r().fleetDoublingDays)}`}
            tone={() => "chip"}
            note={() => `Across AU distances transit is days, so replication time dominates: the fleet's first doubling lands at ~${fmtDays(r().fleetDoublingDays)} - essentially the ${fmtDays(r().copyTimeDays)} copy time above. It grows to ${fmtNum(r().fleetFinalPopulation)} probes and ends ${r().fleetBinding}.`} />
          <MissionStage n="03" title="Galaxy - the same dwell all but vanishes"
            value={() => (r().swarmT100Years === null ? "never fills" : `fills in ${fmtNum(r().swarmT100Years!)} yr`)}
            tone={() => (r().swarmT100Years === null ? "bad" : "good")}
            note={() => (r().swarmT100Years === null
              ? `With these settings the front cannot spread (no copies), so the field never fills and the dwell is moot.`
              : `The front reaches all ${fmtNum(r().nStars)} stars in ${fmtNum(r().swarmT100Years!)} yr under the ${POLICY_LABELS[r().policy]} policy. The dwell that governs the fleet is only ${taxLabel()} of that - interstellar transit dominates by orders of magnitude, so the manufacturing cadence that is the clock for a fleet is a rounding error for a galaxy.`)} />
      </Band>
    </PageShell>
  );
}

// ── the overview surface: what the project is, and where it is ───────────────
type ModuleRow = { name: string; surface: Surface; status: string; statusCls: string; cite: string; desc: string };
const MODULE_STATUS: ModuleRow[] = [
  { name: "closure-sim", surface: "wall", status: "Done", statusCls: "good", cite: "nasa-cp-2255-1980",
    desc: "Models a factory as a parts list, computes its closure (the fraction of its own weight it can build from local material) and finds the electronics wall: chips." },
  { name: "power-budget", surface: "power", status: "Done", statusCls: "good", cite: "landauer-1961",
    desc: "Splits a solar-limited power budget between building, thinking, and housekeeping, floored by the Landauer thermodynamic limit and scaled against the roughly 20-watt human brain." },
  { name: "launch-economics", surface: "launch", status: "Done", statusCls: "good", cite: "tsiolkovsky-1903",
    desc: "Measures the launch-mass leverage of shipping a self-replicating seed instead of a finished factory - installed kilograms per launched kilogram, as a function of closure." },
  { name: "mission", surface: "mission", status: "Done", statusCls: "good", cite: "kopp-lean-2011",
    desc: "Runs the whole operation end to end as one deterministic pass over the four models above: launch, arrive, split power, replicate, and price the payoff." },
  { name: "multi-probe", surface: "fleet", status: "Done (v1)", statusCls: "good", cite: "borgue-hein-2020",
    desc: "A deterministic fleet of tens of probes that reproduces two limits from first principles: a finite pool of imported parts and a spatial power wall." },
  { name: "probe-sim", surface: "probe", status: "In progress", statusCls: "chip", cite: "borgue-hein-2020",
    desc: "Models a single solar-electric probe after Borgue and Hein (2020). The solar-power and range math is live; the full replication model waits on a per-module mass breakdown that does not exist in the literature yet." },
  { name: "swarm", surface: "swarm", status: "In progress", statusCls: "chip", cite: "nicholson-forgan-2013",
    desc: "Models how fast a probe fills the galaxy, after Nicholson and Forgan (2013): the core, all three slingshot policies, a coordination-lag overlay and a light-speed-limited coordination simulation. Parked: a WebGL renderer for 200,000 stars." },
  { name: "spine", surface: "spine", status: "Done", statusCls: "good", cite: "nicholson-forgan-2013",
    desc: "Cross-scale integrator: one factory through all three scales, so replication cadences are derived from one source. It replaces the galaxy model's unsourced zero dwell with a derived figure, a negligible tax on galactic exploration." },
];

// The project's stated research conclusions, each backed by a source and a live surface.
type FindingRow = { headline: string; surface: Surface; cite: string | string[]; detail: string };
const FINDINGS: FindingRow[] = [
  { headline: "Chips are the wall - made of energy as much as supply chain", surface: "wall",
    cite: ["williams-ayres-heller-2002", "nagapurkar-das-2022"],
    detail: "Compute logic costs roughly 8,000 kWh/kg to make against about 5 for smelted metal. A factory escapes the wall only if it is both highly self-sufficient and swimming in power: the lunar seed reaches its target in ~17 years instead of ~29 by making its own chips, but only when fed ~4 MW; at ~1 MW that backfires." },
  { headline: "The realistic factory never closes on chips", surface: "wall",
    cite: ["guided-self-replicating-factory-2021", "nasa-cp-2255-1980"],
    detail: "Achievable mass closure is about 70 to 96 percent, and chasing 100 percent is not worth it, so imported electronics are a permanent design feature." },
  { headline: "Thinking is thermodynamically cheap but practically expensive", surface: "power",
    cite: "landauer-1961",
    detail: "The Landauer floor sits some 9 to 11 orders of magnitude below real hardware, so a probe's onboard intelligence is limited by hardware efficiency and waste heat, not by physics. The ~20 W human brain is the scale marker." },
  { headline: "Launch-mass leverage is the whole case, and scales as 1/(1-closure)", surface: "launch",
    cite: "tsiolkovsky-1903",
    detail: "Mass balance forces (1-C) kg imported per kg built, so installed-per-launched mass is about 3x at 67 percent closure and about 33x at 97 percent - and the rocket equation makes the cost of shipping instead exponential in the distance." },
  { headline: "A solar probe's reach is set by the inverse-square law", surface: "probe",
    cite: ["kopp-lean-2011", "borgue-hein-2020"],
    detail: "Delivered power falls from ~1361 W/m2 at Earth to ~50 at Jupiter: twice the distance, a quarter the power and a quarter the compute. Replication stalls where the power budget drops below the build demand." },
  { headline: "At fleet scale, two ceilings emerge on their own", surface: "fleet",
    cite: "borgue-hein-2020",
    detail: "The finite pool of imported parts caps how many copies can ever exist (the electronics wall made spatial), and a spatial power wall stops expansion around 13.6 AU for the default scenario - not for lack of parts, but distance from the Sun." },
  { headline: "Filling the galaxy: slingshots dominate, nearest beats max-boost", surface: "swarm",
    cite: "nicholson-forgan-2013",
    detail: "A powered front advances at only ~40 percent of a probe's cruise speed. Gravitational slingshots reach ~1000 km/s and are far faster - and targeting the nearest star beats chasing the biggest boost on total time." },
  { headline: "Light-speed coordination is a real, policy-dependent tax", surface: "swarm",
    cite: ["nicholson-forgan-2013", "olfati-saber-murray-2004"],
    detail: "Deciding against a light-delayed belief of what is already settled costs a median ~30 percent of the exploration timescale for nearest-slingshot, ~50 for max-boost, and ~0 for powered flight. A connected field still fills completely - lag alone makes no permanent plateau." },
  { headline: "Which constraint binds at which scale", surface: "spine",
    cite: "nicholson-forgan-2013",
    detail: "The factory's own build physics fixes a ~582-day copy time, which is the local fleet's doubling clock - yet only ~8e-7 of a ~2-million-year galactic fill (about 0.4 percent of exploration time even for fast slingshots)." },
];

function OverviewSurface() {
  return (
    <PageShell title="What if you launched one factory, and it built the rest?" lede="A self-replicating factory lands on the Moon, an asteroid or Mars, digs up local material and builds a copy of itself. One becomes two, two become four. You launch one seed instead of a finished installation. This site is a set of small live models that test how far that holds." hero={<>

          <ActionRow>
            <Action kind="primary" onClick={() => mount("mission")}>Start with the full mission</Action>
            <Action onClick={() => mount("wall")}>See the electronics wall</Action>
            <Action onClick={() => mount("swarm")}>Watch the galaxy fill</Action>
            <Action kind="ghost" onClick={() => mount("sources")}>Sources</Action>
          </ActionRow>
      </>} footer={<>Every figure links to its source on the <a href="/sources" onClick={(e: Event) => { e.preventDefault(); mount("sources"); }}>Sources</a> page, and gaps are marked as gaps. Built on <strong>pimas</strong>.</>}>

      <Band title="Research models, not predictions.">
          <p>
            These are order-of-magnitude models. They show which physical limits bind and roughly how hard, not a schedule. Each model covers one slice, runs and is tested alone, and connects to the others through clean interfaces.
          </p>
          <p>
            <strong>No number is assumed.</strong> Every mass, energy, rate and cost traces to a published source or is derived by explicit math from numbers that do<Cite ids={["nasa-cp-2255-1980", "kopp-lean-2011", "landauer-1961"]} />. Where the literature has no value, the gap is marked and not filled. Best-defensible estimates are labelled as estimates. The models are pure and deterministic: same inputs and seed, same result.
          </p>
          <Note>
            Every figure on this site carries a marker like this<Cite ids="borgue-hein-2020" /> - hover or tab to it for the exact paper and what it grounds. The full list is on the <a href="/sources" onClick={(e: Event) => { e.preventDefault(); mount("sources"); }}>Sources</a> page.
          </Note>
      </Band>

      <Band title="A physical wall reappears at every scale.">
          <p>
            Self-replication buys large launch-mass leverage.
          </p>
          <Panel kind="plain">
            <For each={() => FINDINGS}>
              {(f: FindingRow) => (
                <div class="mod-row" onClick={() => mount(f.surface)} tabindex="0" role="button"
                  onKeyDown={(e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); mount(f.surface); } }}>
                  <div class="mod-head">
                    <span class="mod-name">{f.headline}</span>
                    <Cite ids={f.cite} />
                  </div>
                  <p class="mod-desc">{f.detail}</p>
                </div>
              )}
            </For>
          </Panel>
      </Band>

      <Band title="Eight models. Six complete, two in progress.">
          <p>
            The plan is upwards of ten models. Eight exist today.
          </p>
          <Panel kind="plain">
            <For each={() => MODULE_STATUS}>
              {(m: ModuleRow) => (
                <div class="mod-row" onClick={() => mount(m.surface)} tabindex="0" role="button"
                  onKeyDown={(e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); mount(m.surface); } }}>
                  <div class="mod-head">
                    <span class="mod-name">{m.name}</span>
                    <span class={`mod-status ${m.statusCls}`}>{m.status}</span>
                    <Cite ids={m.cite} />
                  </div>
                  <p class="mod-desc">{m.desc}</p>
                </div>
              )}
            </For>
          </Panel>
      </Band>

      <Band title="Open gaps">
          <ul class="gaps">
            <li><strong>The probe bill-of-materials.</strong> There is no sourced per-module mass breakdown for the Borgue and Hein probe<Cite ids="borgue-hein-2020" />, which blocks probe-sim and forces the mission model onto the lunar-regolith factory as a stand-in.</li>
            <li><strong>The 200,000-star WebGL renderer.</strong> The swarm's algorithm already scales; drawing 200,000 stars at full frame rate is a parked rendering fork, since the current canvas tops out around ten thousand.</li>
            <li><strong>Deferred swarm coordination features.</strong> Probe-to-probe relaying of news, probes lost along the way, and a faster arrival lookup for the largest scales are deferred.</li>
          </ul>
      </Band>
    </PageShell>
  );
}

// ── the sources surface: the whole bibliography, one place ───────────────────
const STRENGTH_NOTE: Record<string, string> = {
  primary: "peer-reviewed paper, standards document, or agency technical report",
  reference: "definitional constant or reference data (CODATA, IAU, agency fact sheet)",
  grey: "preprint or non-refereed but serious",
  vendor: "figure published by a manufacturer or company",
  wiki: "community-edited wiki, used only as a cross-check",
};

function SourcesSurface() {
  return (
    <PageShell title="Sources">

      <For each={() => sourceCategories()}>
        {(cat: string) => {
          const inCat = () => SOURCES.filter((s) => s.category === cat);
          return (
            <Band title={cat}>
                <Accordion title="Sources" count={() => inCat().length}>
                  <For each={inCat}>
                    {(s: Source) => (
                      <div class="src">
                        <div class="src-top">
                          <span class="src-num">[{sourceNumber(s.id)}]</span>
                          <span class="src-cite"><b>{s.authors}</b> ({s.year}). {s.title}. <i>{s.venue}</i>.</span>
                        </div>
                        <div class="src-meta">
                          <span class={`src-strength st-${s.strength}`} title={STRENGTH_NOTE[s.strength]}>{STRENGTH_LABEL[s.strength]}</span>
                          <span class="src-mods">relevant to: {s.modules.join(", ")}</span>
                        </div>
                        <p class="src-grounds">{s.grounds}</p>
                        {s.url
                          ? <a class="src-link" href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a>
                          : <span class="src-nolink">Cited by full reference; no stable public link (textbook, standards resolution, or paywalled record).</span>}
                      </div>
                    )}
                  </For>
                </Accordion>
            </Band>
          );
        }}
      </For>

      <Band title="Gaps and estimates">
          <p>
            Two kinds of number are called out at their use sites rather than sourced as fact, because no source exists today:
          </p>
          <ul class="gaps">
            <li><strong>[GAP] - the probe bill-of-materials.</strong> Borgue and Hein<Cite ids="borgue-hein-2020" /> give six modules and a 70/30 replicated-to-imported split, but not per-module masses at the detail a closure computation needs. No masses are invented; probe-sim and the mission model use a real lunar-regolith factory as a stand-in until a defensible breakdown exists.</li>
            <li><strong>[ESTIMATE] - values the literature brackets but does not pin.</strong> Examples: brain-equivalent compute (~1e18 FLOPS, uncertain by ~2 orders of magnitude)<Cite ids="sandberg-bostrom-2008" />; the stars' galactic velocity in the slingshot model (~220 +/- 40 km/s), which Nicholson and Forgan defer<Cite ids="nicholson-forgan-2013" />; the coordination decision-timescale and rung edges<Cite ids={["ferrell-1965", "olfati-saber-murray-2004", "rfc-4838"]} />; and solar-cell and compute efficiencies, which are scenario inputs, not constants. Each is labelled [ESTIMATE] with its reasoning where it is used.</li>
          </ul>
      </Band>
    </PageShell>
  );
}

// Papers surface: LaTeX write-ups listed from papers-index.ts (generated by papers/scripts/gen-index.mjs), with every cited id validated against the same SOURCES bibliography that powers the <Cite> markers.
function PapersSurface() {
  return (
    <PageShell title="Papers">

      <Show when={() => PAPERS.length > 0} fallback={(
        <Band><Note>No papers published yet.</Note></Band>
      )}>
        <For each={() => PAPERS}>
          {(p: PaperMeta, i: () => number) => (
            <Band title={p.title}>
                <Note>
                  {p.date}{" . "}
                  {() => p.authors.map((a, i) => {
                    const label = a.affiliation ? `${a.name} (${a.affiliation})` : a.name;
                    return a.orcid
                      ? <span>{i > 0 ? ", " : ""}{label} <a href={`https://orcid.org/${a.orcid}`} target="_blank" rel="noopener noreferrer">ORCID {a.orcid}</a></span>
                      : <span>{i > 0 ? ", " : ""}{label}</span>;
                  })}
                </Note>
                <p>{p.abstract}</p>
                <p class="legend">{() => p.keywords.join("  .  ")}</p>
                {p.doi ? (
                  <Note>
                    DOI: <a class="src-link" href={`https://doi.org/${p.doi}`} target="_blank" rel="noopener noreferrer">{p.doi}</a>
                    {p.doiIsSandbox ? " (sandbox; not a citable identifier)" : ""}
                  </Note>
                ) : null}
                <p><a class="src-link" href={p.pdf} target="_blank" rel="noopener noreferrer">Read the latest typeset PDF ({p.pdf})</a></p>
                {/* Every commit touching this paper is a version (issue #7). Each row
                    links its archived PDF when one exists, else the frozen source on
                    GitHub. The list is git-derived at build time (PAPER_VERSIONS). */}
                <Show when={() => (PAPER_VERSIONS[p.slug] || []).length > 1}>
                  <Accordion title="Versions" count={() => (PAPER_VERSIONS[p.slug] || []).length}>
                    <For each={() => PAPER_VERSIONS[p.slug] || []}>
                      {(v: VersionMeta, i: () => number) => (
                        <div class="src">
                          <div class="src-top">
                            <span class="src-num">{() => (i() === 0 ? "latest" : v.shortSha)}</span>
                            <span class="src-cite"><b>{v.date}</b> &nbsp;/&nbsp; {v.subject}</span>
                          </div>
                          {v.hasPdf
                            ? <a class="src-link" href={v.pdf} target="_blank" rel="noopener noreferrer">{v.pdf}</a>
                            : <a class="src-link" href={v.sourceUrl} target="_blank" rel="noopener noreferrer">source at {v.shortSha} (PDF not archived)</a>}
                        </div>
                      )}
                    </For>
                  </Accordion>
                </Show>
                <Accordion title="References" count={() => p.cites.length}>
                  <For each={() => p.cites}>
                    {(id: string) => {
                      const s = sourceById(id);
                      return s ? (
                        <div class="src">
                          <div class="src-top">
                            <span class="src-num">[{sourceNumber(id)}]</span>
                            <span class="src-cite"><b>{s.authors}</b> ({s.year}). {s.title}. <i>{s.venue}</i>.</span>
                          </div>
                          {s.url ? <a class="src-link" href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a> : null}
                        </div>
                      ) : null;
                    }}
                  </For>
                </Accordion>
            </Band>
          )}
        </For>
      </Show>
    </PageShell>
  );
}

// Mount + routing: a shell hosting one surface per model, with the surface kept in the real pathname (/swarm, /wall/low_closure - see routes.ts) so views are shareable and Back/Forward and refresh work; build.mjs emits a real file per path.
const appEl = document.getElementById("app")!;
let disposeRender: (() => void) | null = null;
let model: WallModel | null = null;

function mount(surface: Surface, scenarioKey = DEFAULT_SCENARIO, updateUrl = true) {
  disposeRender?.();
  model?.dispose();
  model = null;
  if (surface === "overview") {
    disposeRender = render(() => (<Shell><Nav surface="overview" /><OverviewSurface /></Shell>), appEl);
  } else if (surface === "sources") {
    disposeRender = render(() => (<Shell><Nav surface="sources" /><SourcesSurface /></Shell>), appEl);
  } else if (surface === "papers") {
    disposeRender = render(() => (<Shell><Nav surface="papers" /><PapersSurface /></Shell>), appEl);
  } else if (surface === "wall") {
    model = createWallModel(SCENARIOS[scenarioKey]);
    const active = model;
    disposeRender = render(
      () => (
        <Shell>
          <Nav surface="wall" />
          <App model={active} scenarioKey={scenarioKey} onScenario={(k: string) => mount("wall", k)} />
        </Shell>
      ),
      appEl,
    );
  } else if (surface === "launch") {
    const lm = createLaunchEconomicsModel();
    disposeRender = render(
      () => (
        <Shell>
          <Nav surface="launch" />
          <LaunchSurface model={lm} />
        </Shell>
      ),
      appEl,
    );
  } else if (surface === "power") {
    const pm = createPowerBudgetModel();
    disposeRender = render(
      () => (
        <Shell>
          <Nav surface="power" />
          <PowerBudgetSurface model={pm} />
        </Shell>
      ),
      appEl,
    );
  } else if (surface === "mission") {
    const mm = createMissionModel();
    disposeRender = render(
      () => (
        <Shell>
          <Nav surface="mission" />
          <MissionSurface model={mm} />
        </Shell>
      ),
      appEl,
    );
  } else if (surface === "fleet") {
    const fm = createMultiProbeModel();
    disposeRender = render(
      () => (
        <Shell>
          <Nav surface="fleet" />
          <MultiProbeSurface model={fm} />
        </Shell>
      ),
      appEl,
    );
  } else if (surface === "swarm") {
    const sm = createSwarmModel();
    disposeRender = render(
      () => (
        <Shell>
          <Nav surface="swarm" />
          <SwarmSurface model={sm} />
        </Shell>
      ),
      appEl,
    );
  } else if (surface === "spine") {
    const spm = createSpineModel();
    disposeRender = render(
      () => (
        <Shell>
          <Nav surface="spine" />
          <SpineSurface model={spm} />
        </Shell>
      ),
      appEl,
    );
  } else {
    const prm = createProbeModel();
    disposeRender = render(
      () => (
        <Shell>
          <Nav surface="probe" />
          <ProbeSurface model={prm} />
        </Shell>
      ),
      appEl,
    );
  }

  document.title = SURFACE_TITLE[surface];
  if (updateUrl) {
    const path = pathForSurface(surface, scenarioKey);
    if (location.pathname !== path) history.pushState(null, "", path);
  }
}

// Back/Forward: re-mount from the new pathname (without pushing another history entry).
window.addEventListener("popstate", () => {
  const { surface, scenarioKey } = parsePath(location.pathname);
  mount(surface, scenarioKey, false);
});

// Intercept same-origin link clicks so in-site navigation stays client-side (pushState) instead of a full reload.
document.addEventListener("click", (e: MouseEvent) => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = (e.target as HTMLElement).closest?.("a[href]") as HTMLAnchorElement | null;
  if (!a || a.target || a.hasAttribute("download") || a.origin !== location.origin) return;
  e.preventDefault();
  const { surface, scenarioKey } = parsePath(a.pathname);
  mount(surface, scenarioKey);
});

// Initial load: translate a legacy hash link (#/swarm) to its real path, then honor a deep link and normalize the bar without adding a history entry.
{
  if (location.hash) history.replaceState(null, "", pathFromLegacyHash(location.hash) ?? "/");
  const { surface, scenarioKey } = parsePath(location.pathname);
  const canonical = pathForSurface(surface, scenarioKey);
  if (isKnownPath(location.pathname) && location.pathname !== canonical) history.replaceState(null, "", canonical);
  mount(surface, scenarioKey, false);
}
