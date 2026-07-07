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
import { createSpineModel } from "./spine-model.js";
import type { SpineModel } from "./spine-model.js";
import { RUNGS } from "./coordination.js";
import { SOURCES, sourceById, sourceNumber, sourceCategories, STRENGTH_LABEL } from "./sources.js";
import type { Source } from "./sources.js";

type Surface = "overview" | "wall" | "mission" | "fleet" | "swarm" | "spine" | "launch" | "power" | "probe" | "sources";

/**
 * An inline citation marker: a superscript [n] (the source's stable bibliography number)
 * that reveals the full reference, its link, and what it grounds on hover or keyboard
 * focus. Pure and static - the tooltip is CSS-driven, so this creates no reactive nodes
 * (7). Pass one id or several; unknown ids are dropped rather than shown wrong.
 */
function Cite(props: { ids: string | string[] }) {
  const ids = Array.isArray(props.ids) ? props.ids : [props.ids];
  const srcs = ids.map(sourceById).filter((s): s is Source => Boolean(s));
  if (srcs.length === 0) return null;
  const nums = srcs.map((s) => sourceNumber(s.id)).join(", ");
  const aria = `Sources: ${srcs.map((s) => `${s.short}`).join("; ")}`;
  return (
    <span class="cite" tabindex="0" role="note" aria-label={aria}>
      <sup>[{nums}]</sup>
      <span class="cite-pop" role="tooltip">
        <For each={() => srcs}>
          {(s: Source) => (
            <span class="cite-item">
              <span class="cite-ref">
                <b>[{sourceNumber(s.id)}] {s.authors}</b> ({s.year}). {s.title}. <i>{s.venue}</i>.
              </span>
              {s.url
                ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a>
                : <span class="cite-nolink">cited by reference (no public link)</span>}
              <span class="cite-use">Grounds: {s.grounds}</span>
            </span>
          )}
        </For>
      </span>
    </span>
  );
}

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
  // For commit-on-release knobs, a local signal tracks the thumb + readout live during a
  // drag while the model value (which may trigger an expensive recompute) is committed only
  // on release. A cheap knob (no flag) sets the model directly on every input, as before.
  const [disp, setDisp] = createSignal(p.get());
  if (p.commitOnRelease) createEffect(() => setDisp(p.get())); // pull in external changes
  const shown = () => (p.commitOnRelease ? disp() : p.get());
  return (
    <div class="ctl">
      <div class="ctl-top">
        <span class="ctl-label">{p.label}</span>
        <span class="ctl-val">{() => fmtNum(shown())} {p.unit}</span>
      </div>
      <input
        type="range"
        aria-label={p.unit ? `${p.label} (${p.unit})` : p.label}
        min={p.min}
        max={p.max}
        step={p.step}
        value={() => shown()}
        onInput={(e: Event) => {
          const v = Number((e.target as HTMLInputElement).value);
          if (p.commitOnRelease) setDisp(v); else p.set(v);
        }}
        onChange={(e: Event) => {
          if (p.commitOnRelease) p.set(Number((e.target as HTMLInputElement).value));
        }}
      />
    </div>
  );
}

function StatRow(props: { what: string; sub?: string; value: () => string; cls?: () => string; cite?: string | string[] }) {
  return (
    <div class="stat-row">
      <span class="what">{props.what}{props.cite ? <Cite ids={props.cite} /> : null}{props.sub ? <small>{props.sub}</small> : null}</span>
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
      <p class="panel-head">The same graph, as an agent surface - pimas/agent</p>
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
              <div><span class="k">wrote fields:</span> <span class="w">{() => props.explain()!.writes.join(", ") || "-"}</span></div>
              <div><span class="k">changed outputs:</span> <span class="c">{() => props.explain()!.changed.join(", ") || "-"}</span></div>
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
            Land a single robotic factory on the Moon and let it copy itself from local rock - until it stalls on the one part it can't make: chips. This is the real <strong>closure-sim</strong> model, running live. Move the assumptions and watch it recompute. Everything below is computed, not narrated.
          </p>
          <div class="card chartcard">
            <GrowthChart model={m} preview={preview} />
            <p class="chartcap">FIG.1 - factory output vs time, straight from the model. Cyan: as built. Amber (when previewing): if it made its own chips.</p>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>01</b> &nbsp;/&nbsp; The controls - steer the factory</p>
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
          <p class="marker"><b>02</b> &nbsp;/&nbsp; The wall - should it make its own chips?</p>
          <h2>Preview the change before you commit it.</h2>
          <p>
            Chips are the vitamin the factory can't make - unless you let it. But making them locally costs thousands of kWh per kg. Does closing that gap help or backfire? <strong>Speculate</strong> it: pimas re-runs the whole model against a shadow of the reactive graph and returns the exact result - <em>without touching the live model</em>. Then commit only if you like it.
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
                  if (a === null) return "Backfire: making chips locally means it never reaches the goal - it runs out of power first. Give it more power and speculate again.";
                  if (b === null) return "Making chips locally is what unlocks the goal at all.";
                  const saved = (b - a) / 365;
                  return saved > 0 ? `Making chips locally reaches the goal ${saved.toFixed(1)} years sooner. Worth committing - if you can build the power plant.` : `Making chips locally is ${(-saved).toFixed(1)} years slower here - the energy cost isn't worth it.`;
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
            The model is closure-sim (NASA CP-2255, 1980; Freitas &amp; Merkle, 2004)<Cite ids={["nasa-cp-2255-1980", "freitas-merkle-2004"]} /> - the same pure functions the Python CLI runs, verified to match.
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
    return `At ${pct}% closure the seed can't build enough of itself to pay off - you'd launch about as much as you install. Raise closure.`;
  }
  return `At ${pct}% closure, each launched kilogram becomes ${c.massLeverage.toFixed(1)} kg of installed factory - turning a launch-it-all bill into ${fmtUsd(c.costSavingsUsd)} of savings. That leverage is the whole economic case for replicating in place.`;
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
            Every kilogram to orbit is expensive. Self-replication trades launched mass for local mass, so the more of itself a factory can build - its <strong>closure</strong> - the less you launch. Drag closure and watch the leverage. Everything below is computed, not narrated.
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
            Launch-mass leverage = target ÷ (seed + vitamins), with the vitamin mass set by closure (mass balance: (1−C) imported per kg built) - the <strong style="color:var(--text)">launch-economics</strong> module coupled to <strong style="color:var(--text)">closure-sim</strong>, running live in pimas. $/kg figures are research-grounded (SpaceX published capabilities<Cite ids="spacex-capabilities" />; standard Δv tables<Cite ids="tsiolkovsky-1903" />), not predictions.
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
  return `This budget buys about ${beStr} of compute. Each FLOP burns ~${fmtSci(o.energyPerFlopJ, 1)} J - roughly ${orders} orders of magnitude above the single-bit Landauer floor, so the real ceiling here is hardware and waste heat, not thermodynamics.`;
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
            An autonomous factory light-minutes from Earth spends some of its power making things and some <em>thinking</em>. Split the budget and watch how much compute it buys - measured against the ~20 W human brain and the hard thermodynamic floor on computation. Everything below is computed, not narrated.
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
              <StatRow what="Landauer floor" cite="landauer-1961" sub="k·T·ln2 at the radiator temp" value={() => `${fmtSci(o().landauerJPerBit, 2)} J/bit`} />
              <StatRow what="Above the floor" sub="a FLOP is many bit-ops" value={() => `${fmtSci(o().headroomOverLandauer, 1)}×`} />
              <p class="explain" style="margin-top:18px">{() => explainPower(m)}</p>
            </div>
          </div>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            Throughput = compute-watts × efficiency; the <strong style="color:var(--text)">Landauer floor</strong> is k·T·ln2 (~2.9e-21 J/bit at 300 K) - the hard thermodynamic minimum. This is the <strong style="color:var(--text)">power-budget</strong> module live in pimas. The brain scale (~20 W<Cite ids="raichle-gusnard-2002" />, ~1e18 FLOPS<Cite ids="sandberg-bostrom-2008" />) and Landauer limit<Cite ids="landauer-1961" /> are sourced; brain-FLOPS is an order-of-magnitude estimate.
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
  return `At ${d.toFixed(1)} AU the array delivers ${fmtPower(o.deliveredPowerW)} - and its compute headroom is about ${beStr}. Move outward and both fall as 1/d²: at twice the distance, a quarter the power. That inverse-square wall is what caps a solar probe's reach.`;
};

