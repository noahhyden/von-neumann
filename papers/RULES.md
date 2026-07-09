# papers - rules in force

This is the canonical rulebook for the `papers` module: every rule that governs a
paper here, in one place, with a note on how each one is enforced. It consolidates
what used to be scattered across the repo charter ([`CLAUDE.md`](../CLAUDE.md)), the
module [`README.md`](README.md), [`REFERENCES.md`](REFERENCES.md), the generator
scripts, and CI. Where a rule restates a repo-wide one, the `CLAUDE.md` section is
cited so the two never drift.

A rule marked **[enforced]** fails the build (a generator or a CI step exits nonzero)
when broken. A rule marked **[convention]** is not machine-checked yet; keep it by
hand.

---

## R1. A paper introduces no new numbers. [enforced upstream]

A paper may only *restate* a result that is already sourced in the module that
produced it. It never introduces a number of its own (`CLAUDE.md` 1; this module's
[`REFERENCES.md`](REFERENCES.md)).

- Every quantitative claim must already appear, with its source, in the originating
  module's `REFERENCES.md` and in the project's findings. If a number has no source
  there, do not state it - that is the cardinal rule, and it is not relaxed for prose.
- This module's own `REFERENCES.md` therefore lists no values: there are none to list.

*Enforcement:* upstream. The number's source lives in its home module's
`REFERENCES.md`, which that module's tests and review gate. A paper that cites a real
source but misstates its number is a review responsibility, not a mechanical check.

## R2. The bibliography has one source of truth: `frontend/src/sources.ts`. [enforced]

The typed `SOURCES` array in [`frontend/src/sources.ts`](../frontend/src/sources.ts)
is the single bibliography source of truth for the whole repo. A `\cite{id}` in a
paper uses the same `id` the live site cites by, so paper and site cite the same work
by the same key.

- `refs.bib` is **generated** from `sources.ts` by `scripts/gen-bib.mjs`. It is a
  build artifact: gitignored, never hand-edited.
- To add or correct a source, edit `sources.ts` (and the originating module's
  `REFERENCES.md`), then regenerate. Never edit `refs.bib`.

*Enforcement:* `refs.bib` is gitignored, so a hand edit cannot be committed; CI
regenerates it from `sources.ts` before every build.

## R3. Declared cites and used cites match exactly. [enforced]

Two lists of citation ids exist for each paper, and they must be identical as sets:

1. `paper.json`'s `cites` array - the manifest shown on the site.
2. Every citation id used in the compiled document (`main.tex` and `body/*.tex`). The
   checker recognizes both the numeric `\cite{...}` of IEEEtran papers and the author-year
   `\citep{...}`/`\citet{...}` of natbib papers (see the per-paper format note in R7).

Because `refs.bib` carries *all* sources, nothing stops prose from citing a source
the manifest omits, or the manifest from declaring a source the prose never uses.
Both are drift and both fail the build:

- **prose cites an id `paper.json` does not declare** -> error.
- **`paper.json` declares an id no section cites** -> error.

Every declared id must additionally resolve in `sources.ts` (R2).

*Enforcement:* `scripts/gen-index.mjs` (run in CI) parses the `.tex` files and the
manifest and exits nonzero on any mismatch or unresolved id.

## R4. The abstract says the same thing in both places. [enforced]

The abstract lives twice: as plain text in `paper.json` (shown on the site) and as
LaTeX in `main.tex` (typeset into the PDF). They must carry the same words. The only
differences allowed are the mechanical LaTeX-vs-plaintext ones: inline math
delimiters (`$...$`), the escaped percent sign (`\%` for `%`), non-breaking spaces
(`~`), simple markup wrappers (`\emph`, `\textbf`, ...), and writing a percentage as
either "30 percent" or "30\%". After folding those, the two must be identical.

*Enforcement:* `scripts/gen-index.mjs` normalizes both copies and exits nonzero if
they differ.

## R5. Typography: ASCII only where it counts. [enforced]

Binding repo-wide (`CLAUDE.md` 5) and enforced here for the module's authored files
(`*.tex`, `*.json`, `*.md`, `*.mjs`):

- **No em-dash (U+2014).** Use an ASCII hyphen `-`.
- **No en-dash (U+2013).** Use an ASCII hyphen `-`, including numeric ranges:
  `90-96\%`, not a dash range. Wrap a range that must not break across lines in
  `\mbox{...}`.
- **No emoji.** The check targets the emoji code planes, the flag range, and the
  emoji variation selector (U+FE0F).
