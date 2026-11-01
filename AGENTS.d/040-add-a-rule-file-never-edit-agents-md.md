## Add a rule FILE, never edit AGENTS.md

Every `AGENTS.md` is generated from the `AGENTS.d/` beside it and is gitignored: write `<dir>/AGENTS.d/NNN-<slug>.md` - a `## heading` plus ONE body line of at most 255 chars - pre-commit regenerates it on checkout, merge and commit.
