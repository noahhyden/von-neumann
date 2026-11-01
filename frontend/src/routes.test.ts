/** Layer A tests for the pure path router: round-trip, unknown routes, the bare root, wall scenarios, and legacy-hash translation. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { VALID_SURFACES, SCENARIO_KEYS, DEFAULT_SCENARIO, pathForSurface, parsePath, isKnownPath, pathFromLegacyHash, allRoutePaths } from "./routes.ts";

test("bare root parses to the overview surface at the default scenario", () => {
  assert.deepEqual(parsePath("/"), { surface: "overview", scenarioKey: DEFAULT_SCENARIO });
  assert.equal(pathForSurface("overview", DEFAULT_SCENARIO), "/");
});

test("every surface round-trips through pathForSurface -> parsePath", () => {
  for (const surface of VALID_SURFACES) {
    const path = pathForSurface(surface, DEFAULT_SCENARIO);
    assert.deepEqual(parsePath(path), { surface, scenarioKey: DEFAULT_SCENARIO });
  }
});

test("a non-default wall scenario round-trips and the default scenario collapses to /wall", () => {
  assert.equal(pathForSurface("wall", "outpost"), "/wall/outpost");
  assert.deepEqual(parsePath("/wall/outpost"), { surface: "wall", scenarioKey: "outpost" });
  assert.equal(pathForSurface("wall", DEFAULT_SCENARIO), "/wall");
  assert.deepEqual(parsePath("/wall"), { surface: "wall", scenarioKey: DEFAULT_SCENARIO });
});

test("an unknown wall scenario in the path falls back to the default scenario", () => {
  assert.deepEqual(parsePath("/wall/not-a-real-scenario"), { surface: "wall", scenarioKey: DEFAULT_SCENARIO });
});

test("an unrecognized route falls back to the overview surface (the 404 case)", () => {
  assert.deepEqual(parsePath("/nonexistent"), { surface: "overview", scenarioKey: DEFAULT_SCENARIO });
  assert.equal(isKnownPath("/nonexistent"), false);
  assert.equal(isKnownPath("/sources"), true);
  assert.equal(isKnownPath("/"), true);
});

test("a trailing slash still resolves (a direct hit on a route directory)", () => {
  assert.deepEqual(parsePath("/sources/"), { surface: "sources", scenarioKey: DEFAULT_SCENARIO });
});

test("legacy #/<surface>[/<scenario>] hashes translate to the new path", () => {
  assert.equal(pathFromLegacyHash("#/swarm"), "/swarm");
  assert.equal(pathFromLegacyHash("#/wall/outpost"), "/wall/outpost");
  assert.equal(pathFromLegacyHash("#/"), "/");
  assert.equal(pathFromLegacyHash(""), null);
});

test("allRoutePaths covers every surface but overview, plus every scenario key", () => {
  const paths = allRoutePaths();
  for (const surface of VALID_SURFACES) {
    if (surface === "overview") continue;
    assert.ok(paths.includes(pathForSurface(surface, DEFAULT_SCENARIO)), `missing route for ${surface}`);
  }
  for (const key of SCENARIO_KEYS) assert.ok(paths.includes(`/wall/${key}`), `missing wall scenario route for ${key}`);
  assert.equal(paths.length, new Set(paths).size, "no duplicate routes");
});
