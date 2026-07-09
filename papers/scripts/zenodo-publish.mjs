// zenodo-publish.mjs - mint a per-paper Zenodo DOI from CI (issue #8).
//
// The repo already has ONE Zenodo concept DOI (10.5281/zenodo.21249296, recorded in
// CITATION.cff) minted by the repo-scoped GitHub->Zenodo auto-integration: it archives
// the whole monorepo on every Release and is a legitimate software citation we keep.
// But that integration cannot scope to a subdirectory, so every paper shares it. This
// script bypasses the auto-integration and drives Zenodo's REST API directly, ONE
// deposition per paper, so each paper is independently citable under its own concept
// DOI, with a fresh version DOI per version (the same "version = commit" spine as #7).
//
// It runs in two phases so the reserved DOI can be printed ON the PDF before upload:
//   reserve  - create the deposition (or a new version of an existing one), read back
//              the pre-reserved DOI, write it into papers/<slug>/doi.tex, and stash the
//              deposition id + upload bucket in a state file.
//   finalize - upload the (DOI-stamped) PDF + reproducibility zip, set the metadata
//              from paper.json, publish, and write the minted DOIs back into paper.json.
//
// Sandbox vs production is chosen by ZENODO_BASE (sandbox.zenodo.org/api by default).
// The concept-id state is namespaced per environment (zenodo_sandbox_* vs zenodo_*), so
// a sandbox run never pollutes the production identifiers and graduating is additive.
//
// API contract verified against https://developers.zenodo.org (endpoints, prereserve_
// doi.doi, links.bucket, actions/newversion -> links.latest_draft, actions/publish,
// conceptrecid/conceptdoi, Bearer auth with scopes deposit:write + deposit:actions).
//
// No numbers invented (CLAUDE.md 1): the only literal identifiers are the repo concept
// DOI and repo URL, both sourced from CITATION.cff.
//
// ASCII only, no em-dash (CLAUDE.md 5).

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

// Sourced from CITATION.cff (the whole-repo software citation the papers relate to).
const REPO_CONCEPT_DOI = "10.5281/zenodo.21249296";
const REPO_URL = "https://github.com/noahhyden/von-neumann";

const papersRoot = fileURLToPath(new URL("..", import.meta.url));

/** Parse `--key value` / `--flag` args into an object. */
function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith("--")) out[key] = true;
      else { out[key] = next; i++; }
    } else out._.push(a);
  }
  return out;
}

/** "Noah Hyden" -> "Hyden, Noah" (Zenodo prefers Family, Given). Single token as-is. */
export function toFamilyGiven(name) {
  const parts = String(name).trim().split(/\s+/);
  if (parts.length < 2) return String(name).trim();
  const family = parts[parts.length - 1];
  const given = parts.slice(0, -1).join(" ");
  return `${family}, ${given}`;
}

/**
 * Build the Zenodo deposition metadata from a paper.json object. Pure - no I/O, no
 * network - so it is unit-testable. The license defaults to the repo's documented
 * research-prose license, CC BY-NC-ND 4.0 (papers/README.md, LICENSE-DOCS); a paper
 * can override it with paper.license (an SPDX id).
 */
