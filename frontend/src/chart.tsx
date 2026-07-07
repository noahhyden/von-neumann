/**
 * The growth chart - driven by the REAL model output (sim().steps), not a faked
 * curve. Plots output (kg/day) against years, with the target line and the day
 * each curve crosses it. When a speculation is active, the hypothetical "chips
 * local" trajectory is overlaid (bronze, dashed) beside the committed one (teal) -
 * a before/after you can see, computed without committing.
 */
import { createMemo } from "pimas";
import type { Accessor } from "pimas";
import type { SimResult } from "./model.js";
import type { WallModel } from "./reactive-model.js";

const W = 900, H = 380, PADL = 58, PADR = 116, PADT = 22, PADB = 44;

interface Geo {
  committed: string;
  preview: string | null;
  ymax: number;
  xmaxYr: number;
  targetY: number;
  tttCommittedX: number | null;
  tttPreviewX: number | null;
  yTicks: { y: number; label: string }[];
  xTicks: { x: number; label: string }[];
  endCommitted: { x: number; y: number };
  endPreview: { x: number; y: number } | null;
}

function polyline(steps: SimResult["steps"], X: (yr: number) => number, Y: (v: number) => number): string {
  const n = steps.length;
  const stride = Math.max(1, Math.floor(n / 220));
  const pts: string[] = [];
  for (let i = 0; i < n; i += stride) {
    const s = steps[i];
    pts.push(`${X(s.day / 365).toFixed(1)},${Y(s.output_kg_per_day).toFixed(1)}`);
  }
  const last = steps[n - 1];
  pts.push(`${X(last.day / 365).toFixed(1)},${Y(last.output_kg_per_day).toFixed(1)}`);
  return pts.join(" ");
}

function geometry(committed: SimResult, previewAfter: SimResult | null, target: number): Geo {
  const xmaxYr = committed.steps[committed.steps.length - 1].day / 365;
  const peak = (r: SimResult) => r.steps.reduce((m, s) => Math.max(m, s.output_kg_per_day), 0);
  const ymaxRaw = Math.max(target * 1.25, peak(committed), previewAfter ? peak(previewAfter) : 0);
  // round up to a nice number
  const pow = Math.pow(10, Math.floor(Math.log10(ymaxRaw)));
  const ymax = Math.ceil(ymaxRaw / pow) * pow;

  const X = (yr: number) => PADL + (yr / xmaxYr) * (W - PADL - PADR);
  const Y = (v: number) => PADT + (H - PADT - PADB) * (1 - Math.min(v, ymax) / ymax);

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
    y: Y(ymax * f),
    label: (ymax * f).toLocaleString(undefined, { maximumFractionDigits: 0 }),
  }));
  const xStep = xmaxYr <= 20 ? 5 : 10;
  const xTicks: { x: number; label: string }[] = [];
  for (let yr = 0; yr <= xmaxYr + 0.01; yr += xStep) xTicks.push({ x: X(yr), label: String(yr) });

  const endC = committed.steps[committed.steps.length - 1];
  const endP = previewAfter ? previewAfter.steps[previewAfter.steps.length - 1] : null;

  return {
    committed: polyline(committed.steps, X, Y),
    preview: previewAfter ? polyline(previewAfter.steps, X, Y) : null,
    ymax,
    xmaxYr,
    targetY: Y(target),
    tttCommittedX: committed.time_to_target_days !== null ? X(committed.time_to_target_days / 365) : null,
    tttPreviewX: previewAfter && previewAfter.time_to_target_days !== null ? X(previewAfter.time_to_target_days / 365) : null,
    yTicks,
    xTicks,
    endCommitted: { x: X(endC.day / 365), y: Y(endC.output_kg_per_day) },
    endPreview: endP ? { x: X(endP.day / 365), y: Y(endP.output_kg_per_day) } : null,
  };
}

export function GrowthChart(props: {
  model: WallModel;
  preview: Accessor<{ before: SimResult; after: SimResult } | null>;
}) {
  const geo = createMemo<Geo>(() => geometry(props.model.sim(), props.preview()?.after ?? null, props.model.params.target.get()));

  const content = () => {
    const g = geo();
    const els: unknown[] = [];
    // horizontal grid
    for (const t of g.yTicks) {
      els.push(<line x1={PADL} y1={t.y} x2={W - PADR} y2={t.y} stroke="rgba(232,226,214,0.08)" stroke-width="1" />);
      els.push(<text x={PADL - 8} y={t.y + 4} text-anchor="end" fill="var(--muted)" style="font:11px var(--mono)">{t.label}</text>);
    }
    for (const t of g.xTicks) {
      els.push(<text x={t.x} y={H - PADB + 20} text-anchor="middle" fill="var(--muted)" style="font:11px var(--mono)">{t.label}</text>);
    }
    els.push(<text x={PADL} y={PADT - 8} fill="var(--muted)" style="font:11px var(--mono)">OUTPUT kg/day</text>);
    els.push(<text x={(PADL + W - PADR) / 2} y={H - 8} text-anchor="middle" fill="var(--muted)" style="font:11px var(--mono)">YEARS →</text>);

    // target line
    els.push(<line x1={PADL} y1={g.targetY} x2={W - PADR} y2={g.targetY} stroke="var(--muted)" stroke-width="1" stroke-dasharray="5 5" />);
    els.push(<text x={W - PADR + 6} y={g.targetY + 4} fill="var(--muted)" style="font:11px var(--mono)">goal</text>);

    // time-to-target markers
    if (g.tttPreviewX !== null) els.push(<line x1={g.tttPreviewX} y1={PADT} x2={g.tttPreviewX} y2={H - PADB} stroke="rgba(199,154,91,0.45)" stroke-width="1" stroke-dasharray="3 3" />);
    if (g.tttCommittedX !== null) els.push(<line x1={g.tttCommittedX} y1={PADT} x2={g.tttCommittedX} y2={H - PADB} stroke="rgba(127,169,181,0.55)" stroke-width="1" stroke-dasharray="3 3" />);

    // preview curve (bronze dashed) under committed
    if (g.preview) {
      els.push(<polyline points={g.preview} fill="none" stroke="var(--metal)" stroke-width="2.5" stroke-dasharray="7 5" stroke-linejoin="round" />);
      if (g.endPreview) els.push(<text x={g.endPreview.x - 6} y={g.endPreview.y - 8} text-anchor="end" fill="var(--metal)" style="font:11px var(--mono)">chips local</text>);
    }
    // committed curve (teal solid)
    els.push(<polyline points={g.committed} fill="none" stroke="var(--chip)" stroke-width="2.5" stroke-linejoin="round" />);
    if (g.endCommitted) els.push(<text x={g.endCommitted.x - 6} y={g.endCommitted.y + 16} text-anchor="end" fill="var(--chip)" style="font:11px var(--mono)">as built</text>);

    return els;
  };

  return (
    <svg class="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Factory output over time, from the live model">
      {content}
    </svg>
  );
}
