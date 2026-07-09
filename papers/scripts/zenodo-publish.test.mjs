// Validation tests for the pure (network-free) core of zenodo-publish.mjs (issue #8).
// The API-driving phases need a live Zenodo token and are exercised by a real sandbox
// run; what we CAN assert here is that the metadata we would send is well-formed and
// faithfully mirrors paper.json - the part most likely to silently drift. Run with:
//   node --test papers/scripts/zenodo-publish.test.mjs
//
// ASCII only, no em-dash (CLAUDE.md 5).

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { toFamilyGiven, buildMetadata } from "./zenodo-publish.mjs";

test("toFamilyGiven reorders to 'Family, Given', preserves accents, passes single tokens", () => {
  assert.equal(toFamilyGiven("Noah Hyden"), "Hyden, Noah");
  assert.equal(toFamilyGiven("Noah Hydén"), "Hydén, Noah"); // accent preserved
  assert.equal(toFamilyGiven("Ada Byron King"), "King, Ada Byron");
  assert.equal(toFamilyGiven("Cher"), "Cher"); // single token, unchanged
  assert.equal(toFamilyGiven("  Grace   Hopper  "), "Hopper, Grace"); // whitespace collapsed
});

test("buildMetadata mirrors paper.json and sets a valid Zenodo shape", () => {
  const paper = {
    title: "A Test Paper",
    abstract: "An abstract.",
    keywords: ["a", "b"],
    authors: [{ name: "Noah Hyden", orcid: "0009-0003-4523-0467", affiliation: "Independent researcher" }],
  };
  const m = buildMetadata(paper);
  assert.equal(m.upload_type, "publication");
  assert.equal(m.publication_type, "article");
  assert.equal(m.title, "A Test Paper");
  assert.equal(m.description, "An abstract.");
  assert.deepEqual(m.keywords, ["a", "b"]);
  assert.equal(m.access_right, "open");
  assert.equal(m.license, "cc-by-nc-nd-4.0"); // repo research-prose license when paper.license unset
  assert.equal(m.prereserve_doi, true);
  // creator faithfully carries the reordered name, bare ORCID, affiliation.
  assert.deepEqual(m.creators, [
    { name: "Hyden, Noah", orcid: "0009-0003-4523-0467", affiliation: "Independent researcher" },
  ]);
  // relates to the whole-repo software DOI and the code, not standing alone.
  const rels = m.related_identifiers.map((r) => `${r.relation}:${r.identifier}`);
  assert.ok(rels.includes("isPartOf:10.5281/zenodo.21249296"), "must relate to the repo concept DOI");
  assert.ok(rels.some((r) => r.startsWith("isSupplementTo:https://github.com/")), "must link the code repo");
});

test("buildMetadata strips an ORCID URL prefix to the bare id", () => {
  const m = buildMetadata({ authors: [{ name: "A B", orcid: "https://orcid.org/0000-0002-1825-0097" }] });
  assert.equal(m.creators[0].orcid, "0000-0002-1825-0097");
});

test("paper.license overrides the sandbox default", () => {
  const m = buildMetadata({ authors: [], license: "MIT" });
  assert.equal(m.license, "MIT");
});

test("real paper.json files build valid metadata (no empty title/description)", () => {
  const papersRoot = fileURLToPath(new URL("..", import.meta.url));
  for (const slug of ["coordination-tax", "electronics-wall"]) {
    const paper = JSON.parse(readFileSync(join(papersRoot, slug, "paper.json"), "utf8"));
    const m = buildMetadata(paper);
    assert.ok(m.title && m.title.length > 0, `${slug}: empty title`);
    assert.ok(m.description && m.description.length > 0, `${slug}: empty description`);
    assert.ok(m.creators.length > 0 && m.creators.every((c) => c.name.includes(",")), `${slug}: creator not 'Family, Given'`);
    assert.ok(m.keywords.length > 0, `${slug}: no keywords`);
  }
});