export function buildMetadata(paper, { license } = {}) {
  return {
    upload_type: "publication",
    publication_type: "article",
    title: paper.title,
    creators: (paper.authors || []).map((a) => {
      const c = { name: toFamilyGiven(a.name || "") };
      if (a.orcid) c.orcid = String(a.orcid).replace(/^https?:\/\/orcid\.org\//, "");
      if (a.affiliation) c.affiliation = a.affiliation;
      return c;
    }),
    description: paper.abstract || "",
    keywords: paper.keywords || [],
    access_right: "open",
    // CC BY-NC-ND 4.0 is the repo's research-prose license (papers/README.md).
    license: paper.license || license || "cc-by-nc-nd-4.0",
    related_identifiers: [
      { identifier: REPO_CONCEPT_DOI, relation: "isPartOf", resource_type: "software" },
      { identifier: REPO_URL, relation: "isSupplementTo", resource_type: "software" },
    ],
    // Ask Zenodo to reserve a DOI so reserve-phase can read it back and print it.
    prereserve_doi: true,
  };
}

// --- thin REST client --------------------------------------------------------------

function client(base, token) {
  const auth = { Authorization: `Bearer ${token}` };
  async function req(method, url, { json, body, headers } = {}) {
    const full = url.startsWith("http") ? url : `${base}${url}`;
    const res = await fetch(full, {
      method,
      headers: { ...auth, ...(json ? { "Content-Type": "application/json" } : {}), ...headers },
      body: json ? JSON.stringify(json) : body,
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`Zenodo ${method} ${full} -> ${res.status}: ${text.slice(0, 800)}`);
    return text ? JSON.parse(text) : {};
  }
  return {
    get: (u) => req("GET", u),
    post: (u, json) => req("POST", u, { json: json || {} }),
    put: (u, json) => req("PUT", u, { json }),
    putFile: (bucketUrl, filename, bytes) =>
      req("PUT", `${bucketUrl}/${encodeURIComponent(filename)}`, { body: bytes, headers: { "Content-Type": "application/octet-stream" } }),
  };
}

function requireEnv(name) {
  const v = process.env[name];
  if (!v) { console.error(`zenodo-publish: ${name} is not set; refusing to run.`); process.exit(2); }
  return v;
}

function paperPath(slug) { return join(papersRoot, slug, "paper.json"); }
function readPaper(slug) { return JSON.parse(readFileSync(paperPath(slug), "utf8")); }

// --- phases ------------------------------------------------------------------------

async function reserve({ slug, statePath, doiTexPath }) {
  const base = process.env.ZENODO_BASE || "https://sandbox.zenodo.org/api";
  const token = requireEnv("ZENODO_TOKEN");
  const isSandbox = base.includes("sandbox");
  const prefix = isSandbox ? "zenodo_sandbox_" : "zenodo_";
  const paper = readPaper(slug);
  const api = client(base, token);

  const priorId = paper[`${prefix}deposition_id`];
  let dep;
  if (priorId) {
    console.log(`zenodo-publish: new version of deposition ${priorId}`);
    const nv = await api.post(`/deposit/depositions/${priorId}/actions/newversion`);
    const draftUrl = nv.links && nv.links.latest_draft;
    if (!draftUrl) throw new Error("newversion returned no links.latest_draft");
    dep = await api.get(draftUrl);
  } else {
    console.log("zenodo-publish: creating a new deposition");
    dep = await api.post("/deposit/depositions", { metadata: buildMetadata(paper, { license: process.env.ZENODO_LICENSE }) });
  }

  const doi = dep.metadata && dep.metadata.prereserve_doi && dep.metadata.prereserve_doi.doi;
  const bucket = dep.links && dep.links.bucket;
  if (!doi) throw new Error("no pre-reserved DOI on the deposition");
  if (!bucket) throw new Error("no upload bucket on the deposition");

  const state = { id: dep.id, bucket, doi, conceptrecid: dep.conceptrecid, prefix, isSandbox };
  writeFileSync(statePath, JSON.stringify(state, null, 2));

  // doi.tex: printed on the title page by main.tex's \IfFileExists include.
  const tex =
    `% doi.tex - GENERATED by zenodo-publish.mjs (issue #8). Do not commit (gitignored).\n` +
    `\\begin{center}\\small DOI: \\url{https://doi.org/${doi}}\\end{center}\n`;
  writeFileSync(doiTexPath, tex);
  console.log(`zenodo-publish: reserved ${doi} (deposition ${dep.id}); wrote ${doiTexPath}`);
}

async function finalize({ slug, statePath, pdfPath, zipPath }) {
  const base = process.env.ZENODO_BASE || "https://sandbox.zenodo.org/api";
  const token = requireEnv("ZENODO_TOKEN");
  const state = JSON.parse(readFileSync(statePath, "utf8"));
  const paper = readPaper(slug);
  const api = client(base, token);

  // Upload files to the bucket (new files API).
  console.log("zenodo-publish: uploading PDF");
  await api.putFile(state.bucket, `${slug}.pdf`, readFileSync(pdfPath));
  if (zipPath) {
    console.log("zenodo-publish: uploading reproducibility zip");
    await api.putFile(state.bucket, `${slug}-reproducibility.zip`, readFileSync(zipPath));
  }

  // Set metadata, then publish.
  console.log("zenodo-publish: setting metadata");
  await api.put(`/deposit/depositions/${state.id}`, { metadata: buildMetadata(paper, { license: process.env.ZENODO_LICENSE }) });
  console.log("zenodo-publish: publishing");
  const published = await api.post(`/deposit/depositions/${state.id}/actions/publish`);

  const versionDoi = published.doi || (published.metadata && published.metadata.doi);
  const conceptDoi = published.conceptdoi || (published.metadata && published.metadata.conceptdoi);
  const conceptRecid = published.conceptrecid || state.conceptrecid;

  // Write the identifiers back into paper.json (committed via the workflow's PR).
  const p = state.prefix;
  paper[`${p}concept_recid`] = conceptRecid;
  paper[`${p}deposition_id`] = published.id || state.id;
  if (conceptDoi) paper[`${p}concept_doi`] = conceptDoi;
  if (versionDoi) paper[`${p}version_doi`] = versionDoi;
  writeFileSync(paperPath(slug), JSON.stringify(paper, null, 2) + "\n");

  console.log(`zenodo-publish: published. concept=${conceptDoi || "(after first publish)"} version=${versionDoi}`);
  // Surface for the workflow log / PR body.
  if (process.env.GITHUB_OUTPUT) {
    writeFileSync(process.env.GITHUB_OUTPUT, `version_doi=${versionDoi || ""}\nconcept_doi=${conceptDoi || ""}\n`, { flag: "a" });
  }
}

// --- main --------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const cmd = args._[0];
  const slug = args.slug;
  if (!slug) { console.error("zenodo-publish: --slug is required"); process.exit(2); }
  const statePath = args.state || join(papersRoot, slug, "zenodo-state.json");
  if (cmd === "reserve") {
    await reserve({ slug, statePath, doiTexPath: args["doi-tex"] || join(papersRoot, slug, "doi.tex") });
  } else if (cmd === "finalize") {
    await finalize({ slug, statePath, pdfPath: args.pdf || join(papersRoot, slug, "main.pdf"), zipPath: args.zip });
  } else {
    console.error("usage: zenodo-publish.mjs <reserve|finalize> --slug <slug> [--state <p>] [--pdf <p>] [--zip <p>] [--doi-tex <p>]");
    process.exit(2);
  }
}

// Only run when invoked directly, so buildMetadata/toFamilyGiven can be imported by tests.
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((e) => { console.error(e.message || e); process.exit(1); });
}
