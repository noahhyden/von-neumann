#!/usr/bin/env bash
#
# backfill-paper-pdfs.sh - ONE-TIME, MANUAL seed of the paper-pdfs orphan branch
# with the rendered PDF of every historical paper version (issue #7).
#
# Why this exists, and why it is not in CI: the deploy pipeline (pages.yml) archives
# each version's PDF the moment it is built, so from the day the feature lands
# forward, every new version is captured with no recompilation. But versions that
# predate the feature were never archived. This script closes that gap ONCE by
# checking out each historical commit and compiling it best-effort. It is the single
# accepted "recompile old LaTeX" event; the pipeline itself never recompiles history
# (that is the whole point of the release-archive approach - old LaTeX against old
# module state is brittle, e.g. the coordination-tax figure module did not exist at
# the paper's first commit).
#
# A version that fails to compile (missing figure module, LaTeX error at that SHA) is
# LOUDLY logged and simply left without an archived PDF: the site then links its
# frozen source on GitHub instead. That is honest - rendered history is best-effort;
# source history is complete.
#
# Prerequisites: git, node (>=22.6 for native TS), uv, and a LaTeX toolchain with
# latexmk + the IEEEtran class (texlive-publishers). Run from anywhere inside the
# repo. Requires push access to origin (it pushes the paper-pdfs branch).
#
# Usage:
#   papers/scripts/backfill-paper-pdfs.sh            # all papers, all versions
#   papers/scripts/backfill-paper-pdfs.sh coordination-tax   # one paper
#   DRY_RUN=1 papers/scripts/backfill-paper-pdfs.sh  # compile + stage, do not push
#
# ASCII only, no em-dash (CLAUDE.md 5).

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Which papers to process.
if [ "$#" -gt 0 ]; then
  SLUGS="$*"
else
  SLUGS="$(for d in papers/*/; do b=$(basename "$d"); [ "$b" = "scripts" ] && continue; [ -f "${d}paper.json" ] && echo "$b"; done)"
fi

WORK="$(mktemp -d)"
PPDFS="$WORK/ppdfs"
trap 'git worktree remove --force "$PPDFS" 2>/dev/null; for w in "$WORK"/src-*; do git worktree remove --force "$w" 2>/dev/null; done; rm -rf "$WORK"' EXIT

# --- prepare the paper-pdfs branch worktree (fetch, or create as orphan) -----------
git config user.name  >/dev/null 2>&1 || git config user.name  "backfill"
git config user.email >/dev/null 2>&1 || git config user.email "noreply@example.com"
if git fetch origin paper-pdfs:paper-pdfs 2>/dev/null; then
  git worktree add "$PPDFS" paper-pdfs >/dev/null
else
  echo "no existing paper-pdfs branch; creating it as an orphan"
  git worktree add --detach "$PPDFS" >/dev/null 2>&1
  git -C "$PPDFS" checkout --orphan paper-pdfs >/dev/null 2>&1
  git -C "$PPDFS" rm -rf . >/dev/null 2>&1 || true
fi

built=0; skipped=0; failed=0
FAIL_LOG=""

for slug in $SLUGS; do
  echo ""
  echo "=== $slug ==="
  # Every commit touching this paper, newest first: short sha + subject.
  git log --format='%h %s' -- "papers/${slug}/" | while read -r sha subject; do
    dest="$PPDFS/${slug}/${sha}.pdf"
    if [ -f "$dest" ]; then
      echo "  [skip]  ${sha}  already archived"
      continue
    fi

    src="$WORK/src-${slug}-${sha}"
    if ! git worktree add --detach "$src" "$sha" >/dev/null 2>&1; then
      echo "  [FAIL]  ${sha}  could not check out ($subject)"
      echo "${slug} ${sha} checkout" >> "$WORK/failures"
      continue
    fi

    (
      cd "$src"
      # The paper must exist at this commit (older commits may predate a slug).
      [ -f "papers/${slug}/main.tex" ] || { echo "no main.tex at this commit"; exit 3; }
      # Bibliography from this commit's sources.ts.
      node papers/scripts/gen-bib.mjs >/dev/null 2>&1 || echo "  (gen-bib failed; typeset may miss refs)"
      # Figures, best-effort: the module may not exist at this commit.
      case "$slug" in
        coordination-tax) fmod="swarm";       fcmd="uv run --extra dev python -m experiments.paper_figures" ;;
        electronics-wall) fmod="closure-sim"; fcmd="uv run --extra dev python -m closure_sim.paper_figures" ;;
        *)                fmod="";            fcmd="" ;;
      esac
      if [ -n "$fmod" ] && [ -d "$fmod" ]; then
        ( cd "$fmod" && eval "$fcmd" ) >/dev/null 2>&1 || echo "  (figures best-effort: not built at ${sha})"
      elif [ -n "$fmod" ]; then
        echo "  (figure module ${fmod} absent at ${sha}; typeset without regenerated figures)"
      fi
      # Typeset.
      ( cd "papers/${slug}" && latexmk -pdf -interaction=nonstopmode main.tex ) >/dev/null 2>&1
      [ -f "papers/${slug}/main.pdf" ]
    )
    rc=$?

    if [ "$rc" -eq 0 ] && [ -f "$src/papers/${slug}/main.pdf" ]; then
      mkdir -p "$PPDFS/${slug}"
      cp "$src/papers/${slug}/main.pdf" "$dest"
      echo "  [built] ${sha}  ($subject)"
      echo "built" >> "$WORK/built"
    else
      echo "  [FAIL]  ${sha}  did not produce a PDF ($subject) - will link source instead"
      echo "${slug} ${sha} compile" >> "$WORK/failures"
    fi
    git worktree remove --force "$src" >/dev/null 2>&1
  done
done

# Tally (the while-loop ran in a subshell via the pipe, so counts come from files).
built=$([ -f "$WORK/built" ] && wc -l < "$WORK/built" | tr -d ' ' || echo 0)
failed=$([ -f "$WORK/failures" ] && wc -l < "$WORK/failures" | tr -d ' ' || echo 0)

echo ""
echo "=== summary: ${built} built, ${failed} could not compile (linked to source) ==="
if [ -f "$WORK/failures" ]; then
  echo "versions with no archived PDF (site links their GitHub source):"
  sed 's/^/  /' "$WORK/failures"
fi

# --- commit + push -----------------------------------------------------------------
if [ -z "$(git -C "$PPDFS" status --porcelain)" ]; then
  echo "nothing new to archive."
  exit 0
fi
git -C "$PPDFS" add -A
git -C "$PPDFS" commit -q -m "backfill: seed historical paper PDFs"
if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "DRY_RUN set: committed to the LOCAL paper-pdfs branch but NOT pushed."
  echo "Inspect: git ls-tree -r --name-only paper-pdfs   (re-run without DRY_RUN to push)"
else
  git -C "$PPDFS" push origin paper-pdfs
  echo "pushed paper-pdfs."
fi
