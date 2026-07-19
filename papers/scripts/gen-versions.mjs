// gen-versions.mjs - build frontend/src/papers-versions.ts, the per-paper version
// list, from git history. A "version" is every commit whose diff touches
// papers/<slug>/ (the paper.json, main.tex, or body/*.tex); git history IS the
// version list, no manual tagging (issue #7).
//
// This is a BUILD-TIME generator, not a committed one, and that distinction is
// load-bearing: the newest version entry references the current commit's own SHA,
// which does not exist until after the commit is made, so the version list can
// never be committed without contradicting the `git diff --exit-code
// frontend/src/papers-index.ts` gate in ci.yml. papers-index.ts stays git-derived-
// free and deterministic; the git-derived version data lives HERE, in a gitignored
// module regenerated on every build (like refs.bib).
//
// It introduces NO numbers of its own: every field mirrors git metadata (commit
// sha, author date, subject) or is a path/URL derived from the slug and sha.
//
// The rendered PDF for a version lives on the `paper-pdfs` orphan branch at
// <slug>/<shortSha>.pdf (issue #7 uses release-archive, not historical recompiles).
// We detect which versions have an archived PDF with `git ls-tree` over that branch;
// a version with no archived PDF falls back to a link to its frozen source on GitHub.
//
// ASCII only, no em-dash (CLAUDE.md 5).

import { readdirSync, existsSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

// papers/ (one up from scripts/) and the repo root (two up). All git commands run
// with cwd = repoRoot and repo-relative pathspecs, so cwd at call time does not
// matter.
const papersRoot = fileURLToPath(new URL("..", import.meta.url));
const repoRoot = fileURLToPath(new URL("../..", import.meta.url));

// The candidate refs that may hold the archived PDFs, most-local first. In CI the
// orphan branch is fetched as origin/paper-pdfs; locally it may be checked out as
// paper-pdfs. PAPER_PDFS_REF overrides for tests.
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

/**
 * The set of "<slug>/<shortSha>.pdf" paths archived on the paper-pdfs branch. We
 * try each candidate ref and use the first that resolves; if none do (no branch
 * yet, or a shallow clone that never fetched it), the set is empty and every
 * version falls back to a source link. This is the whole reason gen-versions can
 * run before the archive is assembled in CI: it reads the branch, not the built
 * files.
 */
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
  // NUL-delimited fields, newline-delimited records: full sha, short sha, author
  // date (ISO, date only), subject. --date=short gives YYYY-MM-DD to match the
  // ISO dates the site already shows.
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

const outPath = fileURLToPath(new URL("../../frontend/src/papers-versions.ts", import.meta.url));
writeFileSync(outPath, out);
console.log(`gen-versions: wrote ${outPath} with ${total} version(s) across ${slugs.length} paper(s).`);
