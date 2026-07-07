// gen-tex.mjs - scaffold an IEEEtran paper from papers/<slug>/paper.json.
//
// Usage: node scripts/gen-tex.mjs <slug>
//
// This only ever CREATES missing files. It never overwrites an existing
// main.tex or an existing body/<section>.tex, so hand-written prose is safe.
// Run it once to lay down the skeleton, then edit the .tex files by hand.
//
// ASCII only, no em-dash (CLAUDE.md 5).

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const slug = process.argv[2];
if (!slug) {
  console.error("usage: node scripts/gen-tex.mjs <slug>");
  process.exit(1);
}

const paperDir = join(slug);
const paperJsonPath = join(paperDir, "paper.json");
if (!existsSync(paperJsonPath)) {
  console.error(`gen-tex: ${paperJsonPath} not found. Create it first.`);
  process.exit(1);
}
const paper = JSON.parse(readFileSync(paperJsonPath, "utf8"));

/** Slugify a section name into a body filename stem. */
function sectionSlug(name) {
  return String(name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const sections = Array.isArray(paper.sections) ? paper.sections : [];
const bodyDir = join(paperDir, "body");
mkdirSync(bodyDir, { recursive: true });

let created = 0;

// --- main.tex (only if missing) --------------------------------------------
const mainPath = join(paperDir, "main.tex");
if (!existsSync(mainPath)) {
  const authors = Array.isArray(paper.authors) ? paper.authors : [];
  const authorBlocks = authors.map((a) => {
    const parts = [`\\IEEEauthorblockN{${a.name || ""}}`];
    const affLines = [];
    if (a.affiliation) affLines.push(a.affiliation);
    if (a.orcid && String(a.orcid).trim() !== "") affLines.push(`ORCID: ${a.orcid}`);
    if (affLines.length) parts.push(`\\IEEEauthorblockA{${affLines.join(" \\\\ ")}}`);
    return parts.join("\n");
  });
  const authorField = authorBlocks.length
    ? authorBlocks.join("\n\\and\n")
    : "\\IEEEauthorblockN{}";

  const keywords = Array.isArray(paper.keywords) ? paper.keywords.join(", ") : "";
  const inputs = sections.map((s) => `\\input{body/${sectionSlug(s)}}`).join("\n");

  const main = `% main.tex - scaffolded by papers/scripts/gen-tex.mjs. Edit freely.
\\documentclass[conference]{IEEEtran}
\\usepackage{graphicx}
\\usepackage{cite}
\\usepackage{url}
\\usepackage{amsmath}

\\title{${paper.title || ""}}

\\author{
${authorField}
}

\\begin{document}
\\maketitle

\\begin{abstract}
${paper.abstract || ""}
\\end{abstract}

\\begin{IEEEkeywords}
${keywords}
\\end{IEEEkeywords}

${inputs}

\\bibliographystyle{IEEEtran}
\\bibliography{../refs}

\\end{document}
`;
  writeFileSync(mainPath, main);
  created++;
  console.log(`gen-tex: wrote ${mainPath}`);
} else {
  console.log(`gen-tex: ${mainPath} exists, left untouched.`);
}

// --- body/<section>.tex stubs (only if missing) ----------------------------
for (const name of sections) {
  const path = join(bodyDir, `${sectionSlug(name)}.tex`);
  if (existsSync(path)) {
    console.log(`gen-tex: ${path} exists, left untouched.`);
    continue;
  }
  const stub = `% TODO: write this section.\n\\section{${name}}\n`;
  writeFileSync(path, stub);
  created++;
  console.log(`gen-tex: wrote ${path}`);
}

console.log(`gen-tex: done (${created} file(s) created).`);
