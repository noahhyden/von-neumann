// gen-versions.mjs - build frontend/src/papers-versions.ts from git history (issue #7; see papers/README.md).

import { readdirSync, existsSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { execFileSync } from "node:child_process";

// papers/ is one up from scripts/, the repo root two up; git runs with cwd = repoRoot.
const papersRoot = join(import.meta.dirname, "..");
const repoRoot = join(import.meta.dirname, "..", "..");

// Candidate refs holding archived PDFs, most-local first; PAPER_PDFS_REF overrides for tests.
const PDF_REFS = [
  process.env.PAPER_PDFS_REF,
  "paper-pdfs",
  "origin/paper-pdfs",
].filter(Boolean);

/** Run git at the repo root; return trimmed stdout, or null if git errors. */
function git(args) {
  try {
    return execFileSync("git", args, { cwd: repoRoot, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return null;
  }
}

/** The GitHub owner/repo, derived from origin, falling back to the known repo. */
function repoSlug() {
  const url = git(["remote", "get-url", "origin"]) || "";
  const m = url.match(/github\.com[:/]([^/]+\/[^/]+?)(?:\.git)?$/);
  return m ? m[1] : "noahhyden/von-neumann";
}

/** The "<slug>/<shortSha>.pdf" paths archived on paper-pdfs; see README, "Reading the PDF archive". */
function archivedPdfs() {
  for (const ref of PDF_REFS) {
    const out = git(["ls-tree", "-r", "--name-only", ref]);
    if (out !== null) {
      return new Set(out.split("\n").map((s) => s.trim()).filter((s) => s.endsWith(".pdf")));
    }
  }
  return new Set();
}

const GH = repoSlug();
const archived = archivedPdfs();

// Discover paper slugs the same way gen-index does: papers/<slug>/paper.json.
const slugs = readdirSync(papersRoot, { withFileTypes: true })
  .filter((d) => d.isDirectory() && d.name !== "scripts" && d.name !== "node_modules")
  .filter((d) => existsSync(join(papersRoot, d.name, "paper.json")))
  .map((d) => d.name)
  .sort();

/** Versions for one slug, newest first, from commits touching papers/<slug>/. */
function versionsFor(slug) {
  // NUL-delimited fields, newline-delimited records: full sha, short sha, author date (YYYY-MM-DD), subject.
  const out = git(["log", "--date=short", "--format=%H%x00%h%x00%ad%x00%s", "--", `papers/${slug}/`]);
  if (!out) return [];
  return out
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const [sha, shortSha, date, ...rest] = line.split("\0");
      const subject = rest.join("\0"); // a subject can (rarely) contain a NUL-free remainder
      const relPdf = `${slug}/${shortSha}.pdf`;
      const hasPdf = archived.has(relPdf);
      return {
        shortSha,
        sha,
        date,
        subject,
        // Site-root-relative, matching the existing papers/<slug>.pdf convention.
        pdf: `papers/${slug}/${shortSha}.pdf`,
        // Frozen source at this commit, the fallback when no PDF is archived.
        sourceUrl: `https://github.com/${GH}/tree/${sha}/papers/${slug}`,
        hasPdf,
      };
    });
}

const byslug = {};
let total = 0;
for (const slug of slugs) {
  const v = versionsFor(slug);
  byslug[slug] = v;
  total += v.length;
}

if (total === 0) {
  console.warn(
    "gen-versions: no git history found (shallow clone or not a repo); emitting an empty manifest. " +
      "The site will show no version list. In CI, check out with fetch-depth: 0.",
  );
}

const out = `/**
 * papers-versions.ts - GENERATED at build time by papers/scripts/gen-versions.mjs.
 * Do not edit by hand, and do not commit: this file is gitignored. It is derived
 * from git history (a version = every commit touching papers/<slug>/), so its
 * newest entry names the current commit's own SHA and therefore cannot live in a
 * committed file (see gen-versions.mjs and papers-index.ts). Pure data, zero pimas
 * imports (Layer A, CLAUDE.md 7): the reactive skin reads this list, never writes it.
 * Regenerate with: npm run gen:versions (from papers/), or it runs in frontend build.
 */

export interface VersionMeta {
  /** Abbreviated commit hash; the version's stable id and PDF filename stem. */
  shortSha: string;
  /** Full commit hash (used for the source-tree link). */
  sha: string;
  /** Author date, ISO YYYY-MM-DD. */
  date: string;
  /** Commit subject line. */
  subject: string;
  /** Site-root-relative path to this version's archived PDF: papers/<slug>/<shortSha>.pdf */
  pdf: string;
  /** GitHub link to the paper's frozen source at this commit (the no-PDF fallback). */
  sourceUrl: string;
  /** True when the PDF is archived on the paper-pdfs branch; else link sourceUrl. */
  hasPdf: boolean;
}

export const PAPER_VERSIONS: Record<string, VersionMeta[]> = ${JSON.stringify(byslug, null, 2)};
`;

const outPath = join(import.meta.dirname, "..", "..", "frontend", "src", "papers-versions.ts");
writeFileSync(outPath, out);
console.log(`gen-versions: wrote ${outPath} with ${total} version(s) across ${slugs.length} paper(s).`);
