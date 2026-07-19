// gen-index.mjs - build frontend/src/papers-index.ts from every
// papers/<slug>/paper.json, after validating that each declared \cite id
// resolves to a real source in frontend/src/sources.ts.
//
// The emitted file is committed and imported by the frontend bundle, so it is
// pure data with ZERO pimas imports (Layer A, CLAUDE.md 7). It introduces no
// numbers: it only carries paper metadata already written in the paper.json
// files. Run from inside papers/.
//
// ASCII only, no em-dash (CLAUDE.md 5).

import { readdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

/** Every citation id used in a compiled document. Handles both the numeric \cite (IEEEtran
 * papers, e.g. electronics-wall) and natbib's \citep / \citet (author-year papers, e.g.
 * coordination-tax), including their starred forms, optional [pre][post] notes, and
 * comma-separated id lists. */
function citesInTex(tex) {
  const ids = new Set();
  for (const m of tex.matchAll(/\\cite[pt]?\*?(?:\[[^\]]*\])*\{([^}]*)\}/g)) {
    for (const id of m[1].split(",").map((s) => s.trim()).filter(Boolean)) ids.add(id);
  }
  return ids;
}

/**
 * Canonicalize an abstract so the LaTeX copy (main.tex) and the plain-text copy
 * (paper.json, shown on the site) compare equal when they say the same thing.
 * Unwraps simple markup, drops inline-math delimiters, folds "N percent" and
 * "N\%" to a single "%" form, and strips the LaTeX thin-space `{,}` used inside
 * digit groupings (200{,}000 in main.tex vs 200,000 in paper.json).
 */
function normAbstract(s) {
  return String(s)
    .replace(/\\(?:emph|textbf|textit|texttt|mbox)\{([^}]*)\}/g, "$1")
    .replace(/\\%/g, "%")
    .replace(/\$/g, "")
    .replace(/~/g, " ")
    .replace(/(\d)\{,\}(\d)/g, "$1,$2")
    .replace(/\bper\s?cent\b/gi, "%")
    .replace(/\s*%/g, "%")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

// sources.ts has no runtime imports, so Node imports the TypeScript directly (native
// type stripping). Paths resolve relative to this file, so cwd does not matter.
const { sourceById } = await import(new URL("../../frontend/src/sources.ts", import.meta.url).href);

// The papers module root (papers/), one level up from scripts/.
const papersRoot = fileURLToPath(new URL("..", import.meta.url));

// Discover paper.json files: papers/<slug>/paper.json.
const entries = readdirSync(papersRoot, { withFileTypes: true })
  .filter((d) => d.isDirectory() && d.name !== "scripts" && d.name !== "node_modules")
  .map((d) => join(papersRoot, d.name, "paper.json"))
  .filter((p) => existsSync(p));

const papers = [];
let invalid = false;