- **Math and astronomy symbols are allowed and are not emoji:** Greek letters, the
  approximately-equal and much-greater signs (≈, ≫), superscripts (²), the sun symbol
  (☉), arrows. Accented letters in names (for example the author's) are fine too.

*Enforcement:* `scripts/check-typography.mjs` (run in CI) scans authored files and
exits nonzero on any em-dash, en-dash, or emoji. It skips generated/build artifacts
(`refs.bib`, `build/`, `node_modules/`).

## R6. Generated files vs authored files. [enforced]

| File | Origin | Committed? | Rule |
| --- | --- | --- | --- |
| `refs.bib` | generated from `sources.ts` | no (gitignored) | never hand-edit (R2) |
| `main.tex`, `body/*.tex` | hand-written | yes | `gen-tex.mjs` scaffolds them **once** and never overwrites |
| `paper.json` | hand-written | yes | the paper's metadata + manifest |
| `frontend/src/papers-index.ts` | generated from all `paper.json` | yes | must match generator output |
| `*.pdf`, `*.aux`, ... | LaTeX build | no (gitignored) | CI produces the published PDF |

- `gen-tex.mjs` only ever **creates missing** files, so hand-written prose is safe to
  regenerate against.
- The committed `papers-index.ts` must equal what `gen-index.mjs` emits: CI runs the
  generator and fails on any `git diff`. Re-run `npm run gen:index` after editing a
  `paper.json`.
- `papers-index.ts` is pure data with zero pimas imports (Layer A, `CLAUDE.md` 7).

*Enforcement:* `.gitignore` for the artifacts; a `git diff --exit-code` step in CI
for the index; `gen-tex.mjs`'s existence guard for no-overwrite.

## R7. Module hygiene and license. [convention]

- One module, one directory: this module owns its `README.md`, `RULES.md`,
  `REFERENCES.md`, scripts, and papers, and is independently runnable (`CLAUDE.md` 4).
- Plain language: a paper explains its "why" in words, for non-specialists
  (`CLAUDE.md` 4).
- The written research (prose in `*.tex` and the Markdown here) is licensed
  **CC BY-NC-ND 4.0** (see [`../LICENSE-DOCS`](../LICENSE-DOCS)). The document classes are
  third-party (LPPL) and are **not redistributed** - CI relies on their being in TeX Live.
- **Format is per paper, whichever the target venue wants; both must be TeX-Live-only.**
  `electronics-wall` uses `IEEEtran` (conference, numeric `\cite`). `coordination-tax` uses
  the standard `article` class as a single-column journal manuscript with author-year
  citations (`natbib` + `plainnat`, `\citep`/`\citet`), suitable as an initial submission to
  an astrobiology journal such as the International Journal of Astrobiology; the publisher's
  own house class (e.g. Cambridge's `cup-journal`, which is not in TeX Live and needs biber)
  is applied at submission time, outside CI. `refs.bib` is style-agnostic and serves both:
  `gen-bib.mjs` emits BibTeX-canonical `Last, First` names so numeric styles print "F. Last"
  and author-year styles can form proper "(Last, Year)" labels from the same entries.

---

## Praxis: how a paper here is written. [convention, not enforced]

The rules above (R1-R7) are about correctness and are machine-checked. The praxis
below is about making a paper read as *real scientific publishing* rather than a
sourced draft. It is drawn from studying the works this project actually cites -
Nicholson & Forgan 2013 and Forgan, Papadogiannakis & Kitching 2013 (the swarm
lineage), Nagapurkar & Das 2022 and Freitas & Merkle 2004 (the closure/embodied-energy
lineage) - and from standard journal/conference conventions. None of it is enforced by a
script; treat it as the house style, and depart from it only with a reason. Some items below
are class-specific (noted inline); the section spine and rigor apply whatever the class.

- **P1. Follow the section spine.** Abstract -> `I. Introduction` (prior work folded
  in, citation-dense; under IEEEtran open it with `\IEEEPARstart`) -> a `Method`/`Model` section with
  subsections -> a `Results` section carrying the figures and a summary table ->
  `Discussion` that *leads with a Limitations subsection* and then draws implications
  -> `Conclusion` -> optional unnumbered `\section*{Acknowledgment}` -> References.
  Appendices are optional; author biographies are a journal feature and do not belong
  in a `conference`-class paper.
- **P2. Voice: first person plural, active, direct.** Write "we add", "we find", "we
  measure". State the result plainly, then hedge honestly ("suggests", "up to",
  "a conservative bound"). Name and own the model's simplifications rather than hiding
  them - both swarm-lineage papers do exactly this.
- **P3. Keep a named-scenario spine.** Define a small set of named regimes (for the
  swarm paper: powered / slingshot-nearest / slingshot-maxboost) and carry those exact
  names, unchanged, through the Method, the Results subsections, the figures, and the
  summary table. The reader should be able to track one regime end to end.
- **P4. Figures are the primary output, and they show spread.** Aim for two to five
  figures. Prefer data plots (a real ensemble) over decoration; show the distribution
  or uncertainty (box plots, IQR, shaded standard error), never a single deterministic
  curve where an ensemble exists. One schematic of the mechanism is welcome. Each
  caption is a full sentence stating what is plotted *and* how spread is shown, and
  cites the source of any borrowed diagram. Every figure is referenced from the prose
  (`Fig.~\ref{...}`). Draw figures at final size (one 3.5 in column), serif font,
  8-9 pt; generate them at build time as gitignored vector PDFs (R6), the same way
  `refs.bib` is generated.
- **P5. Include at least one summary table** of scenario vs. headline number (median or
  mean with its spread). Use `booktabs`; the table `\caption` goes *above* it.
- **P6. Number the equations and reference them by number**, including the one scaling
  relation that bridges the toy model to the real-world quantity (for the swarm paper,
  the dimensionless lag ratio; for the closure paper, the `1/(1-C)` leverage and the
  rocket equation).
- **P7. Cite densely: aim for 15-30 references.** The Introduction should situate the
  contribution in the literature, and the paper must cite the specific prior work it
  extends. Only cite sources that already exist in `sources.ts` (R1/R2); the swarm and
  closure modules already carry far more relevant sources than a first draft uses.
- **P8. State the measurement basis and scope explicitly** in the Method, especially
  for energy or life-cycle figures (which basis, what is excluded). This is P-level
  house style *and* the substance of `CLAUDE.md` 1; an embodied-energy number without
  its basis reads as unfinished.
- **P9. Typography reality check.** The real papers in these fields *do* use em-dashes
  (U+2014) in titles and asides and en-dashes (U+2013) in compounds and ranges. We do
  not (R5, enforced). Imitate their rigor and structure, not their punctuation: use an
  ASCII hyphen everywhere, and write ranges as `9-38` or `90-96\%`.

---

## What runs, and what it checks

| Command | Checks (fails on violation) |
| --- | --- |
| `npm run gen:bib` | regenerates `refs.bib` from `sources.ts` (R2) |
| `npm run gen:index` | R3 (cite match + resolve), R4 (abstract match); writes `papers-index.ts` (R6) |
| `npm run check:typography` | R5 (no em-dash, en-dash, emoji) |
| `npm run check` | `gen:index` + `check:typography` together (R3, R4, R5, R6) |
| CI (`.github/workflows/ci.yml`, `papers` job) | all of the above, plus the index-matches-generator diff (R6) and that **every** paper typesets |

On deploy (`pages.yml`), typesetting is best-effort: a broken paper is skipped with a
warning and never blocks the site. Correctness is gated on the PR by `ci.yml`, not at
deploy time.

## Authoring flow (rule-aware)

1. Add the paper's sources to `sources.ts` (and each source's home-module
   `REFERENCES.md`); run `npm run gen:bib`.
2. Write `papers/<slug>/paper.json` (title, authors, date, keywords, sections,
   `cites`, abstract).
3. `node scripts/gen-tex.mjs <slug>` to scaffold `main.tex` + `body/*.tex` (the
   scaffolded abstract is copied verbatim from `paper.json`, so R4 holds immediately).
4. Write the prose in `body/*.tex`. Cite every quantitative claim - `\cite{<id>}` under
   IEEEtran, or `\citep{<id>}`/`\citet{<id>}` under natbib author-year. Keep the declared
   `cites` and the ids you actually use in exact agreement (R3).
5. `npm run check` to validate cites (R3), the abstract (R4), and typography (R5), and
   to refresh `papers-index.ts` (R6). Run this **after** the prose is written, since
   R3 requires declared and used cites to match.

## The one-line test before you commit a paper

> Does every number trace to a source in its home module (R1), does every citation id
> resolve and do the declared and used cites match exactly (R2, R3), does the abstract
> match in both places (R4), is the typography clean (R5), and are the generated files
> regenerated and in sync (R6)?

If any answer is no, it is not done.
