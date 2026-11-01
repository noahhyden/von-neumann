/** Shared marks, ported from noahhyden.com so the two sites carry the same identity. */

export function GitHubIcon(props: { size?: number } = {}) {
  const s = props.size ?? 19;
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.48 2 2 6.58 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49 0-.24-.01-.88-.01-1.73-2.78.62-3.37-1.37-3.37-1.37-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.62.07-.62 1 .07 1.53 1.06 1.53 1.06.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.55-1.14-4.55-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.28 2.75 1.05A9.36 9.36 0 0 1 12 6.84c.85 0 1.71.12 2.51.34 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.79-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.48-.01 2.82 0 .27.18.6.69.49A10.26 10.26 0 0 0 22 12.25C22 6.58 17.52 2 12 2Z" />
    </svg>
  );
}

export function LinkedInIcon(props: { size?: number } = {}) {
  const s = props.size ?? 19;
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="currentColor">
      <path d="M4.98 3.5C4.98 4.88 3.87 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1s2.48 1.12 2.48 2.5zM.2 8.04h4.6V23H.2V8.04zM8.34 8.04h4.41v2.04h.06c.61-1.16 2.11-2.39 4.35-2.39 4.65 0 5.51 3.06 5.51 7.05V23h-4.6v-6.36c0-1.52-.03-3.47-2.11-3.47-2.12 0-2.44 1.65-2.44 3.36V23h-4.6V8.04z" />
    </svg>
  );
}

/** The site mark: azulejo quatrefoil, heavier strokes than the artwork so it reads at 24px. */
/** The site mark: azulejo quatrefoil, heavier strokes than the artwork so it reads at 24px. */
export function Mark(props: { size?: number } = {}) {
  const s = props.size ?? 34;
  return (
    <svg width={s} height={s} viewBox="0 0 100 100" fill="none" aria-hidden="true">
      <circle cx="50" cy="50" r="48.4" stroke="var(--ocean)" stroke-width="0.9" />
      <circle cx="50" cy="50" r="45.6" stroke="var(--ocean)" stroke-width="2.6" />
      <g stroke="var(--laurel)" stroke-width="2.2">
        <circle cx="50" cy="31.2" r="17.6" />
        <circle cx="50" cy="68.8" r="17.6" />
        <circle cx="31.2" cy="50" r="17.6" />
        <circle cx="68.8" cy="50" r="17.6" />
        <path d="M50 31.2 L68.8 50 L50 68.8 L31.2 50 Z" />
      </g>
      <circle cx="50" cy="50" r="3.2" fill="var(--falu)" />
    </svg>
  );
}
