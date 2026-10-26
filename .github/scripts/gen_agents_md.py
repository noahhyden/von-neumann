#!/usr/bin/env python3
"""Generates each directory's AGENTS.md from the AGENTS.d/ beside it (one file per rule, so two branches adding rules never conflict); ported from pivi. Usage: --write or --check."""

from __future__ import annotations

import argparse
import difflib
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT_HEADER_REQUIRED = "."

PRUNE_DIRS = frozenset(
    {
        ".git",
        ".claude",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        "target",
        "site-packages",
    }
)

BANNER = (
    "<!-- GENERATED from AGENTS.d/ by .github/scripts/gen_agents_md.py - "
    "do not edit; add or edit a file under AGENTS.d/ instead. -->"
)

PART_RE = re.compile(r"^\d{3}-[a-z0-9-]+\.md$")


def discover_roots() -> list[str]:
    """Every directory holding an AGENTS.d/, repo-relative POSIX, sorted - a rule lives beside the code it governs."""
    roots: list[str] = []
    for dirpath, dirnames, _filenames in os.walk(REPO):
        if "AGENTS.d" in dirnames:
            roots.append(Path(dirpath).relative_to(REPO).as_posix())
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS and d != "AGENTS.d"]
    return sorted(roots)


def parts(root: Path) -> list[Path]:
    """Every AGENTS.d part, header first then rules by filename; the name pattern is enforced so a stray note cannot be silently spliced into the published guide."""
    d = root / "AGENTS.d"
    if not d.is_dir():
        return []
    entries = sorted(d.iterdir(), key=lambda p: p.name)
    strays = [e.name for e in entries if not (e.is_file() and PART_RE.match(e.name))]
    if strays:
        raise SystemExit(
            f"{d}: not a valid part: {', '.join(strays)}\n"
            "  Parts are NNN-<kebab-slug>.md files (NNN is a 3-digit sort key), "
            "directly in this directory. Subdirectories are not read."
        )
    has_header = bool(entries) and entries[0].name == "000-header.md"
    if not has_header and _rel(root) == ROOT_HEADER_REQUIRED:
        raise SystemExit(f"{d}: missing 000-header.md")
    return entries


def _rel(root: Path) -> str:
    """`root` relative to REPO, POSIX, with the repo root itself as "."."""
    rel = root.resolve().relative_to(REPO.resolve())
    return "." if str(rel) == "." else rel.as_posix()


def _synth_header(rel: str, root: Path) -> list[str]:
    """The two-line header synthesized for a nested root with no authored 000-header.md."""
    link = Path(os.path.relpath(REPO / "AGENTS.md", start=root)).as_posix()
    return [
        f"# Agent rules for `{rel}/`",
        f"> Scoped rules for `{rel}/`. Repo-wide rules: [`{link}`]({link}).",
    ]


def _depth(rel: str) -> int:
    """Path-segment depth, the repo root being 0."""
    return 0 if rel == "." else rel.count("/") + 1


def _nearest_ancestor(d: str, all_roots: list[str]) -> str:
    """The closest discovered root that strictly encloses `d`."""
    candidates = [r for r in all_roots if r != d and (r == "." or d.startswith(r + "/"))]
    return max(candidates, key=_depth)


def _descendants_of(rel: str, all_roots: list[str]) -> list[str]:
    """Roots whose nearest enclosing root is exactly `rel`, so a nested root is indexed by exactly one ancestor."""
    prefix = "" if rel == "." else rel + "/"
    return sorted(
        r
        for r in all_roots
        if r != rel and (rel == "." or r.startswith(prefix)) and _nearest_ancestor(r, all_roots) == rel
    )


def _headings(rendered_md: str) -> list[str]:
    """Every `## ` heading in a rendered document, its own nested index excluded."""
    out = [ln[3:] for ln in rendered_md.split("\n") if ln.startswith("## ")]
    return [h for h in out if h != "Nested rule sets"]


def _nested_index(rel: str, all_roots: list[str], rendered: dict[str, str]) -> str:
    """The "## Nested rule sets" block for `rel`, or "" when it has no descendants."""
    descendants = _descendants_of(rel, all_roots)
    if not descendants:
        return ""
    lines = [
        "## Nested rule sets",
        "",
        "<!-- GENERATED index of AGENTS.d directories below this one - do not edit. -->",
        "",
        "Rules scoped to a subtree live beside the code they govern. Read the ones that cover the files you are touching.",
        "",
    ]
    for d in descendants:
        d_rel = d if rel == "." else d[len(rel) + 1 :]
        link = f"{d_rel}/AGENTS.md"
        lines.append(f"- [`{link}`]({link})")
        lines.extend(f"  - {heading}" for heading in _headings(rendered.get(d, "")))
    return "\n".join(lines)


def render(root: Path, all_roots: list[str] | None = None, rendered: dict[str, str] | None = None) -> str:
    """Renders `root`'s AGENTS.md from its AGENTS.d/ parts."""
    entries = parts(root)
    if not entries:
        return ""
    rel = _rel(root)
    blocks = [p.read_text().rstrip("\n") for p in entries]
    has_header = entries[0].name == "000-header.md"
    if not has_header:
        blocks = _synth_header(rel, root) + blocks
    header_count = 1 if has_header else 2
    head_lines = blocks[0].split("\n")
    cut = 1 if head_lines and head_lines[0].startswith("# ") else 0
    blocks[0] = "\n".join(head_lines[:cut] + ["", BANNER] + head_lines[cut:])
    body = "\n\n".join(blocks[:header_count] + blocks[header_count:])
    if all_roots is not None:
        nested = _nested_index(rel, all_roots, rendered or {})
        if nested:
            body += "\n\n" + nested
    return body + "\n"


def render_all(roots: list[str]) -> dict[str, str]:
    """Renders every discovered root, deepest first, since a root's nested index reads its descendants' rendered headings."""
    rendered: dict[str, str] = {}
    for rel in sorted(roots, key=_depth, reverse=True):
        rendered[rel] = render(REPO if rel == "." else REPO / rel, roots, rendered)
    return rendered


def main() -> int:
    """Write or check every AGENTS.md against its AGENTS.d/."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="write AGENTS.md files")
    ap.add_argument("--check", action="store_true", help="fail if any is stale")
    args = ap.parse_args()
    if not (args.write or args.check):
        ap.error("pass --write or --check")

    roots = discover_roots()
    if not roots:
        print("gen_agents_md: no AGENTS.d/ found - refusing to pass vacuously")
        return 1
    rendered = render_all(roots)

    stale: list[str] = []
    for rel in roots:
        target = (REPO if rel == "." else REPO / rel) / "AGENTS.md"
        want = rendered[rel]
        have = target.read_text() if target.exists() else ""
        rel_path = target.relative_to(REPO)
        if want == have:
            continue
        if args.write:
            target.write_text(want)
            print(f"wrote {rel_path} ({len(want.splitlines())} lines from AGENTS.d/)")
        else:
            stale.append(str(rel_path))
            diff = difflib.unified_diff(
                have.splitlines(), want.splitlines(),
                f"{rel_path} (committed)", f"{rel_path} (generated)", lineterm="",
            )
            print("\n".join(list(diff)[:40]))

    if stale:
        print(
            f"\n{len(stale)} generated file(s) do not match AGENTS.d/: " + ", ".join(stale)
            + "\nRegenerate with: python3 .github/scripts/gen_agents_md.py --write"
            "\nA hand edit to AGENTS.md is the usual cause - make it in AGENTS.d/ instead."
        )
        return 1
    print(f"gen_agents_md: {len(roots)} root(s) match their AGENTS.d/ directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