for (const path of entries) {
  const paper = JSON.parse(readFileSync(path, "utf8"));
  const cites = Array.isArray(paper.cites) ? paper.cites : [];
  for (const id of cites) {
    if (!sourceById(id)) {
      console.error(`gen-index: ${path} cites unknown source id "${id}"`);
      invalid = true;
    }
  }

  // Prose- and abstract-level rules only apply once a paper is a real document
  // (main.tex exists). A paper.json alone (pre-scaffold) is only checked for
  // resolvable cite ids above.
  const paperDir = dirname(path);
  const mainTexPath = join(paperDir, "main.tex");
  if (existsSync(mainTexPath)) {
    const mainTex = readFileSync(mainTexPath, "utf8");

    // Rule: the declared cites (paper.json, shown on the site) and the cites the
    // compiled paper actually uses (main.tex + body/*.tex) must match exactly.
    // refs.bib carries every source, so nothing stops prose from citing an
    // undeclared source or declaring one it never uses; this makes the site's
    // reference list an exact manifest of the paper.
    const proseCites = citesInTex(mainTex);
    const bodyDir = join(paperDir, "body");
    if (existsSync(bodyDir)) {
      for (const f of readdirSync(bodyDir)) {
        if (f.endsWith(".tex")) for (const id of citesInTex(readFileSync(join(bodyDir, f), "utf8"))) proseCites.add(id);
      }
    }
    const declared = new Set(cites);
    for (const id of proseCites) {
      if (!declared.has(id)) {
        console.error(`gen-index: ${path}: prose cites "${id}" but paper.json does not declare it`);
        invalid = true;
      }
    }
    for (const id of declared) {
      if (!proseCites.has(id)) {
        console.error(`gen-index: ${path}: paper.json declares "${id}" but no section cites it`);
        invalid = true;
      }
    }

    // Rule: the LaTeX abstract must match paper.json.abstract (after folding the
    // one legitimate LaTeX-vs-plaintext difference), so the site and the PDF
    // present the same summary.
    const m = mainTex.match(/\\begin\{abstract\}([\s\S]*?)\\end\{abstract\}/);
    if (!m) {
      console.error(`gen-index: ${path}: main.tex has no \\begin{abstract}...\\end{abstract} block`);
      invalid = true;
    } else if (normAbstract(m[1]) !== normAbstract(paper.abstract || "")) {
      console.error(`gen-index: ${path}: main.tex abstract does not match paper.json abstract`);
      invalid = true;
    }
  }

  // Per-paper Zenodo DOI (issue #8), written back into paper.json by the zenodo
  // workflow. Production takes precedence over sandbox; while only a sandbox DOI
  // exists we still surface it, flagged so the site can label it "(sandbox)". The
  // DOI is an identifier from Zenodo, not a number we invent (CLAUDE.md 1): its
  // source is the minted deposition, recorded in paper.json.
  const prodDoi = paper.zenodo_concept_doi || "";
  const sandboxDoi = paper.zenodo_sandbox_concept_doi || "";
  const doi = prodDoi || sandboxDoi || null;
  const doiIsSandbox = !prodDoi && !!sandboxDoi;

  papers.push({
    slug: paper.slug,
    title: paper.title,
    authors: (paper.authors || []).map((a) => ({
      name: a.name || "",
      affiliation: a.affiliation || "",
      orcid: a.orcid || "",
    })),
    abstract: paper.abstract || "",
    date: paper.date || "",
    keywords: paper.keywords || [],
    cites,
    pdf: `papers/${paper.slug}.pdf`,
    doi,
    doiIsSandbox,
  });
}

if (invalid) {
  console.error("gen-index: aborting; fix the unresolved cite ids above.");
  process.exit(1);
}

// Sort by date descending (newest first).
papers.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));

const out = `/**
 * papers-index.ts - GENERATED by papers/scripts/gen-index.mjs. Do not edit by hand.
 *
 * Metadata for every paper under papers/<slug>/. Pure data, zero pimas imports
 * (Layer A, CLAUDE.md 7): the reactive skin reads this list, it never writes it.
 * Every id in each paper's \`cites\` is validated against frontend/src/sources.ts
 * at generation time, so a PaperMeta.cites entry always resolves via sourceById.
 * Regenerate with: npm run gen:index (from papers/).
 */

export interface PaperAuthor {
  name: string;
  affiliation: string;
  orcid: string;
}

export interface PaperMeta {
  slug: string;
  title: string;
  authors: PaperAuthor[];
  abstract: string;
  date: string;
  keywords: string[];
  cites: string[];
  /** Path to the compiled PDF, relative to the site root: papers/<slug>.pdf */
  pdf: string;
  /**
   * Per-paper Zenodo concept DOI (always resolves to the latest version), or null
   * until one is minted. Production preferred over sandbox; see doiIsSandbox.
   */
  doi: string | null;
  /** True when \`doi\` is a sandbox.zenodo.org DOI (label it as such; not citable). */
  doiIsSandbox: boolean;
}

export const PAPERS: PaperMeta[] = ${JSON.stringify(papers, null, 2)};
`;

const outPath = fileURLToPath(new URL("../../frontend/src/papers-index.ts", import.meta.url));
writeFileSync(outPath, out);
console.log(`gen-index: wrote ${outPath} with ${papers.length} paper(s).`);
