/**
 * The Electronics Wall, live. The narrative of closure-sim's electronics-wall
 * essay, but every number is the real model running in pimas: drag the assumptions and
 * the simulation recomputes; preview "make its own chips" as a speculation (the
 * exact after-state, nothing committed) before you commit it; and watch the model
 * explain which ceiling is binding. The last panel shows the very same reactive
 * graph projected as an agent surface (subscribe / speculate / explain).
 */
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

type Surface = "wall" | "mission" | "fleet" | "swarm" | "launch" | "power" | "probe";

const fmtNum = (n: number, d = 0) => n.toLocaleString(undefined, { maximumFractionDigits: d });
const fmtUsd = (n: number): string => {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${fmtNum(n)}`;
};
const fmtSci = (n: number, d = 2) => n.toExponential(d);
const FLOPS_UNITS: [string, number][] = [["EFLOPS", 1e18], ["PFLOPS", 1e15], ["TFLOPS", 1e12], ["GFLOPS", 1e9], ["MFLOPS", 1e6], ["kFLOPS", 1e3]];
const fmtFlops = (n: number): string => {
  for (const [u, v] of FLOPS_UNITS) if (n >= v) return `${(n / v).toFixed(2)} ${u}`;
  return `${fmtNum(n)} FLOPS`;
};
const fmtPower = (w: number): string => (w >= 1000 ? `${(w / 1000).toFixed(1)} kW` : `${fmtNum(w)} W`);
const regimeClass = (r: string) => (r === "material-limited" ? "rg-material" : r === "energy-limited" ? "rg-energy" : "rg-resupply");
const regimeWord = (r: string) => r.replace("-limited", "");

function Slider(props: { p: ParamSignal }) {
  const p = props.p;
  return (
    <div class="ctl">
      <div class="ctl-top">
        <span class="ctl-label">{p.label}</span>
        <span class="ctl-val">{() => fmtNum(p.get())} {p.unit}</span>
      </div>
      <input
        type="range"
        min={p.min}
        max={p.max}
        step={p.step}
        value={() => p.get()}
        onInput={(e: Event) => p.set(Number((e.target as HTMLInputElement).value))}
      />
    </div>
  );
}

function StatRow(props: { what: string; sub?: string; value: () => string; cls?: () => string }) {
  return (
    <div class="stat-row">
      <span class="what">{props.what}{props.sub ? <small>{props.sub}</small> : null}</span>
      <span class={() => `val ${props.cls ? props.cls() : ""}`}>{props.value}</span>
    </div>
  );
}

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
      .map(([k, v]) => `  ${k}: ${JSON.stringify(v.value)}`)
      .join("\n");
    const acts = Object.keys(d.actions).map((a) => `  ${a}()`).join("\n");
    return `state {\n${state}\n}\nactions {\n${acts}\n}`;
  });
  const askAgent = () => setSpec(m.bridge.speculate("makeChipsLocal") as Record<string, unknown>);
  return (
    <div class="card agent">
      <p class="panel-head">The same graph, as an agent surface — pimas/agent</p>
      <p class="note" style="margin-bottom:14px">
        No new wiring: the exposed values below are subscribable, the actions are callable, and the agent can <strong>speculate</strong> an action (exact prediction, nothing committed) or read <strong>why</strong> a committed one changed what it did.
      </p>
      <pre class="desc">{descriptor}</pre>
      <div class="btnrow" style="margin-bottom:14px">
        <button class="act" onClick={askAgent}>agent asks: speculate makeChipsLocal()</button>
        <Show when={() => spec() !== null}>{() => <button class="act ghost" onClick={() => setSpec(null)}>clear</button>}</Show>
      </div>
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
          <div style="margin-top:14px">
            <p class="panel-head">last committed action · explain()</p>
            <div class="cause">
              <div><span class="k">action:</span> {() => props.explain()!.action}</div>
              <div><span class="k">wrote fields:</span> <span class="w">{() => props.explain()!.writes.join(", ") || "—"}</span></div>
              <div><span class="k">changed outputs:</span> <span class="c">{() => props.explain()!.changed.join(", ") || "—"}</span></div>
            </div>
          </div>
        )}
      </Show>
    </div>
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
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">Self-replicating factories in space · a live model</p>
          <h1>One factory makes two. Two make four. Then it hits a wall.</h1>
          <p class="lede">
            Land a single robotic factory on the Moon and let it copy itself from local rock — until it stalls on the one part it can't make: chips. This is the real <strong>closure-sim</strong> model, running live. Move the assumptions and watch it recompute. Everything below is computed, not narrated.
          </p>
          <div class="card chartcard">
            <GrowthChart model={m} preview={preview} />
            <p class="chartcap">FIG.1 — factory output vs time, straight from the model. Cyan: as built. Amber (when previewing): if it made its own chips.</p>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>01</b> &nbsp;/&nbsp; The controls — steer the factory</p>
          <div class="lab">
            <div class="card controls">
              <p class="panel-head">Assumptions</p>
              <For each={() => Object.values(m.params)}>
                {(p: ParamSignal) => <Slider p={p} />}
              </For>
              <div class="btnrow" style="margin-top:12px">
                <button class="act ghost" onClick={doReset}>reset {props.scenarioKey === "lunar" ? "lunar seed" : "outpost"}</button>
                <For each={() => Object.keys(SCENARIOS)}>
                  {(k: string) => (
                    <button class={() => `act ${k === props.scenarioKey ? "primary" : ""}`} onClick={() => props.onScenario(k)}>{k}</button>
                  )}
                </For>
              </div>
            </div>

            <div class="card readouts">
              <p class="panel-head">Live results</p>
              <StatRow what="Closure" sub="mass built locally" value={() => `${(m.closureRatio() * 100).toFixed(1)}%`} cls={() => "metal"} />
              <StatRow what="Time to reach goal" sub="output ≥ target" value={() => fmtDays(m.sim().time_to_target_days)} cls={tttCls} />
              <StatRow what="Doubling time" sub="first mass doubling" value={() => fmtDays(m.sim().empirical_doubling_time_days)} />
              <StatRow what="Final output" sub={`after ${fmtNum(m.sim().steps[m.sim().steps.length - 1].day / 365)} yr`} value={() => `${fmtNum(m.sim().final_output_kg_per_day)} kg/day`} />
              <StatRow what="Binding regime" sub="which ceiling caps growth" value={() => regimeWord(m.lateRegime())} cls={() => (m.lateRegime() === "energy-limited" ? "bad" : m.lateRegime() === "resupply-limited" ? "chip" : "metal")} />
              <div style="margin-top:14px">
                <p class="panel-head" style="margin-bottom:8px">Regime over time</p>
                <RegimeTimeline model={m} />
              </div>
              <p class="explain" style="margin-top:18px">{() => m.explainRegime(m.sim())}</p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>02</b> &nbsp;/&nbsp; The wall — should it make its own chips?</p>
          <h2>Preview the change before you commit it.</h2>
          <p>
            Chips are the vitamin the factory can't make — unless you let it. But making them locally costs thousands of kWh per kg. Does closing that gap help or backfire? <strong>Speculate</strong> it: pimas re-runs the whole model against a shadow of the reactive graph and returns the exact result — <em>without touching the live model</em>. Then commit only if you like it.
          </p>
          <div class="btnrow">
            <Show when={() => !m.chipsAreLocal()} fallback={() => <button class="act ghost" onClick={doRestore}>revert to imported chips</button>}>
              {() => <button class="act primary" onClick={doPreview}>speculate: make its own chips</button>}
            </Show>
            <Show when={() => preview() !== null}>
              {() => (
                <>
                  <button class="act commit" onClick={doCommit}>commit this change</button>
                  <button class="act ghost" onClick={() => setPreview(null)}>discard</button>
                </>
              )}
            </Show>
          </div>

          <Show when={() => preview() !== null}>
            {() => (
            <div class="preview">
              <p class="ph">speculation · shadow graph · nothing committed yet</p>
              <div class="diff">
                <div class="d">
                  <span>time to goal</span>
                  <b><span class="val chip">{() => fmtDays(preview()!.before.time_to_target_days)}</span> <span class="arrow">→</span> <span class="val metal">{() => fmtDays(preview()!.after.time_to_target_days)}</span></b>
                </div>
                <div class="d">
                  <span>closure</span>
                  <b><span class="val chip">{() => (preview()!.before.closure_ratio * 100).toFixed(1)}%</span> <span class="arrow">→</span> <span class="val metal">{() => (preview()!.after.closure_ratio * 100).toFixed(1)}%</span></b>
                </div>
                <div class="d">
                  <span>binding regime</span>
                  <b><span class="val chip">{() => regimeWord(preview()!.before.regime_timeline.at(-1)!.regime)}</span> <span class="arrow">→</span> <span class="val metal">{() => regimeWord(preview()!.after.regime_timeline.at(-1)!.regime)}</span></b>
                </div>
              </div>
              <p class="note" style="margin:0">
                {() => {
                  const b = preview()!.before.time_to_target_days;
                  const a = preview()!.after.time_to_target_days;
                  if (a === null) return "Backfire: making chips locally means it never reaches the goal — it runs out of power first. Give it more power and speculate again.";
                  if (b === null) return "Making chips locally is what unlocks the goal at all.";
                  const saved = (b - a) / 365;
                  return saved > 0 ? `Making chips locally reaches the goal ${saved.toFixed(1)} years sooner. Worth committing — if you can build the power plant.` : `Making chips locally is ${(-saved).toFixed(1)} years slower here — the energy cost isn't worth it.`;
                }}
              </p>
            </div>
            )}
          </Show>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>03</b> &nbsp;/&nbsp; Under the hood</p>
          <AgentPanel model={m} explain={explain} />
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            The model is closure-sim (NASA CP-2255, 1980; Freitas &amp; Merkle, 2004) — the same pure functions the Python CLI runs, verified to match.
            The live layer is <strong style="color:var(--text)">pimas</strong>: signals + memos for the model, copy-on-write store + <strong style="color:var(--text)">speculate</strong> for the what-if, and pimas/agent for the surface. Figures are research-grounded order-of-magnitude estimates, not predictions.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── the launch-economics surface ───────────────────────────────────────────
