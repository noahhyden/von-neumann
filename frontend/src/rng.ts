// mulberry32, threaded (never ambient) - mirrors vn_core.rng (pinned by core/tests/test_rng.py)
export function nextFloat(state: number): [number, number] {
  const s = (state + 0x6d2b79f5) | 0;
  let t = Math.imul(s ^ (s >>> 15), 1 | s);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return [((t ^ (t >>> 14)) >>> 0) / 4294967296, s | 0];
}
