/** Base components every surface composes: one shell, one band, one panel, one figure. */
import { createSignal, createEffect } from "pimas";
import type { Child } from "pimas/dom";
import { For } from "pimas/flow";
import { sourceById, sourceNumber } from "./sources.js";
import type { Source } from "./sources.js";
import { AzulejoDefs, AzulejoField } from "./azulejo.js";
import { Footer } from "./chrome.js";
import type { ParamSignal } from "./reactive-model.js";

const fmtNum = (n: number, d = 0) => n.toLocaleString(undefined, { maximumFractionDigits: d });

export type Tone = "metal" | "chip" | "good" | "bad" | "plain";
export type ActionKind = "default" | "primary" | "commit" | "ghost";

/** The one page frame: title, optional lede and hero figure, bands, footer. */
export function PageShell(props: {
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
          <Scrim spread="lg" style="width:fit-content; max-width:100%; padding:var(--sp-4) var(--sp-6); margin:calc(-1 * var(--sp-4)) calc(-1 * var(--sp-6));">
            <h1>{props.title}</h1>
            {props.lede ? <p class="lede">{props.lede}</p> : null}
          </Scrim>
          {props.hero ?? null}
        </div>
      </section>
      {props.children ?? null}
      {props.footer ? <footer><div class="wrap"><p>{props.footer}</p></div></footer> : null}
    </div>
  );
}

/** One band of the page; its heading is a claim, never a label above a label. */
export function Band(props: { title?: Child; children?: Child }): Child {
  return (
    <section>
      <div class="wrap">
        {props.title ? (
          <Scrim spread="md" style="width:fit-content; max-width:100%; padding:var(--sp-3) var(--sp-5); margin:calc(-1 * var(--sp-3)) calc(-1 * var(--sp-5)) var(--sp-2);">
            <h2 style="margin:0;">{props.title}</h2>
          </Scrim>
        ) : null}
        {props.children ?? null}
      </div>
    </section>
  );
}

const SPREAD = { sm: "45%", md: "62%", lg: "80%" };

/** Radial ground halo so a block floats on the page tracery instead of punching a rectangular hole in it. */
export function Scrim(props: { spread?: "sm" | "md" | "lg"; style?: string; children?: Child }): Child {
  const stop = SPREAD[props.spread ?? "md"];
  return (
    <div style={`background:radial-gradient(ellipse at 50% 50%, var(--ground) 0%, var(--ground) ${stop}, transparent 100%);${props.style ?? ""}`}>
      {props.children}
    </div>
  );
}

/** One document-height tracery field behind everything; content rides above it on z-index 1. */
export function Shell(props: { children?: Child }): Child {
  return (
    <div style="position:relative;">
      <AzulejoDefs />
      <AzulejoField />
      <div style="position:relative; z-index:1;">{props.children}<Footer /></div>
    </div>
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

/** A native <details>/<summary> disclosure - no signal, no per-entity reactivity, just a collapsible region with an optional item count in its summary. */
export function Accordion(props: { title: Child; count?: (() => number) | number; open?: boolean; children?: Child }): Child {
  const count = props.count;
  return (
    <details class="accordion" open={props.open ?? false}>
      <summary class="accordion-summary panel-head">
        {props.title}
        {count != null ? <span class="accordion-count">{typeof count === "function" ? (() => ` (${count()})`) : ` (${count})`}</span> : null}
      </summary>
      <div class="accordion-body">{props.children}</div>
    </details>
  );
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
