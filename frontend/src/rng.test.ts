/** Layer A test pinning rng.ts nextFloat to the committed Python/JS parity fixture. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { nextFloat } from "./rng.ts";

const FIXTURE = new URL("../../modules/core/tests/rng_js_fixture/fixture.json", import.meta.url);

test("nextFloat reproduces the fixture float stream for every seed", () => {
  const seeds = Object.entries(JSON.parse(readFileSync(FIXTURE, "utf8")).seeds) as [string, { float: number[] }][];
  assert.ok(seeds.length > 0, "fixture has no seeds");
  let draws = 0;
  for (const [key, rec] of seeds) {
    assert.ok(rec.float.length > 0, `seed ${key} has no draws`);
    let state = Number(key) | 0; // unsigned key -> signed state, as gen.mjs does
    rec.float.forEach((want, i) => {
      const [got, next] = nextFloat(state);
      assert.equal(got, want, `seed ${key} draw ${i}`);
      state = next;
      draws++;
    });
  }
  console.log(`rng parity: ${seeds.length} seeds, ${draws} draws`);
});
