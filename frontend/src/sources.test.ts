/**
 * Layer A (pimas-free) tests for the project bibliography. The bibliography is public-
 * facing research provenance, so these assert on its integrity, not just that it loads:
 * ids are unique, every entry is complete, every URL is real or explicitly null, the
 * citation numbering is stable, and the load-bearing sources are present.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  SOURCES,
  sourceById,
  sourceNumber,
  sourceCategories,
  STRENGTH_LABEL,
  type SourceStrength,
} from "./sources.ts";

const KNOWN_MODULES = new Set([
  "closure-sim",
  "probe-sim",
  "power-budget",
  "launch-economics",
  "mission",
  "multi-probe",
  "swarm",
  "spine",
  "frontend",
]);
const KNOWN_STRENGTHS: SourceStrength[] = ["primary", "reference", "grey", "vendor", "wiki"];

test("every source id is unique", () => {
  const ids = SOURCES.map((s) => s.id);
  assert.equal(new Set(ids).size, ids.length, "duplicate source id");
});

test("every source is complete (no empty required fields)", () => {
  for (const s of SOURCES) {
    for (const [k, v] of Object.entries({
      id: s.id,
      short: s.short,
      authors: s.authors,
      year: s.year,
      title: s.title,
      venue: s.venue,
      category: s.category,
      grounds: s.grounds,
    })) {
      assert.ok(typeof v === "string" && v.trim().length > 0, `${s.id}: empty ${k}`);
    }
    assert.ok(s.modules.length > 0, `${s.id}: cites no module`);
    for (const m of s.modules) assert.ok(KNOWN_MODULES.has(m), `${s.id}: unknown module ${m}`);
    assert.ok(KNOWN_STRENGTHS.includes(s.strength), `${s.id}: bad strength ${s.strength}`);
  }
});

test("every URL is either null or a real http(s) link (no fabricated/relative links)", () => {
  for (const s of SOURCES) {
    if (s.url === null) continue;
    assert.match(s.url, /^https?:\/\/\S+$/, `${s.id}: malformed url ${s.url}`);
  }
});

test("arXiv links and titles reference a consistent arXiv id", () => {
  // A title may name its arXiv id, e.g. "(arXiv:2005.12303)"; when it does and the url
  // is an arxiv.org/abs link, the two must match. This catches the class of error where
  // a real link is pasted under the wrong paper's title/authors (as happened with the
  // 2105.02082 entry, which had a valid link under the wrong "Chasing Carbon" title).
  const idIn = (s: string) => s.match(/arxiv[.:/]+(?:abs\/)?(\d{4}\.\d{4,5})/i)?.[1];
  for (const s of SOURCES) {
    const titleId = idIn(s.title);
    const urlId = s.url ? idIn(s.url) : undefined;
    if (titleId && urlId) {
      assert.equal(titleId, urlId, `${s.id}: title arXiv id ${titleId} != url arXiv id ${urlId}`);
    }
  }
});

// Provenance verified by hand against the primary source (2026-07-07): each entry pins
// the author surname and a distinctive title token confirmed at the cited work. A unit
// test cannot reach the live web, so this locks what a human already checked - a later
// careless edit that reintroduces a wrong attribution (as had happened with 2110.15198
// = Shubov, and 2105.02082 = Pirson & Bol) fails here instead of shipping green. Extend
// this table only after re-verifying the entry against its actual source.
const VERIFIED: Record<string, { author: string; titleToken: string }> = {
  "guided-self-replicating-factory-2021": { author: "Shubov", titleToken: "Colonization of Solar System" },
  "sensor-embodied-2021": { author: "Pirson", titleToken: "IoT edge devices" },
  "nagapurkar-das-2022": { author: "Nagapurkar", titleToken: "integrated circuit manufacturing" },
  "power-electronics-lca": { author: "Spejo", titleToken: "Silicon Carbide MOSFET" },
  "williams-ayres-heller-2002": { author: "Williams", titleToken: "1.7 Kilogram Microchip" },
  "borgue-hein-2020": { author: "Borgue", titleToken: "Near-Term Self-replicating Probes" },
  "nicholson-forgan-2013": { author: "Nicholson", titleToken: "Slingshot Dynamics" },
  "landauer-1961": { author: "Landauer", titleToken: "Irreversibility" },
};

test("hand-verified provenance is locked (author + title token match the cited source)", () => {
  for (const [id, exp] of Object.entries(VERIFIED)) {
    const s = sourceById(id);
    assert.ok(s, `verified source ${id} is missing`);
    assert.ok(
      s!.authors.includes(exp.author),
      `${id}: authors "${s!.authors}" lost the verified surname ${exp.author}`,
    );
    assert.ok(
      s!.title.includes(exp.titleToken),
      `${id}: title "${s!.title}" lost the verified token "${exp.titleToken}"`,
    );
  }
});

test("no em-dash or emoji leaks into the public bibliography text", () => {
  // The repo-wide typography rule (CLAUDE.md 5) applies to this user-facing data too.
  const emdash = /—/;
  const emoji = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{26FF}\u{2705}\u{2714}\u{2717}\u{274C}]/u;
  for (const s of SOURCES) {
    const blob = `${s.short} ${s.authors} ${s.title} ${s.venue} ${s.grounds}`;
    assert.ok(!emdash.test(blob), `${s.id}: contains an em-dash`);
    assert.ok(!emoji.test(blob), `${s.id}: contains an emoji`);
  }
});

test("citation numbers are the 1-based position, stable and invertible", () => {
  SOURCES.forEach((s, i) => {
    assert.equal(sourceNumber(s.id), i + 1, `${s.id}: wrong number`);
    assert.equal(sourceById(s.id), s, `${s.id}: lookup mismatch`);
  });
});

test("unknown ids fail closed (undefined / 0), never throw", () => {
  assert.equal(sourceById("not-a-real-source"), undefined);
  assert.equal(sourceNumber("not-a-real-source"), 0);
});

test("sourceCategories lists each category once, in first-appearance order", () => {
  const cats = sourceCategories();
  assert.equal(new Set(cats).size, cats.length, "a category is repeated");
  // Every source's category must be in the returned list.
  for (const s of SOURCES) assert.ok(cats.includes(s.category), `${s.category} missing`);
  // Order must match first appearance in SOURCES.
  const firstSeen: string[] = [];
  for (const s of SOURCES) if (!firstSeen.includes(s.category)) firstSeen.push(s.category);
  assert.deepEqual(cats, firstSeen);
});

test("STRENGTH_LABEL covers every strength tier", () => {
  for (const k of KNOWN_STRENGTHS) assert.ok(STRENGTH_LABEL[k]?.length > 0, `no label for ${k}`);
});

test("the load-bearing sources are present (guards against accidental deletion)", () => {
  const must = [
    "nasa-cp-2255-1980",
    "borgue-hein-2020",
    "kopp-lean-2011",
    "landauer-1961",
    "raichle-gusnard-2002",
    "nicholson-forgan-2013",
    "ferrell-1965",
    "rfc-4838",
  ];
  for (const id of must) assert.ok(sourceById(id), `missing load-bearing source ${id}`);
  // The whole point is a broad bibliography; a sudden shrink is a bug.
  assert.ok(SOURCES.length >= 25, `only ${SOURCES.length} sources, expected >= 25`);
});
