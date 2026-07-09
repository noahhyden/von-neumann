# papers

The project's IEEE-LaTeX paper pipeline. Each paper restates the project's sourced
findings in a citable form; the bibliography is not written by hand but *generated*
from the repo's single bibliography source of truth,
[`frontend/src/sources.ts`](../frontend/src/sources.ts). A `\cite{id}` in a paper uses
the same id the live site uses, so the paper and the site cite the same work by the
same key.

This is a module like any other (CLAUDE.md 4): one directory, its own README,
`REFERENCES.md`, and scripts, independently runnable. It adds no new numbers of its
own (see [`REFERENCES.md`](REFERENCES.md)).

**The binding rules for a paper live in [`RULES.md`](RULES.md)** - the cardinal
"no new numbers," the one bibliography source of truth, the cite/abstract/typography
checks and how each is enforced. This README is the how-to; `RULES.md` is the what and
the why. Read it before authoring.

## Layout

```
papers/
  README.md
  REFERENCES.md
  package.json
  scripts/
    gen-bib.mjs      # sources.ts  -> refs.bib          (generated, gitignored)
    gen-tex.mjs      # paper.json  -> main.tex + body stubs (only fills missing files)
    gen-index.mjs    # paper.json  -> ../frontend/src/papers-index.ts (committed)
    gen-versions.mjs # git history -> ../frontend/src/papers-versions.ts (build-time, gitignored)
    backfill-paper-pdfs.sh # one-time manual seed of historical PDFs onto paper-pdfs
    zenodo-publish.mjs     # drive Zenodo's REST API (used by the zenodo workflow)
  <slug>/
    paper.json       # the paper's metadata (title, authors, sections, cites, abstract)
    main.tex         # the document (hand-written prose after scaffolding)
    body/*.tex       # one file per section
```

## Authoring a paper

1. **Create `papers/<slug>/paper.json`.** It declares the paper's metadata:

   ```json
   {
     "slug": "my-paper",
     "title": "A Concise, Honest Title",
     "authors": [{ "name": "A. Researcher", "affiliation": "Independent researcher", "orcid": "" }],
     "date": "2026-07-07",
     "keywords": ["self-replication", "material closure"],
     "sections": ["Introduction", "Method", "Discussion"],
     "cites": ["nasa-cp-2255-1980", "tsiolkovsky-1903"],
     "abstract": "A faithful summary in plain language."
   }
   ```

   Every id in `cites` must exist in `sources.ts`; `gen-index.mjs` fails hard if one
   does not. If a number you want to state has no source there, do not state it
   (CLAUDE.md 1).

2. **Scaffold** (from inside `papers/`):

   ```bash
   npm run gen:bib                    # writes refs.bib from sources.ts
   node scripts/gen-tex.mjs my-paper  # scaffolds main.tex + body/*.tex stubs
   ```

   `gen-tex.mjs` only ever creates files that are missing - it never overwrites your
   `main.tex` or any body file you have already written. So run it once to lay down
   the skeleton, then edit freely.

3. **Edit `body/*.tex`.** Write the prose. Use `\cite{<id>}` for every quantitative
   claim, with the id of a source in `sources.ts`. Keep the declared `cites` in
   `paper.json` and the ids you actually cite in exact agreement (RULES.md R3). Keep
   the typography plain: ASCII hyphen only, no em-dash, no emoji (CLAUDE.md 5); LaTeX
   numeric ranges use a single hyphen, e.g. `90-96\%`.

4. **Validate and index.** Once the prose is written, run `npm run check` - it
   validates the cites (R3), the abstract (R4), and the typography (R5), and refreshes
   `../frontend/src/papers-index.ts`. Run it after every `paper.json` change so the
   index stays in sync. (It runs `gen:index` after the prose exists, because R3
   requires the declared and used cites to match.)

## The generator workflow, in one line

`sources.ts` (source of truth) -> `gen-bib` -> `refs.bib`; `paper.json` -> `gen-tex`
-> `main.tex`/`body`; all `paper.json` -> `gen-index` -> `papers-index.ts` (committed,
consumed by the frontend). `npm run gen` runs bib + index together.

## Building the PDF (IEEEtran)

