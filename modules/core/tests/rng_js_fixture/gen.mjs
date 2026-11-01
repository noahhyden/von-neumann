// Regenerate the mulberry32 parity fixture for tests/test_rng_js_parity.py (see core README).

function nextU32(state) {
  const s = (state + 0x6d2b79f5) | 0;
  let t = Math.imul(s ^ (s >>> 15), 1 | s);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return [(t ^ (t >>> 14)) >>> 0, s | 0];
}

const SEEDS = [0, 1, 42, 0x80000000, 0xffffffff];
const N = 32;
const out = { seeds: {} };
for (const seed of SEEDS) {
  let state = seed | 0;
  const u32s = [];
  const floats = [];
  for (let i = 0; i < N; i++) {
    const [v, ns] = nextU32(state);
    u32s.push(v);
    floats.push(v / 4294967296);
    state = ns;
  }
  // Store the seed as its unsigned 32-bit key, so Python's positive int matches JS's signed `| 0`.
  out.seeds[(seed >>> 0).toString()] = { u32: u32s, float: floats };
}
process.stdout.write(JSON.stringify(out, null, 2) + "\n");
