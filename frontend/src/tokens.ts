/** Computed value of a `:root` custom property (name without dashes), cached; "" without a document. */
const cache = new Map<string, string>();

export function token(name: string): string {
  const hit = cache.get(name);
  if (hit !== undefined) return hit;
  if (typeof document === "undefined") return "";
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
  if (v) cache.set(name, v);
  return v;
}
