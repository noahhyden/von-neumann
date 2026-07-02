/**
 * Layer B — the pimas framework canary.
 *
 * This file imports ONLY pimas primitives — nothing from closure-sim's model.
 * It asserts the exact contracts the frontend leans on (see reactive-model.ts):
 * fine-grained memo tracking, untrack, `speculate` free rollback, store writes +
 * `onStoreWrite` provenance, and the agent bridge (descriptor / speculate / call /
 * explain). Blame attribution: if Layer A (`npm test`, pure model, no pimas) is
 * green and our tree is unchanged but THIS fails, the regression is in pimas, not
 * in us — flag it in the pimas repo, don't work around it here.
 *
 * Run: node --test src/pimas-contract.test.ts   (needs pimas built: dist is gitignored)
 */
import test from "node:test";
import assert from "node:assert/strict";

import { createSignal, createMemo, speculate, untrack } from "pimas";
import { createStore, onStoreWrite } from "pimas/store";
import { createAgentBridge } from "pimas/agent";

test("createMemo recomputes iff a tracked dependency changes", () => {
  let runs = 0;
  const [a, setA] = createSignal(1);
  const [b, setB] = createSignal(10);
  const derived = createMemo(() => {
    runs++;
    return a() + 1; // depends on `a` only
  });

  assert.equal(derived(), 2);
  const base = runs;

  setB(20); // not a dependency
  assert.equal(derived(), 2);
  assert.equal(runs, base, "changing an untracked signal must not recompute the memo");

  setA(5); // a dependency
  assert.equal(derived(), 6);
  assert.equal(runs, base + 1, "changing a tracked signal must recompute the memo");
});

test("untrack reads a signal without subscribing to it", () => {
  const [x, setX] = createSignal(1);
  const [y, setY] = createSignal(1);
  const m = createMemo(() => x() + untrack(() => y()));

  assert.equal(m(), 2);
  setY(100);
  assert.equal(m(), 2, "y was read via untrack, so it must not be a dependency");
  setX(5);
  assert.equal(m(), 105, "on the next real recompute the memo sees the latest y");
});

test("speculate returns the after-state and rolls the real graph back", () => {
  const [store, setStore] = createStore({ v: 1 });
  const read = createMemo(() => store.v * 10);
  assert.equal(read(), 10);

  const after = speculate(
    () => setStore("v", 5),
    () => read(),
  );

  assert.equal(after, 50, "read() inside speculate reflects the applied mutation");
  assert.equal(store.v, 1, "the real store must be untouched after speculate returns");
  assert.equal(read(), 10, "the live memo must be unchanged (free rollback)");
});

test("createStore + onStoreWrite report the written field path", () => {
  const [store, setStore] = createStore({
    subsystems: [{ local: false }, { local: false }],
    power: 100,
  });
  const paths: string[] = [];
  const unsub = onStoreWrite((e) => paths.push(e.path.join(".")));

  setStore("subsystems", 0, "local", true);
  assert.equal(store.subsystems[0].local, true, "nested store write applied");
  assert.equal(paths[0], "subsystems.0.local", "onStoreWrite reports the exact path");

  unsub();
  setStore("power", 200);
  assert.equal(paths.length, 1, "unsubscribe stops further write events");
});

test("createAgentBridge: descriptor / speculate (no commit) / call + explain", () => {
  const [store, setStore] = createStore({ factory: { chipsLocal: false, powerKw: 100 } });

  const bridge = createAgentBridge(
    (r) => {
      r.expose("chips_local", () => store.factory.chipsLocal, { description: "chips built locally" });
      r.expose("power_kw", () => store.factory.powerKw);
      r.action("makeLocal", () => setStore("factory", "chipsLocal", true), {
        params: [],
        description: "toggle chips to locally producible",
      });
    },
    { writeTap: (record) => onStoreWrite((e) => record(e.path.join("."))) },
  );

  // The wire contract an agent reads.
  const d = bridge.descriptor();
  assert.ok(d.state.chips_local, "descriptor exposes named state");
  assert.ok(d.actions.makeLocal, "descriptor exposes named actions");

  // L3: speculate predicts the after-state WITHOUT committing.
  const pred = bridge.speculate("makeLocal");
  assert.equal(pred.chips_local, true, "speculate returns the predicted after-state");
  assert.equal(store.factory.chipsLocal, false, "speculate must not commit");
  assert.equal(bridge.snapshot().state.chips_local, false, "live snapshot unchanged after speculate");

  // Commit for real, then L2 explain records the causal chain.
  bridge.call("makeLocal");
  assert.equal(store.factory.chipsLocal, true, "call commits the action");
  const cause = bridge.explain();
  assert.ok(cause, "explain() returns a record after a call");
  assert.equal(cause!.action, "makeLocal");
  assert.ok(cause!.writes.some((w) => w.includes("chipsLocal")), "explain names the field writes");
  assert.ok(cause!.changed.includes("chips_local"), "explain names the changed exposed outputs");

  bridge.dispose();
});
