/** Base components every surface composes: one shell, one band, one panel, one figure. */
import { createSignal, createEffect } from "pimas";
import type { Child } from "pimas/dom";
import { For } from "pimas/flow";
import { sourceById, sourceNumber } from "./sources.js";
import type { Source } from "./sources.js";
import type { ParamSignal } from "./reactive-model.js";

const fmtNum = (n: number, d = 0) => n.toLocaleString(undefined, { maximumFractionDigits: d });

export type Tone = "metal" | "chip" | "good" | "bad" | "plain";
export type ActionKind = "default" | "primary" | "commit" | "ghost";

/** The one page frame: eyebrow, title, optional lede and hero figure, bands, footer. */
export function PageShell(props: {
  eyebrow: string;
  title: Child;
  lede?: Child;
  hero?: Child;
  children?: Child;
  footer?: Child;
}): Child {
  return (
    <div>
      <section class="hero">
        <div class="wrap">
          <p class="eyebrow">{props.eyebrow}</p>
          <h1>{props.title}</h1>
          {props.lede ? <p class="lede">{props.lede}</p> : null}
          {props.hero ?? null}
        </div>
      </section>
      {props.children ?? null}
      {props.footer ? <footer><div class="wrap"><p>{props.footer}</p></div></footer> : null}
    </div>
  );
}

/** One numbered band of the page. */
export function Band(props: { n?: string; label?: Child; children?: Child }): Child {
  return (
    <section>
      <div class="wrap">
        {props.n || props.label ? (
          <p class="marker">{props.n ? <b>{props.n}</b> : null}{props.n && props.label ? " / " : ""}{props.label}</p>
        ) : null}
        {props.children ?? null}
      </div>
    </section>
  );
}

/** Controls beside readouts. */
export function Lab(props: { children?: Child }): Child {
  return <div class="lab">{props.children}</div>;
}

/** A bordered region with a mono heading. */
export function Panel(props: { head?: Child; kind?: "controls" | "readouts" | "plain"; children?: Child }): Child {
  return (
    <div class={`panel panel-${props.kind ?? "plain"}`}>
      {props.head ? <p class="panel-head">{props.head}</p> : null}
      {props.children ?? null}
    </div>
  );
}

/** A chart or canvas with its caption. */
export function Figure(props: { caption: Child; children?: Child }): Child {
  return (
    <figure class="fig">
      {props.children}
      <figcaption class="figcap">{props.caption}</figcaption>
    </figure>
  );
}

export function ActionRow(props: { children?: Child }): Child {
  return <div class="btnrow">{props.children}</div>;
}

export function Action(props: { kind?: ActionKind; onClick: () => void; children?: Child }): Child {
  return <button class={`act act-${props.kind ?? "default"}`} onClick={props.onClick}>{props.children}</button>;
}

/** One label/value line in a readouts panel. */
export function Stat(props: { what: Child; sub?: Child; value: () => string; tone?: () => Tone; cite?: string | string[] }): Child {
  return (
    <div class="stat-row">
      <span class="what">{props.what}{props.cite ? <Cite ids={props.cite} /> : null}{props.sub ? <small>{props.sub}</small> : null}</span>
      <span class={() => `val val-${props.tone ? props.tone() : "plain"}`}>{props.value}</span>
    </div>
  );
}

/** The model's own sentence about the current state. */
export function Explain(props: { children?: Child }): Child {
  return <p class="explain">{props.children}</p>;
}

export function Note(props: { children?: Child }): Child {
  return <p class="note">{props.children}</p>;
}

export function Slider(props: { p: ParamSignal }): Child {
  const p = props.p;
  // For commit-on-release knobs, a local signal tracks the thumb + readout live during a drag while the model value (which may trigger an expensive recompute) is committed only on release.
  const [disp, setDisp] = createSignal(p.get());
  if (p.commitOnRelease) createEffect(() => setDisp(p.get()));
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

/** An inline citation marker: a superscript [n] (the source's stable bibliography number) that reveals the full reference, its link, and what it grounds on hover or keyboard focus. */
export function Cite(props: { ids: string | string[] }): Child {
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