The papers use the `IEEEtran` document class. It ships in the full
[TeX Live](https://tug.org/texlive/) distribution, so a standard `texlive-full`
install already has it. The canonical package is on CTAN:
<https://ctan.org/pkg/ieeetran> (license: LPPL 1.3). No manual download is needed on
a full TeX Live install.

Build a paper locally with `latexmk` (needs bibtex for the bibliography):

```bash
cd papers
npm run gen:bib
latexmk -pdf -cd electronics-wall/main.tex
```

`npm run build` wraps that command and degrades gracefully (prints a note) when
`latexmk` is not installed, since CI is what produces the published PDF.

## How PDFs are published

CI compiles each paper and copies the resulting `<slug>.pdf` to the site build under
`papers/<slug>.pdf` (the "latest" alias). `papers-index.ts` records that path in each
`PaperMeta.pdf`, so the frontend can link to the compiled PDF. Build artifacts
(`refs.bib`, `doi.tex`, `*.pdf`, `*.aux`, and friends) are gitignored - only the
sources (`paper.json`, `*.tex`) and the committed `papers-index.ts` live in the repo.

## Every version is published (issue #7)

A **version** is every commit whose diff touches `papers/<slug>/` - git history is the
version list, no manual tagging. `scripts/gen-versions.mjs` derives that list at build
time (it cannot be committed: its newest entry names the current commit's own SHA) and
writes the gitignored `frontend/src/papers-versions.ts`, which the papers surface reads
to show a per-paper "Versions" list.

Rendered history is kept out of git on an **orphan `paper-pdfs` branch** (binaries out
of the main tree, and - unlike a GitHub Release - it never triggers the repo-level
Zenodo webhook). The deploy (`pages.yml`) archives each freshly built PDF there at
`<slug>/<shortSha>.pdf` (immutable: an already-archived version is never rewritten or
recompiled), then assembles every archived PDF into the site at
`/papers/<slug>/<shortSha>.pdf`. A version with no archived PDF links its frozen source
on GitHub instead.

Versions that predate this feature can be seeded once with
`scripts/backfill-paper-pdfs.sh` (a manual, best-effort recompile of history - the only
time old LaTeX is ever recompiled; the pipeline never does). Run it once with push
access; versions that fail to compile are logged and simply link their source.

## Per-paper Zenodo DOI (issue #8)

Each paper can get its **own** Zenodo concept DOI (independent of the whole-repo DOI in
[`CITATION.cff`](../CITATION.cff), which stays as the software citation). The `zenodo`
workflow drives Zenodo's REST API directly, one deposition per paper, minting a fresh
version DOI per run under a stable concept DOI. It is **manual and gated** - it runs only
when you trigger it and only against **sandbox.zenodo.org** until a token is present.

To use it:

1. Create a token at
   <https://sandbox.zenodo.org/account/settings/applications/tokens/new/> with scopes
   `deposit:write` and `deposit:actions`.
2. Add it as the repo Actions secret **`ZENODO_SANDBOX_TOKEN`**.
3. Run the **zenodo** workflow (Actions tab -> zenodo -> Run workflow -> pick a paper).
   It reserves the DOI, typesets the paper with the DOI printed on it, uploads the PDF
   plus a reproducibility zip, publishes, and opens a **PR** writing the sandbox DOI
   into `paper.json` (`zenodo_sandbox_*`) and regenerating `papers-index.ts`. Merge the
   PR; the site then shows the DOI, labelled "(sandbox)".

Graduating to production later is additive: add a `ZENODO_TOKEN` secret and point
`ZENODO_BASE` at `https://zenodo.org/api`. Production identifiers are stored under
separate `zenodo_*` keys, so the sandbox and production state never collide. The deposit
license defaults to the repo's research-prose license (CC BY-NC-ND 4.0); set
`paper.license` (an SPDX id) to override.

## License

The written research (prose in `*.tex` and this Markdown) is licensed
**CC BY-NC-ND 4.0** per the repository's [`LICENSE-DOCS`](../LICENSE-DOCS). Cite it
with attribution; no commercial use and no derivative or altered versions. The
`IEEEtran` class itself is third-party (LPPL 1.3) and is not redistributed here.
