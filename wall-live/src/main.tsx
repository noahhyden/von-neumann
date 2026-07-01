/**
 * The Electronics Wall, live. The narrative of closure-sim's `explainer.html`,
 * but every number is the real model running in pimas: drag the assumptions and
 * the simulation recomputes; preview "make its own chips" as a speculation (the
 * exact after-state, nothing committed) before you commit it; and watch the model
 * explain which ceiling is binding. The last panel shows the very same reactive
 * graph projected as an agent surface (subscribe / speculate / explain).
 */
import { createSignal, createMemo } from "pimas";
import { render } from "pimas/dom";
import { Show, For } from "pimas/flow";
import { createWallModel, fmtDays } from "./reactive-model.js";
import type { WallModel, ParamSignal } from "./reactive-model.js";
import { SCENARIOS } from "./scenarios.js";
import { GrowthChart } from "./chart.js";
import type { SimResult } from "./model.js";

const fmtNum = (n: number, d = 0) => n.toLocaleString(undefined, { maximumFractionDigits: d });
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

// ── mount, with scenario swapping by re-render ─────────────────────────────
const appEl = document.getElementById("app")!;
let disposeRender: (() => void) | null = null;
let model: WallModel | null = null;

function mount(key: string) {
  disposeRender?.();
  model?.dispose();
  model = createWallModel(SCENARIOS[key]);
  const active = model;
  disposeRender = render(() => <App model={active} scenarioKey={key} onScenario={mount} />, appEl);
}

mount("lunar");