const explainLeverage = (m: LaunchModel): string => {
  const c = m.comparison();
  const pct = m.closurePct().toFixed(0);
  if (c.massLeverage <= 1) {
    return `At ${pct}% closure the seed can't build enough of itself to pay off — you'd launch about as much as you install. Raise closure.`;
  }
  return `At ${pct}% closure, each launched kilogram becomes ${c.massLeverage.toFixed(1)} kg of installed factory — turning a launch-it-all bill into ${fmtUsd(c.costSavingsUsd)} of savings. That leverage is the whole economic case for replicating in place.`;
};

function LaunchSurface(props: { model: LaunchModel }) {
  const m = props.model;
  const c = () => m.comparison();
  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">Launch economics · a live model</p>
          <h1>Don't launch the factory. Launch a seed that builds it.</h1>
          <p class="lede">
            Every kilogram to orbit is expensive. Self-replication trades launched mass for local mass, so the more of itself a factory can build — its <strong>closure</strong> — the less you launch. Drag closure and watch the leverage. Everything below is computed, not narrated.
          </p>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>01</b> &nbsp;/&nbsp; The assumptions</p>
          <div class="lab">
            <div class="card controls">
              <p class="panel-head">Assumptions</p>
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
            </div>
            <div class="card readouts">
              <p class="panel-head">Live results</p>
              <StatRow what="Launch-mass leverage" sub="installed kg per launched kg" value={() => `${c().massLeverage.toFixed(1)}×`} cls={() => "metal"} />
              <StatRow what="Mass launched" sub="seed + vitamins" value={() => `${fmtNum(c().launchedMassKg / 1000)} t`} />
              <StatRow what="Launch it all" sub="direct cost" value={() => fmtUsd(c().directLaunchCostUsd)} cls={() => "bad"} />
              <StatRow what="Launch a seed" sub="seed + vitamins" value={() => fmtUsd(c().replicationLaunchCostUsd)} cls={() => "metal"} />
              <StatRow what="Savings" sub="direct − replication" value={() => fmtUsd(c().costSavingsUsd)} cls={() => "good"} />
              <p class="explain" style="margin-top:18px">{() => explainLeverage(m)}</p>
            </div>
          </div>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            Launch-mass leverage = target ÷ (seed + vitamins), with the vitamin mass set by closure (mass balance: (1−C) imported per kg built) — the <strong style="color:var(--text)">launch-economics</strong> module coupled to <strong style="color:var(--text)">closure-sim</strong>, running live in pimas. $/kg figures are research-grounded (SpaceX published capabilities; standard Δv tables), not predictions.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── the power-budget surface ────────────────────────────────────────────────
const explainPower = (m: PowerBudgetModel): string => {
  const o = m.outputs();
  const be = o.brainEquivalents;
  const beStr = be >= 1 ? `${be.toFixed(1)} human brains` : be >= 0.01 ? `${(be * 100).toFixed(0)}% of one brain` : `${fmtSci(be, 1)} of a brain`;
  const orders = Math.round(Math.log10(o.headroomOverLandauer));
  return `This budget buys about ${beStr} of compute. Each FLOP burns ~${fmtSci(o.energyPerFlopJ, 1)} J — roughly ${orders} orders of magnitude above the single-bit Landauer floor, so the real ceiling here is hardware and waste heat, not thermodynamics.`;
};

function PowerBudgetSurface(props: { model: PowerBudgetModel }) {
  const m = props.model;
  const o = () => m.outputs();
  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">Power budget · a live model</p>
          <h1>How much can a factory think, if it also has to build?</h1>
          <p class="lede">
            An autonomous factory light-minutes from Earth spends some of its power making things and some <em>thinking</em>. Split the budget and watch how much compute it buys — measured against the ~20 W human brain and the hard thermodynamic floor on computation. Everything below is computed, not narrated.
          </p>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>01</b> &nbsp;/&nbsp; The budget</p>
          <div class="lab">
            <div class="card controls">
              <p class="panel-head">Assumptions</p>
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
            </div>
            <div class="card readouts">
              <p class="panel-head">Live results</p>
              <StatRow what="Compute power" sub="share of the budget" value={() => `${fmtNum(o().computeW)} W`} cls={() => "metal"} />
              <StatRow what="Compute throughput" sub="at this efficiency" value={() => fmtFlops(o().computeFlops)} cls={() => "metal"} />
              <StatRow what="Brain-equivalents" sub="≈1e18 FLOPS each · [ESTIMATE]" value={() => (o().brainEquivalents >= 0.01 ? `${o().brainEquivalents.toFixed(2)}×` : `${fmtSci(o().brainEquivalents, 1)}×`)} cls={() => (o().brainEquivalents >= 1 ? "good" : "chip")} />
              <StatRow what="Energy per FLOP" value={() => `${fmtSci(o().energyPerFlopJ, 2)} J`} />
              <StatRow what="Landauer floor" sub="k·T·ln2 at the radiator temp" value={() => `${fmtSci(o().landauerJPerBit, 2)} J/bit`} />
              <StatRow what="Above the floor" sub="a FLOP is many bit-ops" value={() => `${fmtSci(o().headroomOverLandauer, 1)}×`} />
              <p class="explain" style="margin-top:18px">{() => explainPower(m)}</p>
            </div>
          </div>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            Throughput = compute-watts × efficiency; the <strong style="color:var(--text)">Landauer floor</strong> is k·T·ln2 (~2.9e-21 J/bit at 300 K) — the hard thermodynamic minimum. This is the <strong style="color:var(--text)">power-budget</strong> module live in pimas. The brain scale (~20 W, ~1e18 FLOPS) and Landauer limit are sourced; brain-FLOPS is an order-of-magnitude estimate.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── the probe surface ───────────────────────────────────────────────────────
const explainProbe = (m: ProbeModel): string => {
  const o = m.outputs();
  const d = m.distanceAu();
  const be = o.brainEquivalents;
  const beStr = be >= 1 ? `${be.toFixed(1)} brains` : be >= 0.01 ? `${(be * 100).toFixed(0)}% of a brain` : `${fmtSci(be, 1)} of a brain`;
  return `At ${d.toFixed(1)} AU the array delivers ${fmtPower(o.deliveredPowerW)} — and its compute headroom is about ${beStr}. Move outward and both fall as 1/d²: at twice the distance, a quarter the power. That inverse-square wall is what caps a solar probe's reach.`;
};

function ProbeSurface(props: { model: ProbeModel }) {
  const m = props.model;
  const o = () => m.outputs();
  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">The single probe · a live model</p>
          <h1>How far out can a self-powered probe still work — and still think?</h1>
          <p class="lede">
            A self-replicating probe is solar-powered, so how far from the Sun it can operate is set by how much power sunlight delivers there — and sunlight falls as the inverse square of distance. Drag the probe out past Mars, past Jupiter, and watch its power and compute collapse. Everything below is computed, not narrated.
          </p>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>01</b> &nbsp;/&nbsp; The probe and where it is</p>
          <div class="lab">
            <div class="card controls">
              <p class="panel-head">Assumptions</p>
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
            </div>
            <div class="card readouts">
              <p class="panel-head">Live results</p>
              <StatRow what="Sunlight here" sub="irradiance, inverse-square" value={() => `${fmtNum(o().irradianceWM2)} W/m²`} />
              <StatRow what="Delivered power" sub="array × efficiency × sunlight" value={() => fmtPower(o().deliveredPowerW)} cls={() => "metal"} />
              <StatRow what="Compute power" sub="share for thinking" value={() => fmtPower(o().computePowerW)} />
              <StatRow what="Compute throughput" sub="at this efficiency" value={() => fmtFlops(o().computeFlops)} cls={() => "metal"} />
              <StatRow what="Brain-equivalents" sub="≈1e18 FLOPS each · [ESTIMATE]" value={() => (o().brainEquivalents >= 0.01 ? `${o().brainEquivalents.toFixed(2)}×` : `${fmtSci(o().brainEquivalents, 1)}×`)} cls={() => (o().brainEquivalents >= 1 ? "good" : "chip")} />
              <p class="explain" style="margin-top:18px">{() => explainProbe(m)}</p>
            </div>
          </div>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            Irradiance = solar constant ÷ distance² (1360.8 W/m² at 1 AU, Kopp &amp; Lean 2011); delivered power = irradiance × area × efficiency; compute headroom couples in the <strong style="color:var(--text)">power-budget</strong> model. This is <strong style="color:var(--text)">probe-sim</strong> live in pimas, after Borgue &amp; Hein (2020). The probe's full replication range awaits a sourced per-module mass breakdown.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── the mission surface: the whole operation, end to end ─────────────────────
// Quick-jump destinations (heliocentric distance, AU) — mean distances, NASA fact sheet.
const DESTINATIONS: [string, number][] = [["Earth orbit", 1.0], ["Mars", 1.524], ["Asteroid belt", 2.7], ["Jupiter", 5.203], ["Deep", 20]];

const explainMission = (m: MissionModel): string => {
  const r = m.outputs();
  const lev = r.massLeverage;
  if (!r.reachesTarget) {
    if (r.manufacturingW <= 0) {
      return `You've handed all the power to thinking, so the factory never builds a thing — it stalls at the seed. Give manufacturing some power and the operation comes alive.`;
    }
    return `At ${r.distanceAu.toFixed(1)} AU the array delivers only ${fmtPower(r.deliveredPowerW)}, and the ${fmtPower(r.manufacturingW)} left for building isn't enough to ever reach target output — the operation is power-starved. Move closer to the Sun, or grow the array.`;
  }
  return `It works: launch ${fmtNum(r.launchedMassKg / 1000)} t of seed + vitamins, and it grows into a ${fmtNum(r.targetInstalledMassKg / 1000)} t factory — ${lev.toFixed(1)}× leverage, ${fmtUsd(r.costSavingsUsd)} saved versus launching it all, reaching full output in ${fmtDays(r.timeToTargetDays)}. The ${fmtPower(r.manufacturingW)} to manufacturing builds; the ${fmtPower(r.computeW)} to compute thinks.`;
};

function MissionStage(props: { n: string; title: string; value: () => string; cls?: () => string; note: () => string }) {
  return (
    <div class="card" style="margin-bottom:14px">
      <p class="marker" style="margin:0 0 10px"><b>{props.n}</b> &nbsp;/&nbsp; {props.title}</p>
      <div class="stat-row" style="border:0;padding-top:0">
        <span class="what" />
        <span class={() => `val ${props.cls ? props.cls() : ""}`} style="font-size:1.5rem">{props.value}</span>
      </div>
      <p class="explain" style="margin:6px 0 0">{props.note}</p>
    </div>
  );
}

function MissionSurface(props: { model: MissionModel }) {
  const m = props.model;
  const r = () => m.outputs();
  const okCls = () => (r().reachesTarget ? "good" : "bad");
  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">The whole operation · end to end · a live model</p>
          <h1>Launch a seed. Fly it to the Sun's light. Watch it build a factory.</h1>
          <p class="lede">
            This is every piece at once: the <strong>launch</strong> bill, the factory's <strong>closure</strong>, the <strong>solar power</strong> that reaches it, the <strong>split</strong> between building and thinking, and whether it ever <strong>replicates</strong> into a full installation. One deterministic run over all four models. Drag the knobs — or pick a destination — and the whole chain recomputes.
          </p>
          <div class="card" style="margin-top:8px">
            <p class="panel-head" style="margin-bottom:8px">Does the operation succeed?</p>
            <p class="explain" style="margin:0;font-size:1.05rem">{() => explainMission(m)}</p>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>◆</b> &nbsp;/&nbsp; The knobs</p>
          <div class="lab">
            <div class="card controls">
              <p class="panel-head">Mission parameters</p>
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
              <div class="btnrow" style="margin-top:12px">
                <span class="note" style="align-self:center;margin-right:4px">jump to:</span>
                <For each={() => DESTINATIONS}>
                  {(d: [string, number]) => (
                    <button
                      class={() => `act ${Math.abs(m.params[0].get() - d[1]) < 0.05 ? "primary" : "ghost"}`}
                      onClick={() => m.params[0].set(d[1])}
                    >{d[0]}</button>
                  )}
                </For>
              </div>
            </div>
            <div class="card readouts">
              <p class="panel-head">Headline</p>
              <StatRow what="Reaches full output?" sub="does it ever hit target" value={() => (r().reachesTarget ? "yes" : "no")} cls={okCls} />
              <StatRow what="Launch-mass leverage" sub="installed kg per launched kg" value={() => `${r().massLeverage.toFixed(1)}×`} cls={() => "metal"} />
              <StatRow what="Savings vs launch-it-all" value={() => fmtUsd(r().costSavingsUsd)} cls={() => "good"} />
              <StatRow what="Time to full output" value={() => fmtDays(r().timeToTargetDays)} cls={okCls} />
              <StatRow what="Delivered power here" sub="inverse-square" value={() => fmtPower(r().deliveredPowerW)} cls={() => "metal"} />
              <StatRow what="Compute afforded" sub="brain-equivalents · [ESTIMATE]" value={() => (r().brainEquivalents >= 0.01 ? `${r().brainEquivalents.toFixed(2)}×` : `${fmtSci(r().brainEquivalents, 1)}×`)} cls={() => "chip"} />
            </div>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>▶</b> &nbsp;/&nbsp; The chain, stage by stage</p>
          <MissionStage n="00" title="Launch — put the seed in space"
            value={() => `${fmtNum(r().launchedMassKg / 1000)} t launched`}
            cls={() => "metal"}
            note={() => `You launch the ${fmtNum(r().seedMassKg / 1000)} t seed plus ${fmtNum(r().vitaminMassKg / 1000)} t of "vitamins" (parts it can't make). Reaching orbit is ${(r().propellantFraction * 100).toFixed(0)}% propellant by mass (Δv ${fmtNum(r().deltaVMs)} m/s, Isp ${fmtNum(r().specificImpulseS)} s) — that exponential penalty is why launching the finished factory is unthinkable.`} />
          <MissionStage n="01" title="Closure — how much it makes for itself"
            value={() => `${(r().closureRatio * 100).toFixed(1)}% closed`}
            cls={() => "metal"}
            note={() => `The seed factory can build ${(r().closureRatio * 100).toFixed(1)}% of its own mass from local material; the remaining ${((1 - r().closureRatio) * 100).toFixed(1)}% must be imported as vitamins. That single fraction sets both the launch bill above and the payoff below.`} />
          <MissionStage n="02" title="Arrive — solar power at distance"
            value={() => fmtPower(r().deliveredPowerW)}
            cls={() => "metal"}
            note={() => `At ${r().distanceAu.toFixed(1)} AU sunlight is ${fmtNum(r().irradianceWM2)} W/m²; the ${fmtNum(m.params[2].get())} m² array converts it to ${fmtPower(r().deliveredPowerW)}. Double the distance and this quarters — the inverse-square law is the whole constraint on where a solar probe can work.`} />
          <MissionStage n="03" title="Split — build vs. think"
            value={() => `${fmtPower(r().manufacturingW)} build · ${fmtPower(r().computeW)} think`}
            note={() => `That power is divided: manufacturing gets ${fmtPower(r().manufacturingW)}, computation ${fmtPower(r().computeW)}, housekeeping the rest. This is the one dial the modules didn't share — here it's decided once and routed to the two stages below.`} />
          <MissionStage n="04" title="Replicate — does it grow?"
            value={() => (r().reachesTarget ? `reaches target in ${fmtDays(r().timeToTargetDays)}` : "never reaches target")}
            cls={okCls}
            note={() => (r().reachesTarget
              ? `Fed ${fmtPower(r().manufacturingW)}, the factory doubles about every ${fmtDays(r().doublingTimeDays)} and climbs to target output, ending ${regimeWord(r().bindingRegime ?? "")}-limited.`
              : `With only ${fmtPower(r().manufacturingW)} for manufacturing, growth never reaches the target output rate — the operation is power-starved at this distance and split.`)} />
          <MissionStage n="05" title="Payoff — what you saved"
            value={() => `${r().massLeverage.toFixed(1)}× · ${fmtUsd(r().costSavingsUsd)}`}
            cls={() => "good"}
            note={() => `Launching a ${fmtNum(r().launchedMassKg / 1000)} t seed instead of a ${fmtNum(r().targetInstalledMassKg / 1000)} t factory is ${r().massLeverage.toFixed(1)}× leverage — ${fmtUsd(r().replicationLaunchCostUsd)} instead of ${fmtUsd(r().directLaunchCostUsd)}, a saving of ${fmtUsd(r().costSavingsUsd)}. That gap is the entire reason to send a self-replicating seed.`} />
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            One pure fold over all four modules — <strong style="color:var(--text)">launch-economics</strong>, <strong style="color:var(--text)">closure-sim</strong>, <strong style="color:var(--text)">probe-sim</strong>, and <strong style="color:var(--text)">power-budget</strong> — composed in the <strong style="color:var(--text)">mission</strong> module and run live in pimas. Every number traces to a source (see each module's REFERENCES.md); the launch scalars are representative sourced values.
            <br /><br />
            <em>Honest caveat:</em> there is no sourced per-module mass breakdown for the Borgue &amp; Hein probe yet (an open gap), so the factory here is closure-sim's lunar-regolith seed scenario used as a stand-in — a real bill of materials, but not probe-specific. No masses are invented to fill that gap.
          </p>
        </div>
      </footer>
    </div>
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
      els.push(<line x1={PADL} y1={y} x2={W - PADR} y2={y} stroke="rgba(232,226,214,0.08)" stroke-width="1" />);
      els.push(<text x={PADL - 8} y={y + 4} text-anchor="end" fill="var(--chip)" style="font:11px var(--mono)">{fmtNum(g.maxPop * f)}</text>);
      els.push(<text x={W - PADR + 8} y={y + 4} fill="var(--metal)" style="font:11px var(--mono)">{fmtNum(g.maxDist * f, 1)}</text>);
    }
    els.push(<text x={PADL} y={PADT - 6} fill="var(--chip)" style="font:11px var(--mono)">PROBES</text>);
    els.push(<text x={W - PADR + 8} y={PADT - 6} text-anchor="end" fill="var(--metal)" style="font:11px var(--mono)">FRONTIER AU</text>);
    els.push(<text x={(PADL + W - PADR) / 2} y={H - 6} text-anchor="middle" fill="var(--muted)" style="font:11px var(--mono)">YEARS →</text>);
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
    els.push(<line x1={PADL} y1={MID} x2={W - PADR} y2={MID} stroke="rgba(232,226,214,0.14)" stroke-width="1" />);
    els.push(<circle cx={PADL} cy={MID} r="7" fill="var(--metal)" />);
    els.push(<text x={PADL} y={MID - 12} text-anchor="middle" fill="var(--muted)" style="font:11px var(--mono)">Sun</text>);
    for (const t of g.ticks) {
      els.push(<line x1={t.x} y1={MID - 4} x2={t.x} y2={MID + 4} stroke="var(--muted)" stroke-width="1" />);
      els.push(<text x={t.x} y={H - 6} text-anchor="middle" fill="var(--muted)" style="font:11px var(--mono)">{t.label}</text>);
    }
    els.push(<text x={W - PADR} y={16} text-anchor="end" fill="var(--muted)" style="font:11px var(--mono)">HELIOCENTRIC DISTANCE (AU) →</text>);
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
  if (r.binding.vitaminLimited) walls.push("it runs out of imported vitamins — the electronics wall, now at fleet scale");
  if (r.binding.powerLimited) walls.push("its probes drift too far from the Sun to keep building — a spatial power wall");
  if (r.binding.capLimited) walls.push("it reaches the fleet cap you set");
  const why = walls.length ? walls.join("; and ") : "the mission window simply ends";
  const dbl = r.doublingTimeDays === null ? "never doubles in the window" : `first doubles in ${fmtDays(r.doublingTimeDays)}`;
  return `The fleet grows to ${r.finalPopulation} probes (${dbl}), spreading out to ${r.maxDistanceAu.toFixed(1)} AU and consuming ${fmtNum(r.vitaminsConsumedKg / 1000)} t of vitamins. It stops growing because ${why}. Same seed, same run — every time.`;
};

function MultiProbeSurface(props: { model: MultiProbeModel }) {
  const m = props.model;
  const r = () => m.result();
  const s = () => m.snap();
  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">A small, deterministic fleet · a live model</p>
          <h1>One probe becomes a fleet — until it hits the same two walls.</h1>
          <p class="lede">
            Give one self-replicating probe local sunlight and imported parts, and it copies itself; the copies disperse outward and copy again. This is that fleet as a <strong>pure, seeded</strong> simulation — a handful of probes, not a swarm. Drag the knobs, then <strong>scrub through the mission</strong> and watch the fleet grow and spread. It's fully deterministic: same seed, same fleet, every run.
          </p>
          <div class="card chartcard">
            <FleetChart model={m} />
            <p class="chartcap">FIG.1 — fleet size (cyan) and how far the farthest probe has spread (amber) over 40 years. The dashed line is the day you're scrubbed to.</p>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>01</b> &nbsp;/&nbsp; The knobs, and the day</p>
          <div class="lab">
            <div class="card controls">
              <p class="panel-head">Fleet parameters</p>
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
              <div style="margin-top:14px;padding-top:8px;border-top:1px solid rgba(232,226,214,0.1)">
                <Slider p={m.scrub} />
              </div>
            </div>
            <div class="card readouts">
              <p class="panel-head">At this day</p>
              <StatRow what="Mission day" sub={() => `year ${(s().day / 365).toFixed(1)}`} value={() => `${fmtNum(s().day)} d`} />
              <StatRow what="Probes alive" sub="traveling + active" value={() => fmtNum(s().population)} cls={() => "chip"} />
              <StatRow what="Active (building)" value={() => fmtNum(s().active)} cls={() => "good"} />
              <StatRow what="Dispersal frontier" sub="farthest probe" value={() => `${s().maxDistanceAu.toFixed(1)} AU`} cls={() => "metal"} />
              <StatRow what="Mean distance" value={() => `${s().meanDistanceAu.toFixed(1)} AU`} />
              <StatRow what="Vitamins left" sub="the electronics budget" value={() => `${fmtNum(s().vitaminPoolKg / 1000)} t`} />
              <p class="explain" style="margin-top:18px">{() => explainFleet(m)}</p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>02</b> &nbsp;/&nbsp; Where the fleet ends up</p>
          <div class="card chartcard">
            <FleetScatter model={m} />
            <p class="chartcap">FIG.2 — the final fleet, each probe placed by its distance from the Sun. Green: still building. Grey: in transit. Push the start distance out and watch replication choke on the inverse-square power wall.</p>
          </div>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            A pure, seeded fold (mulberry32 RNG threaded through state — byte-identical to the Python) over the <strong style="color:var(--text)">multi-probe</strong> module, live in pimas. Each probe builds at <strong style="color:var(--text)">closure-sim</strong>'s min(machinery, energy-cap) rate using <strong style="color:var(--text)">probe-sim</strong>'s 1/d² power; a finite vitamin pool and 1/d² dispersal are the two ceilings. Physics and figures trace to the sibling modules' REFERENCES.md; the factory is the lunar-regolith seed scenario used as a stand-in (the probe-BOM gap persists).
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── the swarm surface: a settlement front filling the galaxy, live on a canvas ─
const CANVAS_W = 900, CANVAS_H = 520, CANVAS_PAD = 26;

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

  ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
  ctx.fillStyle = "#0b0d10";
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

  // unsettled stars: dim; settled (by this year): bright cyan, brighter when recent.
  for (let i = 0; i < r.xs.length; i++) {
    const sy = r.settledYear[i];
    const settled = sy >= 0 && sy <= year;
    if (settled) {
      const age = year > 0 ? (year - sy) / year : 1;
      ctx.fillStyle = age < 0.06 ? "#e8e2d6" : "#58c7d6"; // freshly-settled flashes white
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      ctx.arc(px(r.xs[i]), py(r.ys[i]), 2.4, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.fillStyle = "#3a4048";
      ctx.globalAlpha = 0.55;
      ctx.beginPath();
      ctx.arc(px(r.xs[i]), py(r.ys[i]), 1.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;

  // the wavefront: a faint ring at the current front radius, centred on the homeworld.
  const front = m.settledAt().frontPc;
  ctx.strokeStyle = "rgba(232,163,61,0.35)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(px(r.xs[r.origin]), py(r.ys[r.origin]), front * s, 0, Math.PI * 2);
  ctx.stroke();

  // the homeworld.
  ctx.fillStyle = "#e8a33d";
  ctx.beginPath();
  ctx.arc(px(r.xs[r.origin]), py(r.ys[r.origin]), 4.5, 0, Math.PI * 2);
  ctx.fill();
}

const explainSwarm = (m: SwarmModel): string => {
  const r = m.result();
  if (r.t100Years === null) {
    return `With ${m.params[1].get()} offspring per settlement the front can't fill the field — raise it above zero and the reachable galaxy fills exponentially.`;
  }
  const frontSpeedFrac = (r.frontRadiusPc / r.t100Years) / (0.3066 * m.params[2].get()) * 100;
  return `From one homeworld, the front settles all ${r.nStars} stars in ${fmtNum(r.t100Years)} years (50% by ${fmtNum(r.t50Years ?? 0)}, 90% by ${fmtNum(r.t90Years ?? 0)}), reaching ${r.frontRadiusPc.toFixed(1)} pc. The wavefront advances at only ~${frontSpeedFrac.toFixed(0)}% of a single probe's speed — nearest-hop zig-zag and settling slow the wave, just as Nicholson & Forgan found. Same seed, same galaxy, every run.`;
};

function SwarmSurface(props: { model: SwarmModel }) {
  const m = props.model;
  const [canvas, setCanvas] = createSignal<HTMLCanvasElement | null>(null);

  // Draw whenever the field (knobs/seed) or the scrubbed year changes — a single effect
  // reading the fold's buffers (§7), never a DOM node per star.
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

  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">The swarm · a settlement front · a live model</p>
          <h1>One probe. Then the galaxy fills in.</h1>
          <p class="lede">
            Give a self-replicating probe a galaxy of stars and it spreads — settle a star, build copies, send them to the next nearest stars, repeat. This is that front as a <strong>pure, seeded</strong> simulation (slice 1 of the swarm). Press play and watch the reachable field light up from one homeworld; drag the knobs and reseed the galaxy. Deterministic: same seed, same spread, every run.
          </p>
          <div class="card chartcard">
            <canvas
              ref={setCanvas}
              width={CANVAS_W}
              height={CANVAS_H}
              style="width:100%;height:auto;display:block;border-radius:8px;background:#0b0d10"
            />
            <p class="chartcap">FIG.1 — the star field. Amber: the homeworld. Cyan: settled by the scrubbed year (white = just settled). Grey: not yet reached. The amber ring is the settlement wavefront.</p>
          </div>
          <div class="btnrow" style="align-items:center;gap:12px">
            <button class="act primary" onClick={togglePlay}>{() => (m.playing() ? "⏸ pause" : "▶ play")}</button>
            <input
              type="range"
              min={0}
              max={() => m.maxYear()}
              step={() => Math.max(1, m.maxYear() / 400)}
              value={() => m.scrubYear()}
              onInput={(e: Event) => { m.setPlaying(false); m.setScrubYear(Number((e.target as HTMLInputElement).value)); }}
              style="flex:1"
            />
            <span class="ctl-val" style="min-width:110px;text-align:right">{() => fmtNum(m.scrubYear())} yr</span>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>01</b> &nbsp;/&nbsp; The galaxy and the probes</p>
          <div class="lab">
            <div class="card controls">
              <p class="panel-head">Parameters</p>
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
            </div>
            <div class="card readouts">
              <p class="panel-head">At this year</p>
              <StatRow what="Year" value={() => `${fmtNum(m.scrubYear())} yr`} />
              <StatRow what="Stars settled" sub={() => `of ${fmtNum(m.result().nStars)}`} value={() => `${fmtNum(m.settledAt().count)} (${pct().toFixed(0)}%)`} cls={() => "chip"} />
              <StatRow what="Wavefront radius" value={() => `${m.settledAt().frontPc.toFixed(1)} pc`} cls={() => "metal"} />
              <StatRow what="Fill 50% / 90%" sub="exploration timescale" value={() => `${fmtNum(m.result().t50Years ?? 0)} / ${fmtNum(m.result().t90Years ?? 0)} yr`} />
              <StatRow what="Fill 100%" value={() => (m.result().t100Years === null ? "never" : `${fmtNum(m.result().t100Years!)} yr`)} cls={() => (m.result().t100Years === null ? "bad" : "good")} />
              <StatRow what="Probes launched" value={() => fmtNum(m.result().totalProbesLaunched)} />
              <p class="explain" style="margin-top:18px">{() => explainSwarm(m)}</p>
            </div>
          </div>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            A pure, seeded, fixed-step fold (mulberry32 threaded through state, byte-identical to the Python) over the <strong style="color:var(--text)">swarm</strong> module, live in pimas — the canvas reads the fold's settlement buffers each frame; there is no DOM node per star (the rendering discipline that scales, CLAUDE.md §7). Slice 1: straight-line travel, nearest-unsettled policy. Gravitational slingshots, 200k-star scale, and the light-speed-limited-coordination extension are later slices. Speed 0.1c and stellar density trace to Nicholson &amp; Forgan (2013) and the solar-neighborhood census; see swarm/REFERENCES.md.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── shell nav: one surface per model ────────────────────────────────────────
function Nav(props: { surface: Surface }) {
  return (
    <div class="wrap" style="padding-top:18px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <span style="font-weight:700;letter-spacing:.3px;margin-right:8px">von-neumann</span>
      <button class={`act ${props.surface === "mission" ? "primary" : "ghost"}`} onClick={() => mount("mission")}>Full mission</button>
      <button class={`act ${props.surface === "fleet" ? "primary" : "ghost"}`} onClick={() => mount("fleet")}>Fleet</button>
      <button class={`act ${props.surface === "swarm" ? "primary" : "ghost"}`} onClick={() => mount("swarm")}>Swarm</button>
      <button class={`act ${props.surface === "wall" ? "primary" : "ghost"}`} onClick={() => mount("wall")}>Electronics wall</button>
      <button class={`act ${props.surface === "probe" ? "primary" : "ghost"}`} onClick={() => mount("probe")}>Single probe</button>
      <button class={`act ${props.surface === "launch" ? "primary" : "ghost"}`} onClick={() => mount("launch")}>Launch economics</button>
      <button class={`act ${props.surface === "power" ? "primary" : "ghost"}`} onClick={() => mount("power")}>Power budget</button>
    </div>
  );
}

// ── mount: a shell hosting one surface per model, swapped by re-render ───────
const appEl = document.getElementById("app")!;
let disposeRender: (() => void) | null = null;
let model: WallModel | null = null;

function mount(surface: Surface, scenarioKey = "lunar") {
  disposeRender?.();
  model?.dispose();
  model = null;
  if (surface === "wall") {
    model = createWallModel(SCENARIOS[scenarioKey]);
    const active = model;
    disposeRender = render(
      () => (
        <div>
          <Nav surface="wall" />
          <App model={active} scenarioKey={scenarioKey} onScenario={(k: string) => mount("wall", k)} />
        </div>
      ),
      appEl,
    );
  } else if (surface === "launch") {
    const lm = createLaunchEconomicsModel();
    disposeRender = render(
      () => (
        <div>
          <Nav surface="launch" />
          <LaunchSurface model={lm} />
        </div>
      ),
      appEl,
    );
  } else if (surface === "power") {
    const pm = createPowerBudgetModel();
    disposeRender = render(
      () => (
        <div>
          <Nav surface="power" />
          <PowerBudgetSurface model={pm} />
        </div>
      ),
      appEl,
    );
  } else if (surface === "mission") {
    const mm = createMissionModel();
    disposeRender = render(
      () => (
        <div>
          <Nav surface="mission" />
          <MissionSurface model={mm} />
        </div>
      ),
      appEl,
    );
  } else if (surface === "fleet") {
    const fm = createMultiProbeModel();
    disposeRender = render(
      () => (
        <div>
          <Nav surface="fleet" />
          <MultiProbeSurface model={fm} />
        </div>
      ),
      appEl,
    );
  } else if (surface === "swarm") {
    const sm = createSwarmModel();
    disposeRender = render(
      () => (
        <div>
          <Nav surface="swarm" />
          <SwarmSurface model={sm} />
        </div>
      ),
      appEl,
    );
  } else {
    const prm = createProbeModel();
    disposeRender = render(
      () => (
        <div>
          <Nav surface="probe" />
          <ProbeSurface model={prm} />
        </div>
      ),
      appEl,
    );
  }
}

mount("wall");
