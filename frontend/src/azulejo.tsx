/** Pattern definitions; render once per document. */
export function AzulejoDefs() {
  return (
    <svg width="0" height="0" style="position:absolute;" aria-hidden="true">
      <defs>
        <pattern id="rosette" width="48" height="48" patternUnits="userSpaceOnUse">
          <g fill="none" stroke="var(--ocean)" stroke-width="1">
            <circle cx="0" cy="0" r="24" />
            <circle cx="48" cy="0" r="24" />
            <circle cx="0" cy="48" r="24" />
            <circle cx="48" cy="48" r="24" />
            <circle cx="24" cy="24" r="24" />
            <circle cx="24" cy="0" r="24" />
            <circle cx="24" cy="48" r="24" />
            <circle cx="0" cy="24" r="24" />
            <circle cx="48" cy="24" r="24" />
          </g>
        </pattern>
        <pattern id="quatrefoil" width="48" height="48" patternUnits="userSpaceOnUse">
          <g fill="none" stroke="var(--ocean)" stroke-width="1.15">
            <circle cx="24" cy="11" r="13" />
            <circle cx="37" cy="24" r="13" />
            <circle cx="24" cy="37" r="13" />
            <circle cx="11" cy="24" r="13" />
            <circle cx="0" cy="0" r="13" />
            <circle cx="48" cy="0" r="13" />
            <circle cx="0" cy="48" r="13" />
            <circle cx="48" cy="48" r="13" />
            <circle cx="24" cy="24" r="4.5" />
            <rect x="14.7" y="14.7" width="18.6" height="18.6" transform="rotate(45 24 24)" />
          </g>
        </pattern>
      </defs>
    </svg>
  );
}


/** Tracery opacity for the page field; the one place to retune. */
export const FIELD_OPACITY = 0.16;

/** One tile-able period of the mask: opaque OUTSIDE a sine corridor (centre 50 +/-9, half-width 41), blurred; shapes run past the tile so the seam is invisible. */
function corridorMask(): string {
  const edge = (y: number, s: number) => 50 - 9 * Math.sin((y / 100) * 2 * Math.PI) + s * 41;
  const ys: number[] = [];
  for (let y = -40; y <= 140; y += 4) ys.push(y);
  const side = (s: number, far: number) => [...ys.map((y) => `${edge(y, s).toFixed(2)},${y}`), `${far},140`, `${far},-40`].join(" ");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="none"><filter id="b" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5 2"/></filter><g filter="url(#b)" fill="#000"><polygon points="${side(-1, -60)}"/><polygon points="${side(1, 160)}"/></g></svg>`;
  return `url(data:image/svg+xml,${encodeURIComponent(svg).replace(/[()']/g, (c) => "%" + c.charCodeAt(0).toString(16))})`;
}

const CORRIDOR_MASK = corridorMask();

/** Page-wide tracery field: ONE document-height element (one 48px grid); the mask tiles one corridor wave per viewport height. */
export function AzulejoField(props: { pattern?: "quatrefoil" | "rosette"; opacity?: number; corridor?: boolean }) {
  const o = props.opacity ?? FIELD_OPACITY;
  const m = (props.corridor ?? true) ? `-webkit-mask-image:${CORRIDOR_MASK}; mask-image:${CORRIDOR_MASK}; -webkit-mask-size:100% 100vh; mask-size:100% 100vh; -webkit-mask-repeat:repeat-y; mask-repeat:repeat-y;` : "";
  return (
    <svg width="100%" height="100%" style={`position:absolute; inset:0; opacity:${o}; pointer-events:none; ${m}`} aria-hidden="true">
      <rect width="100%" height="100%" fill={`url(#${props.pattern ?? "quatrefoil"})`} />
    </svg>
  );
}
