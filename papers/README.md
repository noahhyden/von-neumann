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

   An optional `"draft": true` keeps the paper out of the site: it is still validated
   and typeset, but `gen-index.mjs` leaves it out of `papers-index.ts`,
   `gen-versions.mjs` emits no version list for it, and the deploy publishes none of
   its PDFs. Remove the key to publish.

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

## Script notes

- All scripts resolve paths from `import.meta.url` (run from anywhere), except `gen-index.mjs`, run from inside `papers/`. None introduces numbers (CLAUDE.md 1).
- **gen-bib.mjs**: writes `refs.bib` from `frontend/src/sources.ts`, keyed by source `id`. Needs Node >=22.6 (native type stripping), so it imports the `.ts` with no build step. A `note` flags sources cited by reference with no online link.
  - Names are emitted "Last, First" (not display order) so BibTeX finds the surname: IEEEtran still prints "A. Nicholson", natbib can form "(Nicholson, 2013)".
  - A token not starting with initials (e.g. "International Astronomical Union") is brace-wrapped verbatim so its last word is not read as a surname.
  - Affiliations, "(eds.)" and suffixes are stripped; a trailing "et al." or "and others" becomes BibTeX `others`.
- **gen-index.mjs**: writes the committed `frontend/src/papers-index.ts` (pure data, no pimas, Layer A) after checking every declared cite resolves in `sources.ts`.
  - Once `main.tex` exists, declared cites must equal the cites used in `main.tex` + `body/*.tex` (`\cite`, `\citep`, `\citet`, starred forms, `[pre][post]` notes), so the site's reference list is an exact manifest.
  - The LaTeX abstract must equal `paper.json.abstract` after folding markup, "N percent" / "N\%", and the thin-space `{,}` (`200{,}000` vs `200,000`).
  - The Zenodo DOI (issue #8) is written back to `paper.json`; production beats sandbox, and a sandbox-only DOI is shown flagged "(sandbox)".
- **gen-tex.mjs** `<slug>`: only creates missing files, never overwrites `main.tex` or `body/<section>.tex`.
- **gen-versions.mjs**: a version is every commit touching `papers/<slug>/` (issue #7). The output `papers-versions.ts` is gitignored and built every time because its newest entry holds the current commit's own SHA, which would contradict the `git diff --exit-code frontend/src/papers-index.ts` gate in `ci.yml` if committed.
  - Git runs from the repo root; log fields are `--date=short` (YYYY-MM-DD, matching the site), full sha, short sha, subject.
  - `archivedPdfs` lists `<slug>/<shortSha>.pdf` on the `paper-pdfs` orphan branch via `git ls-tree`, trying `origin/paper-pdfs` (CI), then `paper-pdfs` (local); `PAPER_PDFS_REF` overrides. If none resolves (shallow clone, no branch yet) the set is empty and each version falls back to a link to its frozen source on GitHub, so it can run before CI assembles the archive.
- **zenodo-publish.mjs** (issue #8): the repo's one concept DOI `10.5281/zenodo.21249296` ([`CITATION.cff`](../CITATION.cff)) comes from the GitHub-Zenodo integration, which archives the whole monorepo and cannot scope to a subdirectory. This script drives the REST API instead (<https://developers.zenodo.org>), one deposition per paper.
  - **reserve**: create the deposition or a new version, read `prereserve_doi.doi`, write `papers/<slug>/doi.tex`, stash the deposition id and `links.bucket` in a state file. **finalize**: upload the DOI-stamped PDF and reproducibility zip, set metadata from `paper.json`, publish, write minted DOIs back. Two phases so the DOI is printed on the PDF before upload.
  - API fields used: `actions/newversion` -> `links.latest_draft`, `actions/publish`, `conceptrecid`/`conceptdoi`. Bearer auth with scopes `deposit:write` + `deposit:actions`.
  - `ZENODO_BASE` picks the environment (`sandbox.zenodo.org/api` by default); state keys are `zenodo_sandbox_*` vs `zenodo_*` so sandbox never pollutes production.
  - `node --test papers/scripts/zenodo-publish.test.mjs` checks the network-free metadata core against `paper.json`.
- **backfill-paper-pdfs.sh**: one-time manual seed of `paper-pdfs` with PDFs of historical versions (not in CI; `pages.yml` archives new ones). It is the only place old LaTeX is recompiled, best-effort, because old LaTeX against old module state is brittle; a failed version is logged and falls back to the source link. Needs git, node (>=22.6), uv, latexmk and IEEEtran (`texlive-publishers`), and push access to origin.

```bash
papers/scripts/backfill-paper-pdfs.sh                       # all papers, all versions
papers/scripts/backfill-paper-pdfs.sh coordination-tax      # one paper
DRY_RUN=1 papers/scripts/backfill-paper-pdfs.sh             # compile + stage, do not push
```

## License

The written research (prose in `*.tex` and this Markdown) is licensed
**CC BY-NC-ND 4.0** per the repository's [`LICENSE-DOCS`](../LICENSE-DOCS). Cite it
with attribution; no commercial use and no derivative or altered versions. The
`IEEEtran` class itself is third-party (LPPL 1.3) and is not redistributed here.