function ProbeSurface(props: { model: ProbeModel }) {
  const m = props.model;
  const o = () => m.outputs();
  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">The single probe · a live model</p>
          <h1>How far out can a self-powered probe still work - and still think?</h1>
          <p class="lede">
            A self-replicating probe is solar-powered, so how far from the Sun it can operate is set by how much power sunlight delivers there - and sunlight falls as the inverse square of distance. Drag the probe out past Mars, past Jupiter, and watch its power and compute collapse. Everything below is computed, not narrated.
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
              <StatRow what="Sunlight here" cite="kopp-lean-2011" sub="irradiance, inverse-square" value={() => `${fmtNum(o().irradianceWM2)} W/m²`} />
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
            Irradiance = solar constant ÷ distance² (1360.8 W/m² at 1 AU, Kopp &amp; Lean 2011<Cite ids="kopp-lean-2011" />); delivered power = irradiance × area × efficiency; compute headroom couples in the <strong style="color:var(--text)">power-budget</strong> model. This is <strong style="color:var(--text)">probe-sim</strong> live in pimas, after Borgue &amp; Hein (2020)<Cite ids="borgue-hein-2020" />. The probe's full replication range awaits a sourced per-module mass breakdown.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── the mission surface: the whole operation, end to end ─────────────────────
// Quick-jump destinations (heliocentric distance, AU) - mean distances, NASA fact sheet.
const DESTINATIONS: [string, number][] = [["Earth orbit", 1.0], ["Mars", 1.524], ["Asteroid belt", 2.7], ["Jupiter", 5.203], ["Deep", 20]];

const explainMission = (m: MissionModel): string => {
  const r = m.outputs();
  const lev = r.massLeverage;
  if (!r.reachesTarget) {
    if (r.manufacturingW <= 0) {
      return `You've handed all the power to thinking, so the factory never builds a thing - it stalls at the seed. Give manufacturing some power and the operation comes alive.`;
    }
    return `At ${r.distanceAu.toFixed(1)} AU the array delivers only ${fmtPower(r.deliveredPowerW)}, and the ${fmtPower(r.manufacturingW)} left for building isn't enough to ever reach target output - the operation is power-starved. Move closer to the Sun, or grow the array.`;
  }
  return `It works: launch ${fmtNum(r.launchedMassKg / 1000)} t of seed + vitamins, and it grows into a ${fmtNum(r.targetInstalledMassKg / 1000)} t factory - ${lev.toFixed(1)}× leverage, ${fmtUsd(r.costSavingsUsd)} saved versus launching it all, reaching full output in ${fmtDays(r.timeToTargetDays)}. The ${fmtPower(r.manufacturingW)} to manufacturing builds; the ${fmtPower(r.computeW)} to compute thinks.`;
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
            This is every piece at once: the <strong>launch</strong> bill, the factory's <strong>closure</strong>, the <strong>solar power</strong> that reaches it, the <strong>split</strong> between building and thinking, and whether it ever <strong>replicates</strong> into a full installation. One deterministic run over all four models. Drag the knobs - or pick a destination - and the whole chain recomputes.
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
          <MissionStage n="00" title="Launch - put the seed in space"
            value={() => `${fmtNum(r().launchedMassKg / 1000)} t launched`}
            cls={() => "metal"}
            note={() => `You launch the ${fmtNum(r().seedMassKg / 1000)} t seed plus ${fmtNum(r().vitaminMassKg / 1000)} t of "vitamins" (parts it can't make). Reaching orbit is ${(r().propellantFraction * 100).toFixed(0)}% propellant by mass (Δv ${fmtNum(r().deltaVMs)} m/s, Isp ${fmtNum(r().specificImpulseS)} s) - that exponential penalty is why launching the finished factory is unthinkable.`} />
          <MissionStage n="01" title="Closure - how much it makes for itself"
            value={() => `${(r().closureRatio * 100).toFixed(1)}% closed`}
            cls={() => "metal"}
            note={() => `The seed factory can build ${(r().closureRatio * 100).toFixed(1)}% of its own mass from local material; the remaining ${((1 - r().closureRatio) * 100).toFixed(1)}% must be imported as vitamins. That single fraction sets both the launch bill above and the payoff below.`} />
          <MissionStage n="02" title="Arrive - solar power at distance"
            value={() => fmtPower(r().deliveredPowerW)}
            cls={() => "metal"}
            note={() => `At ${r().distanceAu.toFixed(1)} AU sunlight is ${fmtNum(r().irradianceWM2)} W/m²; the ${fmtNum(m.params[2].get())} m² array converts it to ${fmtPower(r().deliveredPowerW)}. Double the distance and this quarters - the inverse-square law is the whole constraint on where a solar probe can work.`} />
          <MissionStage n="03" title="Split - build vs. think"
            value={() => `${fmtPower(r().manufacturingW)} build · ${fmtPower(r().computeW)} think`}
            note={() => `That power is divided: manufacturing gets ${fmtPower(r().manufacturingW)}, computation ${fmtPower(r().computeW)}, housekeeping the rest. This is the one dial the modules didn't share - here it's decided once and routed to the two stages below.`} />
          <MissionStage n="04" title="Replicate - does it grow?"
            value={() => (r().reachesTarget ? `reaches target in ${fmtDays(r().timeToTargetDays)}` : "never reaches target")}
            cls={okCls}
            note={() => (r().reachesTarget
              ? `Fed ${fmtPower(r().manufacturingW)}, the factory doubles about every ${fmtDays(r().doublingTimeDays)} and climbs to target output, ending ${regimeWord(r().bindingRegime ?? "")}-limited.`
              : `With only ${fmtPower(r().manufacturingW)} for manufacturing, growth never reaches the target output rate - the operation is power-starved at this distance and split.`)} />
          <MissionStage n="05" title="Payoff - what you saved"
            value={() => `${r().massLeverage.toFixed(1)}× · ${fmtUsd(r().costSavingsUsd)}`}
            cls={() => "good"}
            note={() => `Launching a ${fmtNum(r().launchedMassKg / 1000)} t seed instead of a ${fmtNum(r().targetInstalledMassKg / 1000)} t factory is ${r().massLeverage.toFixed(1)}× leverage - ${fmtUsd(r().replicationLaunchCostUsd)} instead of ${fmtUsd(r().directLaunchCostUsd)}, a saving of ${fmtUsd(r().costSavingsUsd)}. That gap is the entire reason to send a self-replicating seed.`} />
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            One pure fold over all four modules - <strong style="color:var(--text)">launch-economics</strong>, <strong style="color:var(--text)">closure-sim</strong>, <strong style="color:var(--text)">probe-sim</strong>, and <strong style="color:var(--text)">power-budget</strong> - composed in the <strong style="color:var(--text)">mission</strong> module and run live in pimas. Every number traces to a source (see each module's REFERENCES.md)<Cite ids={["nasa-cp-2255-1980", "kopp-lean-2011", "landauer-1961", "tsiolkovsky-1903"]} />; the launch scalars are representative sourced values.
            <br /><br />
            <em>Honest caveat:</em> there is no sourced per-module mass breakdown for the Borgue &amp; Hein probe yet<Cite ids="borgue-hein-2020" /> (an open gap), so the factory here is closure-sim's lunar-regolith seed scenario used as a stand-in - a real bill of materials, but not probe-specific. No masses are invented to fill that gap.
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
  if (r.binding.vitaminLimited) walls.push("it runs out of imported vitamins - the electronics wall, now at fleet scale");
  if (r.binding.powerLimited) walls.push("its probes drift too far from the Sun to keep building - a spatial power wall");
  if (r.binding.capLimited) walls.push("it reaches the fleet cap you set");
  const why = walls.length ? walls.join("; and ") : "the mission window simply ends";
  const dbl = r.doublingTimeDays === null ? "never doubles in the window" : `first doubles in ${fmtDays(r.doublingTimeDays)}`;
  return `The fleet grows to ${r.finalPopulation} probes (${dbl}), spreading out to ${r.maxDistanceAu.toFixed(1)} AU and consuming ${fmtNum(r.vitaminsConsumedKg / 1000)} t of vitamins. It stops growing because ${why}. Same seed, same run - every time.`;
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
          <h1>One probe becomes a fleet - until it hits the same two walls.</h1>
          <p class="lede">
            Give one self-replicating probe local sunlight and imported parts, and it copies itself; the copies disperse outward and copy again. This is that fleet as a <strong>pure, seeded</strong> simulation - a handful of probes, not a swarm. Drag the knobs, then <strong>scrub through the mission</strong> and watch the fleet grow and spread. It's fully deterministic: same seed, same fleet, every run.
          </p>
          <div class="card chartcard">
            <FleetChart model={m} />
            <p class="chartcap">FIG.1 - fleet size (cyan) and how far the farthest probe has spread (amber) over 40 years. The dashed line is the day you're scrubbed to.</p>
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
            <p class="chartcap">FIG.2 - the final fleet, each probe placed by its distance from the Sun. Green: still building. Grey: in transit. Push the start distance out and watch replication choke on the inverse-square power wall.</p>
          </div>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            A pure, seeded fold (mulberry32 RNG threaded through state - byte-identical to the Python) over the <strong style="color:var(--text)">multi-probe</strong> module, live in pimas. Each probe builds at <strong style="color:var(--text)">closure-sim</strong>'s min(machinery, energy-cap) rate using <strong style="color:var(--text)">probe-sim</strong>'s 1/d² power; a finite vitamin pool and 1/d² dispersal are the two ceilings. Physics and figures trace to the sibling modules' REFERENCES.md<Cite ids={["nasa-cp-2255-1980", "kopp-lean-2011", "borgue-hein-2020"]} />; the factory is the lunar-regolith seed scenario used as a stand-in (the probe-BOM gap persists).
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

  // Deep-space background + a soft vignette.
  ctx.globalCompositeOperation = "source-over";
  ctx.fillStyle = "#06070a";
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
  const vg = ctx.createRadialGradient(CANVAS_W / 2, CANVAS_H / 2, 0, CANVAS_W / 2, CANVAS_H / 2, CANVAS_W * 0.6);
  vg.addColorStop(0, "rgba(22,28,38,0.45)");
  vg.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = vg;
  ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

  // Stars, drawn additively so settled clusters bloom into a glowing front. Settled
  // stars flash white when the scrub has just crossed their settlement year, then cool
  // from cyan to teal with age; unsettled stars are a dim dust.
  const flash = Math.max(1, m.maxYear() * 0.03);
  const coolSpan = Math.max(1, m.maxYear() * 0.6);
  ctx.globalCompositeOperation = "lighter";
  for (let i = 0; i < r.xs.length; i++) {
    const sy = r.settledYear[i];
    const x = px(r.xs[i]), y = py(r.ys[i]);
    if (sy >= 0 && sy <= year) {
      const age = year - sy;
      if (age < flash) {
        ctx.fillStyle = "rgba(240,245,255,0.95)"; // just settled - a white flash
      } else {
        const t = Math.min(1, age / coolSpan); // cyan (88,199,214) → teal (36,116,150)
        ctx.fillStyle = `rgba(${Math.round(88 - 52 * t)},${Math.round(199 - 83 * t)},${Math.round(214 - 64 * t)},0.8)`;
      }
      ctx.beginPath();
      ctx.arc(x, y, age < flash ? 2.8 : 2.0, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.fillStyle = "rgba(96,116,140,0.22)";
      ctx.beginPath();
      ctx.arc(x, y, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  ctx.globalCompositeOperation = "source-over";
  // The wavefront: a ring at the current front radius, centred on the homeworld.
  const front = m.settledAt().frontPc;
  const ox = px(r.xs[r.origin]), oy = py(r.ys[r.origin]);
  ctx.strokeStyle = "rgba(232,163,61,0.5)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(ox, oy, front * s, 0, Math.PI * 2);
  ctx.stroke();

  // The homeworld - a bright amber core with a soft halo.
  const halo = ctx.createRadialGradient(ox, oy, 0, ox, oy, 12);
  halo.addColorStop(0, "rgba(232,163,61,0.9)");
  halo.addColorStop(1, "rgba(232,163,61,0)");
  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(ox, oy, 12, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#f4c46a";
  ctx.beginPath();
  ctx.arc(ox, oy, 4, 0, Math.PI * 2);
  ctx.fill();

  // Coordination cue: the link from the homeworld to the hovered star, drawn in the
  // rung's colour, plus a ring on the star. The "aha" - every inter-star link is red
  // (independent colonies). Reading hoverStar here means a hover redraws the field, which
  // at ~10³ stars is trivially cheap (§7: still one canvas, one effect).
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

/**
 * Map a canvas-space point to the nearest star index (within ~8 px), or null. Inverts the
 * same projection `drawSwarm` uses - no per-star DOM, no hit regions; a brute O(N) scan is
 * negligible at slice-1 field sizes.
 */
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
    return `With ${m.params[1].get()} offspring per settlement the front can't fill the field - raise it above zero and the reachable galaxy fills exponentially.`;
  }
  if (r.policy === "powered") {
    const probeSpeedPcPerYr = (m.params[2].get() * 3.15576e7) / 3.0856775814913673e13;
    const frontSpeedFrac = (r.frontRadiusPc / r.t100Years) / probeSpeedPcPerYr * 100;
    return `Powered flight: from one homeworld the front settles all ${r.nStars} stars in ${myr(r.t100Years)} Myr (50% by ${myr(r.t50Years ?? 0)}, 90% by ${myr(r.t90Years ?? 0)}), the wavefront advancing at only ~${frontSpeedFrac.toFixed(0)}% of a probe's speed. Now switch on a slingshot policy and watch it accelerate - the whole point of Nicholson & Forgan's paper.`;
  }
  const tail = r.policy === "slingshot_maxboost"
    ? "Chasing the biggest boost reaches higher speeds but wastes travel, so it's actually slower than nearest-star - exactly what Nicholson & Forgan found."
    : "Nearest-star slingshots stay the most time-effective policy (Nicholson & Forgan's headline).";
  return `Slingshots: probes steal speed from the stars' galactic motion, peaking at ${fmtNum(r.maxProbeSpeedKmS)} km/s (from a ${fmtNum(m.params[2].get())} km/s powered cruise) and filling the field in just ${myr(r.t100Years)} Myr. ${tail} Same seed, same galaxy, every run.`;
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

// The coordination-mode readout for the hovered star. Reads one memo (hoverInfo) - the
// reactive graph scales with the star a human inspects, never with nStars (§7).
const explainCoord = (m: SwarmModel): string => {
  const info = m.hoverInfo();
  if (info === null)
    return "Hover any star in the field above. Coordination fidelity is set by ρ = round-trip light-time ÷ decision timescale: when ρ ≪ 1 news arrives while it's still current (tight control possible); when ρ ≳ 1 the world changes faster than word of it arrives. Every ~1 pc hop in this galaxy already lands in the top rung - light-years of lag, so each settled system is a causally-disconnected autonomous colony. That collapse is the lesson: across interstellar space you don't coordinate a swarm, you set its priors before launch and let geometry do the rest.";
  if (info.isOrigin) return "That's the homeworld - zero lag to itself. Hover another star to see the light-speed gap open up.";
  return `This star is ${info.distPc.toFixed(2)} pc from home. A signal takes ${fmtLatency(info.oneWayYears)} one way, ${fmtLatency(info.roundTripYears)} round-trip - that's ρ ≈ ${info.rho < 0.001 ? info.rho.toExponential(1) : fmtNum(info.rho, 2)} against a ${fmtNum(m.decisionTimescale(), 2)}-yr decision cadence. Coordination mode: ${info.rung.label} (${info.rung.who}), the ${info.rung.analog} regime.`;
};

function RungLegend(props: { model: SwarmModel }) {
  const m = props.model;
  const activeKey = () => m.hoverInfo()?.rung.key ?? null;
  return (
    <div class="btnrow" style="flex-wrap:wrap;gap:6px 14px;align-items:center">
      <For each={() => RUNGS}>
        {(rung) => (
          <span
            class="note"
            style={() =>
              `display:inline-flex;align-items:center;gap:6px;opacity:${activeKey() === null || activeKey() === rung.key ? 1 : 0.4};font-weight:${activeKey() === rung.key ? 700 : 400}`
            }
          >
            <span style={`width:10px;height:10px;border-radius:50%;background:${rung.color};display:inline-block`} />
            {rung.label} <span style="opacity:.6">· {rung.analog}</span>
          </span>
        )}
      </For>
    </div>
  );
}

function SwarmSurface(props: { model: SwarmModel }) {
  const m = props.model;
  const [canvas, setCanvas] = createSignal<HTMLCanvasElement | null>(null);

  // Draw whenever the field (knobs/seed) or the scrubbed year changes - a single effect
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
  // % slowdown of the fill-100% timescale vs the perfect-info baseline (only in lightspeed).
  const slowdownPct = (): number | null => {
    const b = m.instantBaseline();
    const r = m.result();
    if (!b || !b.t100Years || !r.t100Years) return null;
    return ((r.t100Years - b.t100Years) / b.t100Years) * 100;
  };
  const wastedPct = () => { const r = m.result(); return r.totalArrivals ? (r.wastedArrivals / r.totalArrivals) * 100 : 0; };

  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">The swarm · a settlement front · a live model</p>
          <h1>One probe. Then the galaxy fills in.</h1>
          <p class="lede">
            Give a self-replicating probe a galaxy of stars and it spreads - settle a star, build copies, send them to the next nearest stars, repeat. This is that front as a <strong>pure, seeded</strong> simulation (slice 1 of the swarm). Press play and watch the reachable field light up from one homeworld; drag the knobs and reseed the galaxy. Deterministic: same seed, same spread, every run.
          </p>
          <div class="card chartcard">
            <canvas
              ref={setCanvas}
              width={CANVAS_W}
              height={CANVAS_H}
              style="width:100%;height:auto;display:block;border-radius:8px;background:#0b0d10;cursor:crosshair"
              onMouseMove={(e: MouseEvent) => {
                const cv = e.currentTarget as HTMLCanvasElement;
                const rect = cv.getBoundingClientRect();
                const mx = (e.clientX - rect.left) * (cv.width / rect.width);
                const my = (e.clientY - rect.top) * (cv.height / rect.height);
                m.setHoverStar(pickStar(m, mx, my));
              }}
              onMouseLeave={() => m.setHoverStar(null)}
            />
            <p class="chartcap">FIG.1 - the star field. Amber: the homeworld. Cyan: settled by the scrubbed year (white = just settled). Grey: not yet reached. The amber ring is the settlement wavefront. <b>Hover any star</b> to read its light-speed coordination lag from home.</p>
          </div>
          <div class="btnrow" style="align-items:center;gap:12px">
            <button class="act primary" onClick={togglePlay}>{() => (m.playing() ? "⏸ pause" : "▶ play")}</button>
            <input
              type="range"
              aria-label="Mission year (scrub the settlement front)"
              min={0}
              max={() => m.maxYear()}
              step={() => Math.max(1, m.maxYear() / 400)}
              value={() => m.scrubYear()}
              onInput={(e: Event) => { m.setPlaying(false); m.setScrubYear(Number((e.target as HTMLInputElement).value)); }}
              style="flex:1"
            />
            <span class="ctl-val" style="min-width:110px;text-align:right">{() => fmtNum(m.scrubYear())} yr</span>
          </div>
          <div class="btnrow" style="align-items:center;gap:8px;margin-top:4px">
            <span class="note" style="align-self:center;margin-right:4px">travel policy:</span>
            <For each={() => ["powered", "slingshot_nearest", "slingshot_maxboost"] as const}>
              {(pol: "powered" | "slingshot_nearest" | "slingshot_maxboost") => (
                <button
                  class={() => `act ${m.policy() === pol ? "primary" : "ghost"}`}
                  onClick={() => { m.setPolicy(pol); m.setPlaying(false); m.setScrubYear(m.maxYear()); }}
                >{POLICY_LABELS[pol]}</button>
              )}
            </For>
          </div>
          <div class="btnrow" style="align-items:center;gap:8px;margin-top:4px">
            <span class="note" style="align-self:center;margin-right:4px">coordination:</span>
            <For each={() => ["instant", "lightspeed"] as const}>
              {(mode: "instant" | "lightspeed") => (
                <button
                  class={() => `act ${m.coordination() === mode ? "primary" : "ghost"}`}
                  onClick={() => { m.setCoordination(mode); m.setPlaying(false); m.setScrubYear(m.maxYear()); }}
                >{mode === "instant" ? "Perfect info" : "Light-speed lag"}</button>
              )}
            </For>
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
              <StatRow what="Peak probe speed" cite="nicholson-forgan-2013" sub="powered = the cruise; slingshots accumulate" value={() => `${fmtNum(m.result().maxProbeSpeedKmS)} km/s`} cls={() => (m.result().policy === "powered" ? "" : "good")} />
              <StatRow what="Wasted trips" sub="arrivals at an already-settled star" value={() => `${fmtNum(m.result().wastedArrivals)} (${wastedPct().toFixed(0)}%)`} cls={() => (m.coordination() === "lightspeed" ? "chip" : "")} />
              <StatRow what="Slowdown vs perfect info" sub="the cost of light-speed lag" value={() => (slowdownPct() === null ? "-" : `+${slowdownPct()!.toFixed(0)}%`)} cls={() => { const s = slowdownPct(); return s === null ? "" : s > 5 ? "bad" : "good"; }} />
              <p class="explain" style="margin-top:18px">{() => explainSwarm(m)}</p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>02</b> &nbsp;/&nbsp; The coordination horizon - can the swarm even talk?</p>
          <div class="lab">
            <div class="card controls">
              <p class="panel-head">The coordination ratio</p>
              <p class="note" style="margin:0 0 12px">
                ρ = round-trip light-time ÷ decision timescale. The rung a link falls into is fixed by its <em>absolute</em> light-lag (sourced from teleoperation &amp; DTN regimes); ρ is a tunable lens - set the decision cadence you care about.
              </p>
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
                  style="width:100%"
                />
              </div>
              <p class="panel-head" style="margin-top:18px">The staircase</p>
              <RungLegend model={m} />
            </div>
            <div class="card readouts">
              <p class="panel-head">The hovered star</p>
              <StatRow what="Distance from home" value={() => (m.hoverInfo() ? `${m.hoverInfo()!.distPc.toFixed(2)} pc` : "-")} cls={() => "metal"} />
              <StatRow what="One-way light time" value={() => (m.hoverInfo() ? fmtLatency(m.hoverInfo()!.oneWayYears) : "-")} />
              <StatRow what="Round-trip latency" sub="a message and its reply" value={() => (m.hoverInfo() ? fmtLatency(m.hoverInfo()!.roundTripYears) : "-")} cls={() => "metal"} />
              <StatRow what="ρ = latency ÷ τ" value={() => { const i = m.hoverInfo(); return i ? (i.rho < 0.001 ? i.rho.toExponential(1) : `${fmtNum(i.rho, 2)}×`) : "-"; }} cls={() => { const i = m.hoverInfo(); return i && i.rho >= 1 ? "bad" : i ? "good" : ""; }} />
              <StatRow what="Coordination mode" sub={() => (m.hoverInfo() ? m.hoverInfo()!.rung.analog + " regime" : "hover a star")} value={() => (m.hoverInfo() ? m.hoverInfo()!.rung.label : "-")} cls={() => { const i = m.hoverInfo(); return i && i.rung.index >= 3 ? "bad" : i && i.rung.index >= 2 ? "chip" : i ? "good" : ""; }} />
              <p class="explain" style="margin-top:18px">{() => explainCoord(m)}</p>
            </div>
          </div>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            A pure, seeded, fixed-step fold (mulberry32 threaded through state, byte-identical to the Python) over the <strong style="color:var(--text)">swarm</strong> module, live in pimas - the canvas reads the fold's settlement buffers each frame; there is no DOM node per star (the rendering discipline that scales, CLAUDE.md §7). Three travel policies (powered, and two gravitational-slingshot policies that steal speed from stellar motion) after Nicholson &amp; Forgan (2013)<Cite ids="nicholson-forgan-2013" />; powered speed (3×10⁻⁵c ≈ 9 km/s), density (1 star/pc³), and the slingshot boost (their Eq. 4, u_esc ≈ 617.5 km/s solar) are the paper's parameters, with rotation/dispersion tagged [ESTIMATE]. The coordination-horizon overlay (§02) turns each link's light-lag into a coordination rung after Olfati-Saber &amp; Murray (2004), Ferrell (1965) and RFC 4838<Cite ids={["olfati-saber-murray-2004", "ferrell-1965", "rfc-4838"]} />; rung edges tagged [ESTIMATE]. The light-speed-limited-coordination <em>simulation</em> (FRONTIER #1) is built - toggle "Light-speed lag" above; the one remaining slice is the full 200k-star WebGL render engine. See swarm/REFERENCES.md.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── the spine surface: one factory threaded through all three scales ─────────
function SpineSurface(props: { model: SpineModel }) {
  const m = props.model;
  const r = () => m.result();
  // The dwell's galactic cost, in words: measured A/B for the fast policies, the analytic
  // fraction for powered (where a brute-force A/B is infeasible - itself the finding).
  const taxLabel = () => {
    const t = m.dwellTax();
    if (t && t.taxFraction !== null && t.t100ZeroDwell !== null && t.t100WithDwell !== null)
      return `+${(t.taxFraction * 100).toFixed(2)}% (${fmtNum(t.t100ZeroDwell)} → ${fmtNum(t.t100WithDwell)} yr)`;
    const f = r().dwellFractionOfT100;
    return f === null ? "-" : `~${f.toExponential(1)} of the fill (negligible)`;
  };
  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">The whole project · across scale · one derived number</p>
          <h1>One factory. Three scales. The same build time, weighed at each.</h1>
          <p class="lede">
            The project models self-replication at three scales - a <strong>single factory</strong>, a <strong>local fleet</strong>, and a <strong>galaxy</strong> - each its own model. This surface threads <strong>one</strong> factory through all three, so a number that was guessed at one scale is <strong>derived</strong> instead: the galaxy model's per-star build-and-launch dwell used to be an unsourced <em>zero</em> (instant replication). Here it is derived from the very same factory build physics the fleet uses - and shown to be a negligible tax on galactic exploration, because interstellar travel dwarfs it.
          </p>
          <div class="card" style="margin-top:8px">
            <p class="panel-head" style="margin-bottom:8px">The cross-scale reading</p>
            <p class="explain" style="margin:0;font-size:1.05rem">{() => r().verdict}</p>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>◆</b> &nbsp;/&nbsp; The knobs</p>
          <div class="lab">
            <div class="card controls">
              <p class="panel-head">The galaxy</p>
              <For each={() => m.params}>{(p: ParamSignal) => <Slider p={p} />}</For>
              <div class="btnrow" style="align-items:center;gap:8px;margin-top:12px">
                <span class="note" style="align-self:center;margin-right:4px">travel policy:</span>
                <For each={() => ["powered", "slingshot_nearest", "slingshot_maxboost"] as const}>
                  {(pol: "powered" | "slingshot_nearest" | "slingshot_maxboost") => (
                    <button class={() => `act ${m.policy() === pol ? "primary" : "ghost"}`} onClick={() => m.setPolicy(pol)}>{POLICY_LABELS[pol]}</button>
                  )}
                </For>
              </div>
              <p class="note" style="margin-top:10px">The dwell tax is measured directly (a fine-step A/B of the derived dwell versus zero) only for the slingshot policies; for powered, resolving a roughly one-year dwell against hundred-thousand-year hops by brute force is impractical - so the analytic fraction is shown instead. That gap <em>is</em> the finding.</p>
            </div>
            <div class="card readouts">
              <p class="panel-head">The shared factory, and what it derives</p>
              <StatRow what="Closure ratio" cite="nasa-cp-2255-1980" sub="one factory, read once, used by every scale" value={() => `${(r().closureRatio * 100).toFixed(1)}%`} cls={() => "metal"} />
              <StatRow what="Time to build one copy" cite="borgue-hein-2020" sub="derived at 1 AU · the cross-scale handoff" value={() => `${fmtDays(r().copyTimeDays)} (${r().settleTimeYears.toFixed(2)} yr)`} cls={() => "chip"} />
              <StatRow what="Galactic dwell (was)" sub="the old unsourced estimate" value={() => "0 yr (instant)"} cls={() => "bad"} />
              <StatRow what="Galactic dwell (now)" sub="derived, not guessed" value={() => `${r().settleTimeYears.toFixed(2)} yr`} cls={() => "good"} />
              <StatRow what="Manufacturing tax on the fill" cite="nicholson-forgan-2013" sub="cost of a real dwell vs. instant" value={taxLabel} cls={() => (m.policy() === "powered" ? "" : "chip")} />
            </div>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>▶</b> &nbsp;/&nbsp; The same build time, at three scales</p>
          <MissionStage n="01" title="One factory - the build cadence is set"
            value={() => `${fmtDays(r().copyTimeDays)} per copy`}
            cls={() => "chip"}
            note={() => `The seed factory is ${(r().closureRatio * 100).toFixed(1)}% closed and reaches full output in ${fmtDays(r().singleFactoryTimeToTargetDays)}. The number that travels up the scales is simpler: the time to build one copy's worth of local structure at 1 AU, ${fmtDays(r().copyTimeDays)}. Every scale below reuses this exact figure - no scale invents its own.`} />
          <MissionStage n="02" title="Local fleet - here the build time IS the clock"
            value={() => `doubles in ${fmtDays(r().fleetDoublingDays)}`}
            cls={() => "chip"}
            note={() => `Across AU distances transit is days, so replication time dominates: the fleet's first doubling lands at ~${fmtDays(r().fleetDoublingDays)} - essentially the ${fmtDays(r().copyTimeDays)} copy time above. It grows to ${fmtNum(r().fleetFinalPopulation)} probes and ends ${r().fleetBinding}.`} />
          <MissionStage n="03" title="Galaxy - the same dwell all but vanishes"
            value={() => (r().swarmT100Years === null ? "never fills" : `fills in ${fmtNum(r().swarmT100Years!)} yr`)}
            cls={() => (r().swarmT100Years === null ? "bad" : "good")}
            note={() => (r().swarmT100Years === null
              ? `With these knobs the front cannot spread (no offspring), so the field never fills and the dwell is moot.`
              : `The front reaches all ${fmtNum(r().nStars)} stars in ${fmtNum(r().swarmT100Years!)} yr under the ${POLICY_LABELS[r().policy]} policy. The same ${r().settleTimeYears.toFixed(2)} yr dwell that governs the fleet is only ${taxLabel()} of that - interstellar transit dominates by orders of magnitude, so the manufacturing cadence that is the clock for a fleet is a rounding error for a galaxy.`)} />
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            A pure, deterministic fold over the <strong style="color:var(--text)">spine</strong> module - the cross-scale integrator - live in pimas, composing the parity-tested TS ports of closure-sim, multi-probe, and swarm. It adds <em>no new numbers</em>: the galactic dwell is derived from the factory's 1-AU copy time (closure and machinery from NASA CP-2255 (1980)<Cite ids="nasa-cp-2255-1980" /> and Borgue &amp; Hein (2020)<Cite ids="borgue-hein-2020" />; the exploration timescale from Nicholson &amp; Forgan (2013)<Cite ids="nicholson-forgan-2013" />). It replaces one honest gap - the swarm's old zero dwell - by grounding it. See spine/REFERENCES.md.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── the overview surface: what the project is, and where it is ───────────────
type ModuleRow = { name: string; surface: Surface; status: string; statusCls: string; cite: string; desc: string };
const MODULE_STATUS: ModuleRow[] = [
  { name: "closure-sim", surface: "wall", status: "Done", statusCls: "good", cite: "nasa-cp-2255-1980",
    desc: "Describes a factory as a parts list and computes its closure - the fraction of its own weight it can build from local material - then finds the electronics wall: chips are the one part a lone factory cannot make." },
  { name: "power-budget", surface: "power", status: "Done", statusCls: "good", cite: "landauer-1961",
    desc: "Splits a solar-limited power budget between building, thinking, and housekeeping, floored by the Landauer thermodynamic limit and scaled against the roughly 20-watt human brain." },
  { name: "launch-economics", surface: "launch", status: "Done", statusCls: "good", cite: "tsiolkovsky-1903",
    desc: "Measures the launch-mass leverage of shipping a self-replicating seed instead of a finished factory - installed kilograms per launched kilogram, as a function of closure." },
  { name: "mission", surface: "mission", status: "Done", statusCls: "good", cite: "kopp-lean-2011",
    desc: "Runs the whole operation end to end as one deterministic pass over the four modules above: launch, arrive, split power, replicate, and price the payoff." },
  { name: "multi-probe", surface: "fleet", status: "Done (v1)", statusCls: "good", cite: "borgue-hein-2020",
    desc: "A small deterministic fleet of tens of self-replicating probes that re-creates two limits from first principles: a finite vitamin pool and a spatial power wall where sunlight thins with distance." },
  { name: "probe-sim", surface: "probe", status: "In progress", statusCls: "chip", cite: "borgue-hein-2020",
    desc: "Models a single solar-electric probe after Borgue and Hein (2020). The solar-power and range math is live; the full replication model waits on a per-module mass breakdown that does not exist in the literature yet." },
  { name: "swarm", surface: "swarm", status: "In progress", statusCls: "chip", cite: "nicholson-forgan-2013",
    desc: "Models how fast a probe could fill the galaxy star to star, after Nicholson and Forgan (2013): the core, all three slingshot policies, a coordination-lag overlay, and a light-speed-limited coordination simulation. A WebGL renderer for 200,000 stars is the one parked fork." },
  { name: "spine", surface: "spine", status: "Done", statusCls: "good", cite: "nicholson-forgan-2013",
    desc: "The cross-scale integrator: threads one factory through all three scales so their replication cadences are derived from one source, not assumed. It replaces the galaxy model's old unsourced zero dwell with a figure derived from the same factory build physics the fleet uses - and shows it is a negligible tax on galactic exploration." },
];

// The project's stated research conclusions, each backed by a source and a live surface.
// Kept here (not in a repo doc) because the site is standalone: this is the public
// findings page. Numbers trace to the modules' REFERENCES.md and FINDINGS.md.
type FindingRow = { headline: string; surface: Surface; cite: string | string[]; detail: string };
const FINDINGS: FindingRow[] = [
  { headline: "Chips are the wall - made of energy as much as supply chain", surface: "wall",
    cite: ["williams-ayres-heller-2002", "nagapurkar-das-2022"],
    detail: "Compute logic costs roughly 8,000 kWh/kg to make against about 5 for smelted metal. A factory escapes the wall only if it is both highly self-sufficient and swimming in power: the lunar seed reaches its target in ~17 years instead of ~29 by making its own chips, but only when fed ~4 MW; at ~1 MW that backfires." },
  { headline: "The realistic factory never closes on chips", surface: "wall",
    cite: ["guided-self-replicating-factory-2021", "nasa-cp-2255-1980"],
    detail: "Achievable mass closure is about 70 to 96 percent, and chasing 100 percent is not worth it, so imported electronics are a permanent design feature rather than a temporary compromise." },
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
    detail: "The finite vitamin pool caps how many copies can ever exist (the electronics wall made spatial), and a spatial power wall stops expansion around 13.6 AU for the default scenario - not for lack of parts, but distance from the Sun." },
  { headline: "Filling the galaxy: slingshots dominate, nearest beats max-boost", surface: "swarm",
    cite: "nicholson-forgan-2013",
    detail: "A powered front advances at only ~40 percent of a probe's cruise speed. Gravitational slingshots reach ~1000 km/s and are far faster - and targeting the nearest star beats chasing the biggest boost on total time." },
  { headline: "Light-speed coordination is a real, policy-dependent tax", surface: "swarm",
    cite: ["nicholson-forgan-2013", "olfati-saber-murray-2004"],
    detail: "Deciding against a light-delayed belief of what is already settled costs a median ~30 percent of the exploration timescale for nearest-slingshot, ~50 for max-boost, and ~0 for powered flight. A connected field still fills completely - lag alone makes no permanent plateau." },
  { headline: "Which constraint binds at which scale", surface: "spine",
    cite: "nicholson-forgan-2013",
    detail: "The factory's own build physics fixes a ~582-day copy time, which is the local fleet's doubling clock - yet only ~8e-7 of a ~2-million-year galactic fill (about 0.4 percent of exploration time even for fast slingshots). The cadence that rules a fleet is a rounding error against interstellar transit." },
];

function OverviewSurface() {
  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">A modular, source-checked model of self-replicating space manufacturing</p>
          <h1>What if you launched one factory, and it built the rest?</h1>
          <p class="lede">
            A self-replicating factory lands on the Moon, an asteroid, or Mars, digs up local material, and uses it to build a working copy of itself. One becomes two, two become four, and an entire industry grows from a single rocket's worth of cargo. That is the leverage worth taking seriously: you pay to launch one seed instead of a whole finished installation. This site is a set of small, live, interactive models that test how far that idea actually holds up, where the physics fights back, and what it would really take.
          </p>
          <p class="lede">
            Every model runs in your browser, so you can move the assumptions yourself and watch the numbers recompute. And every number traces to published research - nothing here is a guess.
          </p>
          <div class="btnrow" style="margin-top:8px">
            <button class="act primary" onClick={() => mount("mission")}>Start with the full mission</button>
            <button class="act" onClick={() => mount("wall")}>See the electronics wall</button>
            <button class="act" onClick={() => mount("swarm")}>Watch the galaxy fill</button>
            <button class="act ghost" onClick={() => mount("sources")}>Sources</button>
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>01</b> &nbsp;/&nbsp; What this is</p>
          <h2>Research models, not predictions.</h2>
          <p>
            These are order-of-magnitude research models. The goal is to understand which physical limits bind, and roughly how hard - not to claim a schedule or a guaranteed outcome. The project is built as separate, independent modules rather than one giant simulation: each models a single slice of the problem, is runnable and tested on its own, and connects to the others through clean interfaces. Keeping the pieces small is what keeps them checkable.
          </p>
          <p>
            The rule that separates this from a fun demo is simple: <strong>no number is assumed</strong>. Every mass, energy, rate, and cost either traces to a citable published source or is derived by explicit math from numbers that do<Cite ids={["nasa-cp-2255-1980", "kopp-lean-2011", "landauer-1961"]} />. Where the literature genuinely has no value, the gap is marked as a gap rather than filled with an invented figure, and any best-defensible estimate is labelled as an estimate with its reasoning. The models themselves are pure and deterministic - the same inputs and the same random seed always produce the same result - so the interactive what-if features are exact and every run reproduces.
          </p>
          <p class="note" style="margin-top:6px">
            Every figure on this site carries a marker like this<Cite ids="borgue-hein-2020" /> - hover or tab to it for the exact paper and what it grounds. The full list is on the <a href="#/sources" onClick={(e: Event) => { e.preventDefault(); mount("sources"); }}>Sources</a> page.
          </p>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>02</b> &nbsp;/&nbsp; What we have learned</p>
          <h2>One argument, told at every scale.</h2>
          <p>
            Read together, the models trace a single line: self-replication buys enormous launch-mass leverage, but physical walls reappear at every scale and decide how far the idea holds. Each result below is live in a surface you can drive - click to open it.
          </p>
          <div class="card" style="padding:6px 20px;margin-top:8px">
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
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>03</b> &nbsp;/&nbsp; Where the project is</p>
          <h2>Eight modules. Six complete, two in progress.</h2>
          <p>
            The project is planned as upwards of ten interacting modules over time. Eight exist today. Here is where each one stands - click any row to open its live surface.
          </p>
          <div class="card" style="padding:6px 20px;margin-top:8px">
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
          </div>
        </div>
      </section>

      <section>
        <div class="wrap">
          <p class="marker"><b>04</b> &nbsp;/&nbsp; The honest gaps</p>
          <p>
            Six of the eight modules are complete and running live (closure-sim, power-budget, launch-economics, mission, multi-probe, and the spine that ties them together across scales), and the end-to-end mission chain composes them. The two in progress are at very different stages: <strong>swarm</strong> is substantially built and interactive, with only a parked rendering fork and some deferred coordination features left; <strong>probe-sim</strong>'s full replication model is deliberately on hold behind a real data gap. The main known open gaps, all stated openly in the modules themselves:
          </p>
          <ul class="gaps">
            <li><strong>The probe bill-of-materials.</strong> There is no sourced per-module mass breakdown for the Borgue and Hein probe<Cite ids="borgue-hein-2020" />, which blocks probe-sim and forces the mission surface to use a real, sourced lunar-regolith factory as a stand-in rather than a probe-specific one. No masses are invented to fill it.</li>
            <li><strong>The 200,000-star WebGL renderer.</strong> The swarm's algorithm already scales; drawing 200,000 stars at full frame rate is a parked rendering fork, since the current canvas tops out around ten thousand.</li>
            <li><strong>The swarm coordination siblings.</strong> Probe-to-probe relaying of news, a settlement death term, and a faster arrival index for the largest scales are deferred, built on the light-speed coordination slice that is already done.</li>
          </ul>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            Explore the models directly - each is a live surface you can drive: move the assumptions, preview a what-if before committing to it, and watch the model explain which limit is binding and why. Nothing here asks you to take a number on trust: every figure is backed by a source on the <a href="#/sources" onClick={(e: Event) => { e.preventDefault(); mount("sources"); }}>Sources</a> page, and every honest gap is marked as a gap. Built on <strong style="color:var(--text)">pimas</strong>, a from-scratch reactive framework.
          </p>
        </div>
      </footer>
    </div>
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
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">The bibliography</p>
          <h1>Every number on this site, and where it came from.</h1>
          <p class="lede">
            This project holds itself to one rule: no number is assumed. Each mass, energy, rate, and cost either traces to a source below or is derived by explicit math from ones that do. This is the full list, consolidated from every module - what each source is, a link where one exists, and the specific quantity it grounds. Each source is also tagged with how much weight it carries, so it is clear which figures rest on peer-reviewed work and which on a vendor page or a wiki cross-check.
          </p>
          <p class="note">
            {() => `${SOURCES.length} sources across ${sourceCategories().length} areas. Where the literature has no value, the gap is marked in the module rather than filled - see the honesty note at the foot of this page.`}
          </p>
        </div>
      </section>

      <For each={() => sourceCategories()}>
        {(cat: string) => (
          <section>
            <div class="wrap">
              <p class="marker"><b>{() => `${SOURCES.filter((s) => s.category === cat).length}`}</b> &nbsp;/&nbsp; {cat}</p>
              <For each={() => SOURCES.filter((s) => s.category === cat)}>
                {(s: Source) => (
                  <div class="src">
                    <div class="src-top">
                      <span class="src-num">[{sourceNumber(s.id)}]</span>
                      <span class="src-cite"><b>{s.authors}</b> ({s.year}). {s.title}. <i>{s.venue}</i>.</span>
                    </div>
                    <div class="src-meta">
                      <span class={`src-strength st-${s.strength}`} title={STRENGTH_NOTE[s.strength]}>{STRENGTH_LABEL[s.strength]}</span>
                      <span class="src-mods">used in: {s.modules.join(", ")}</span>
                    </div>
                    <p class="src-grounds">{s.grounds}</p>
                    {s.url
                      ? <a class="src-link" href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a>
                      : <span class="src-nolink">Cited by full reference; no stable public link (textbook, standards resolution, or paywalled record).</span>}
                  </div>
                )}
              </For>
            </div>
          </section>
        )}
      </For>

      <section>
        <div class="wrap">
          <p class="marker"><b>+</b> &nbsp;/&nbsp; Honesty note: gaps and estimates</p>
          <p>
            Two kinds of number are called out at their use sites rather than sourced as fact, because sourcing them honestly is impossible today:
          </p>
          <ul class="gaps">
            <li><strong>[GAP] - the probe bill-of-materials.</strong> Borgue and Hein<Cite ids="borgue-hein-2020" /> give six modules and a 70/30 replicated-to-imported split, but not per-module masses at the fidelity a closure computation needs. No masses are invented; probe-sim and the mission surface use a real lunar-regolith factory as a stand-in until a defensible breakdown exists.</li>
            <li><strong>[ESTIMATE] - values the literature brackets but does not pin.</strong> Examples: brain-equivalent compute (~1e18 FLOPS, uncertain by ~2 orders of magnitude)<Cite ids="sandberg-bostrom-2008" />; the stars' galactic velocity in the slingshot model (~220 +/- 40 km/s), which Nicholson and Forgan defer<Cite ids="nicholson-forgan-2013" />; the coordination decision-timescale and rung edges<Cite ids={["ferrell-1965", "olfati-saber-murray-2004", "rfc-4838"]} />; and solar-cell and compute efficiencies, which are scenario inputs, not constants. Each is labelled [ESTIMATE] with its reasoning where it is used.</li>
          </ul>
          <p class="note" style="margin-top:10px">
            The per-module detail behind every entry here lives in that module's REFERENCES.md in the repository, which records value, source, and a verdict on how solid each one is.
          </p>
        </div>
      </section>

      <footer>
        <div class="wrap">
          <p>
            A mis-attributed number is treated as worse than an admitted gap. If you find a figure on this site that does not match its cited source, that is a bug - the whole project is meant to be checked against these references. Back to the <a href="#/" onClick={(e: Event) => { e.preventDefault(); mount("overview"); }}>overview</a>.
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
      <button class="nav-brand" onClick={() => mount("overview")} title="Project overview">von-neumann</button>
      <button class={`act ${props.surface === "overview" ? "primary" : "ghost"}`} onClick={() => mount("overview")}>Overview</button>
      <button class={`act ${props.surface === "mission" ? "primary" : "ghost"}`} onClick={() => mount("mission")}>Full mission</button>
      <button class={`act ${props.surface === "fleet" ? "primary" : "ghost"}`} onClick={() => mount("fleet")}>Fleet</button>
      <button class={`act ${props.surface === "swarm" ? "primary" : "ghost"}`} onClick={() => mount("swarm")}>Swarm</button>
      <button class={`act ${props.surface === "spine" ? "primary" : "ghost"}`} onClick={() => mount("spine")}>Across scales</button>
      <button class={`act ${props.surface === "wall" ? "primary" : "ghost"}`} onClick={() => mount("wall")}>Electronics wall</button>
      <button class={`act ${props.surface === "probe" ? "primary" : "ghost"}`} onClick={() => mount("probe")}>Single probe</button>
      <button class={`act ${props.surface === "launch" ? "primary" : "ghost"}`} onClick={() => mount("launch")}>Launch economics</button>
      <button class={`act ${props.surface === "power" ? "primary" : "ghost"}`} onClick={() => mount("power")}>Power budget</button>
      <button class={`act ${props.surface === "sources" ? "primary" : "ghost"}`} onClick={() => mount("sources")}>Sources</button>
    </div>
  );
}

// ── mount + routing: a shell hosting one surface per model, swapped by re-render ─
// The surface lives in the URL hash (#/swarm, #/wall/low_closure) so every surface is
// shareable, the browser Back/Forward buttons work, and a refresh restores where you
// were. mount() is the single navigation entry point (every onClick calls it); it
// renders, sets the title, and syncs the hash. A hashchange listener drives mount()
// back for external changes (Back/Forward, a pasted deep link), guarded so the two
// never loop. Kept here in the skin, not in pimas (7): routing is app plumbing.
const appEl = document.getElementById("app")!;
let disposeRender: (() => void) | null = null;
let model: WallModel | null = null;

const VALID_SURFACES: Surface[] = [
  "overview", "mission", "fleet", "swarm", "spine", "wall", "probe", "launch", "power", "sources",
];
const SURFACE_TITLE: Record<Surface, string> = {
  overview: "von-neumann - self-replicating space manufacturing",
  mission: "Full mission - von-neumann",
  fleet: "Fleet - von-neumann",
  swarm: "Swarm - von-neumann",
  spine: "Across scales - von-neumann",
  wall: "Electronics wall - von-neumann",
  probe: "Single probe - von-neumann",
  launch: "Launch economics - von-neumann",
  power: "Power budget - von-neumann",
  sources: "Sources - von-neumann",
};

function surfaceToHash(surface: Surface, scenarioKey: string): string {
  if (surface === "overview") return "#/";
  if (surface === "wall" && scenarioKey && scenarioKey !== "lunar") return `#/wall/${scenarioKey}`;
  return `#/${surface}`;
}
function parseHash(): { surface: Surface; scenarioKey: string } {
  const raw = location.hash.replace(/^#\/?/, "");
  const [s, scen] = raw.split("/");
  const surface = (VALID_SURFACES as string[]).includes(s) ? (s as Surface) : "overview";
  const scenarioKey = surface === "wall" && scen && SCENARIOS[scen] ? scen : "lunar";
  return { surface, scenarioKey };
}

// True while we are the ones writing the hash, so our own hashchange is ignored.
let suppressHash = false;

function mount(surface: Surface, scenarioKey = "lunar", updateUrl = true) {
  disposeRender?.();
  model?.dispose();
  model = null;
  if (surface === "overview") {
    disposeRender = render(() => (<div><Nav surface="overview" /><OverviewSurface /></div>), appEl);
  } else if (surface === "sources") {
    disposeRender = render(() => (<div><Nav surface="sources" /><SourcesSurface /></div>), appEl);
  } else if (surface === "wall") {
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
  } else if (surface === "spine") {
    const spm = createSpineModel();
    disposeRender = render(
      () => (
        <div>
          <Nav surface="spine" />
          <SpineSurface model={spm} />
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

  document.title = SURFACE_TITLE[surface];
  if (updateUrl) {
    const hash = surfaceToHash(surface, scenarioKey);
    if (location.hash !== hash) {
      suppressHash = true; // our own write; the listener below will skip it
      location.hash = hash;
    }
  }
}

// Back/Forward, or a pasted deep link: re-mount from the hash (without re-writing it).
window.addEventListener("hashchange", () => {
  if (suppressHash) { suppressHash = false; return; }
  const { surface, scenarioKey } = parseHash();
  mount(surface, scenarioKey, false);
});

// Initial load: honor a deep link, and normalize the bar without adding a history entry.
{
  const { surface, scenarioKey } = parseHash();
  const hash = surfaceToHash(surface, scenarioKey);
  if (location.hash !== hash) history.replaceState(null, "", hash);
  mount(surface, scenarioKey, false);
}
