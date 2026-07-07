# References

Module hygiene (CLAUDE.md 4) requires every module to carry a `REFERENCES.md`.
This one is short by design.

**This module introduces no new numbers.** It is a paper-authoring pipeline, not a
model. Any quantitative claim in a paper here must already appear, with its source,
in the project's findings and the module that produced it - a paper may only restate
sourced results, never invent them (CLAUDE.md 1).

**The single bibliography source of truth is [`frontend/src/sources.ts`](../frontend/src/sources.ts).**
That typed `SOURCES` array consolidates every module's `REFERENCES.md` into one
sourced list. The BibTeX file `refs.bib` is *generated* from it by
`scripts/gen-bib.mjs` (keyed by each source's `id`, so `\cite{id}` in a paper matches
the site's citation id). `refs.bib` is therefore a build artifact - it is gitignored
and never hand-edited. To add or correct a source, edit `sources.ts` (and the
originating module's `REFERENCES.md`), then regenerate.
