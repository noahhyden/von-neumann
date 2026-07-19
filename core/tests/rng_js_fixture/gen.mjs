// Regenerate the mulberry32 parity fixture consumed by tests/test_rng_js_parity.py.
//
// The JS side is the algorithmic reference: mulberry32 was written in JS first and
// mirrored into Python (see swarm/src/swarm/rng.py, multi_probe/src/multi_probe/rng.py,
// and the three copies under frontend/). This script produces the u32 and float streams
// the JS mulberry32 emits for a handful of seeds; the Python test asserts vn_core.rng
// reproduces them bit-for-bit. If the fixture ever needs to change, run:
//
//   node core/tests/rng_js_fixture/gen.mjs > core/tests/rng_js_fixture/fixture.json
//
// The `nextFloat` body below is a verbatim copy of the mulberry32 in frontend/src/swarm.ts
// and frontend/src/multi-probe.ts (both are identical). Keeping this copy self-contained
// means the fixture generator has no import surface - it always agrees with itself, and
// any drift between it and a frontend file is caught by the parity test.

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
  // JS numbers are signed 32-bit under `| 0`, so seed_state(0xffffffff) is -1 in JS.
  // We store the seed as its unsigned 32-bit key so Python's positive int matches directly.
  out.seeds[(seed >>> 0).toString()] = { u32: u32s, float: floats };
}
process.stdout.write(JSON.stringify(out, null, 2) + "\n");
