/** Layer A tests for the design-token reader. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { token } from "./tokens.ts";

test("without a document, token returns an empty string rather than throwing", () => {
  assert.equal(typeof document, "undefined");
  assert.equal(token("metal"), "");
});

test("token caches: getComputedStyle runs once per name", () => {
  let calls = 0;
  const g = globalThis as Record<string, unknown>;
  g.document = { documentElement: {} };
  g.getComputedStyle = () => (calls++, { getPropertyValue: (n: string) => (n === "--cached-x" ? "  #abc  " : "") });
  try {
    assert.equal(token("cached-x"), "#abc");
    assert.equal(token("cached-x"), "#abc");
    assert.equal(calls, 1);
  } finally {
    delete g.document;
    delete g.getComputedStyle;
  }
});
