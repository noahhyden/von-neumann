/** Design tokens, single-sourced; build.mjs injects BASE_CSS at the __DESIGN_TOKENS__ placeholder. */
export const BASE_CSS = `:root {
  --ground: #12140f; --surface: #1b1e18; --line: #2c302a; --ink: #e5e4db; --granite: #9a988c;
  --laurel: #7fae8f; --ocean: #7fa0b6; --falu: #d67a72; --tile: #8595a0;
  --metal: #c79a5b;
  --text: var(--ink);
  --muted: var(--granite);
  --panel: var(--surface);
  --chip: var(--ocean);
  --good: var(--laurel);
  --bad: var(--falu);
  --serif: 'Spectral', Georgia, 'Times New Roman', serif;
  --sans: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --fs-micro: 0.68rem; --fs-tiny: 0.72rem; --fs-small: 0.82rem;
  --fs-body: 0.97rem; --fs-lede: 1.08rem;
  --fs-h2: clamp(1.25rem, 1rem + 1.2vw, 1.6rem); --fs-h1: clamp(1.8rem, 1.1rem + 3vw, 2.9rem);
  --lh-tight: 1.12; --lh-body: 1.62; --lh-mono: 1.55;
  --track-eyebrow: 0.08em;
  --sp-1: 6px; --sp-2: 12px; --sp-3: 20px; --sp-4: 28px; --sp-5: 52px; --sp-6: 80px;
  --radius: 2px; --radius-lg: 3px;
  --measure: 70ch; --wrap: 1080px;
}`;
