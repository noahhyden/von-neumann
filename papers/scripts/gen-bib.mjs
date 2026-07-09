// gen-bib.mjs - generate papers/refs.bib from the project's single bibliography
// source of truth, frontend/src/sources.ts (CLAUDE.md 1, 4).
//
// This script introduces NO numbers of its own: every BibTeX entry mirrors a
// source that already lives in sources.ts, keyed by that source's `id` so a
// \cite{williams-ayres-heller-2002} in a paper matches the site's Cite id.
//
// sources.ts is TypeScript with no runtime imports, so Node (>=22.6, native type
// stripping) imports it directly - no build step and no reaching into another
// module's toolchain. Paths are resolved relative to this file (import.meta.url), so
// the script runs correctly from any working directory.
//
// ASCII only, no em-dash (CLAUDE.md 5).

import { writeFileSync } from "node:fs";

const { SOURCES } = await import(new URL("../../frontend/src/sources.ts", import.meta.url).href);

/** Escape the four BibTeX-special characters. Backslash is never introduced by data. */
function esc(s) {
  return String(s).replace(/([&%#_])/g, "\\$1");
}

/**
 * Convert one author DISPLAY token ("A. Nicholson", "R. A. Freitas Jr.") into BibTeX's
 * canonical "Last, First" (or "Last, Suffix, First") form.
 *
 * We use "Last, First" rather than the raw display order so BibTeX can identify the
 * surname: numeric styles (IEEEtran) still print "A. Nicholson", and author-year styles
 * (natbib/plainnat, used by the astrobiology-journal manuscript) can form proper Harvard
 * labels like "(Nicholson, 2013)" instead of the whole name. Person names in sources.ts
 * always begin with initials ("A.", "M. H."); a token that does not (an institutional
 * author such as "International Astronomical Union") is left brace-wrapped verbatim so
 * BibTeX does not mistake its last word for a surname.
 */
function toBibName(token) {
  const words = token.split(/\s+/).filter(Boolean);
  if (words.length <= 1 || !/^[A-Z]\.$/.test(words[0])) return `{${token}}`;
  let suffix = null;
  if (/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(words[words.length - 1])) suffix = words.pop();
  const last = words.pop();
  const first = words.join(" ");
  return suffix ? `${last}, ${suffix}, ${first}` : `${last}, ${first}`;
}

/**
 * Convert an author DISPLAY string into BibTeX's "A and B and C" form.
 *
 * The display strings in sources.ts intentionally carry affiliations, "(eds.)",
 * "et al." / "and others", and name suffixes ("Jr.", "III"). We strip the parts that must
 * never enter the author field, split into individual names on the display separators
 * (comma, ampersand, semicolon, or the word "and"), and hand each to toBibName. A trailing
 * "et al." or "and others" becomes BibTeX's "others" keyword (IEEEtran renders it "et al.";
 * author-year styles render it "et al." too).
 *
 * Applied before esc(), so any "&" here is still a literal separator.
 */
function authorsToBib(authors) {
  // 1. Strip parenthetical groups (affiliations, "(eds.)", "(ed.)") and collapse whitespace.
  let s = String(authors)
    .replace(/\s*\([^)]*\)/g, "")
    .replace(/\s+/g, " ")
    .trim();

  // 2. Detect a trailing "et al." or "and others" and replace it with BibTeX's "others".
  let hasEtAl = false;
  const stripped = s.replace(/\s*(?:\bet al\.?|\band others)\s*$/i, "");
  if (stripped !== s) {
    hasEtAl = true;
    s = stripped.trim();
  }

  // 3. Split into author tokens on the display separators (&, ;, comma, or the word "and"),
  //    convert each to "Last, First", and drop empties.
  const tokens = s
    .split(/\s*(?:[&;,]|\band\b)\s*/i)
    .map((t) => t.trim())
    .filter((t) => t.length > 0)
    .map(toBibName);

  // 4. Join with " and ", appending " and others" when the et al. flag fired.
  if (hasEtAl) tokens.push("others");
  return tokens.join(" and ");
}

/**
 * Pick an entry type from the venue text. Order matters: the more specific
 * tests run first. This is a heuristic over free-text venues, not a schema.
 */
function entryType(venue) {
  const v = String(venue);
  if (/textbook|isbn/i.test(v)) return "book";
  if (/nasa|ntrs|report|technical/i.test(v)) return "techreport";
  if (/\brfc\b|\biau\b|astm|codata|standard/i.test(v)) return "misc";
  const looksJournal =
    /journal|transactions|trans\.|review|letters|\bnature\b|pnas|geophys|acta|astronom|env\.|environmental|\bj\.\b|doi|\d+\s*\(\d+\)|\d+:\d+/i.test(
      v,
    );
  return looksJournal ? "article" : "misc";
}

/** The venue field name that carries the "where published" text for each type. */
const VENUE_FIELD = {
  article: "journal",
  book: "publisher",
  techreport: "institution",
  misc: "howpublished",
};

function toBibEntry(src) {
  const type = entryType(src.venue);
  const lines = [];
  lines.push(`@${type}{${src.id},`);
  // Title in braces so BibTeX preserves capitalization.
  lines.push(`  title = {{${esc(src.title)}}},`);
  lines.push(`  author = {${esc(authorsToBib(src.authors))}},`);
  lines.push(`  year = {${esc(src.year)}},`);
  const venueField = VENUE_FIELD[type];
  if (src.venue) lines.push(`  ${venueField} = {${esc(src.venue)}},`);
  if (src.url) lines.push(`  url = {${src.url}},`);
  // A note only where it adds something: flag entries the repo cites by
  // reference with no online link, so the gap is visible in the .bib too.
  if (!src.url) lines.push(`  note = {Cited by reference; no online link.},`);
  lines.push(`}`);
  return lines.join("\n");
}

const header = [
  "% refs.bib - GENERATED by papers/scripts/gen-bib.mjs. Do not edit by hand.",
  "% Every entry mirrors a source in frontend/src/sources.ts (the single",
  "% bibliography source of truth). Regenerate with: npm run gen:bib",
  "",
  "",
].join("\n");

const body = SOURCES.map(toBibEntry).join("\n\n");
writeFileSync(new URL("../refs.bib", import.meta.url), header + body + "\n");
console.log(`gen-bib: wrote refs.bib with ${SOURCES.length} entries.`);
