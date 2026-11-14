#!/usr/bin/env python3
"""Regenerates the modules/README.md inventory and each module's submodule table. Usage: no flag checks, --write rewrites."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODULES = REPO / "modules"
README = MODULES / "README.md"
BEGIN = "<!-- BEGIN GENERATED:inventory -->"
END = "<!-- END GENERATED:inventory -->"
SUB_BEGIN = "<!-- BEGIN GENERATED:submodules -->"
SUB_END = "<!-- END GENERATED:submodules -->"
DOCSTRING = re.compile(r'^\s*"""(.+?)"""', re.S)


def _module_dirs() -> list[Path]:
    """Every directory under modules/ that carries a pyproject.toml, sorted."""
    return sorted(p for p in MODULES.iterdir() if (p / "pyproject.toml").is_file())


def render() -> str:
    """The generated block body: a count line and the table."""
    rows = []
    for d in _module_dirs():
        proj = tomllib.loads((d / "pyproject.toml").read_text())["project"]
        purpose = " ".join(proj.get("description", "-").split()).replace("|", "\\|")
        rows.append(f"| `{d.name}/` | `{proj['name']}` | {purpose} |")
    head = [f"`modules/` has **{len(rows)}** modules.", "", "| Module | Package | Purpose |", "|---|---|---|"]
    return "\n".join(head + rows)


def _subpackages(module: Path) -> list[Path]:
    """Importable subpackages of a module's single src/<pkg>/, sorted; empty when it has none."""
    src = module / "src"
    roots = [p for p in src.iterdir() if p.is_dir() and not p.name.endswith(".egg-info")] if src.is_dir() else []
    if len(roots) != 1:
        return []
    return sorted(p for p in roots[0].iterdir() if p.is_dir() and (p / "__init__.py").is_file())


def _purpose(pkg: Path) -> str:
    """A subpackage's one-line docstring with any leading `name - ` stripped."""
    m = DOCSTRING.match((pkg / "__init__.py").read_text())
    text = " ".join(m.group(1).split()) if m else "-"
    return re.sub(rf"^{re.escape(pkg.name).replace('_', '[-_]')}\s+-\s+", "", text).rstrip(".")


def render_submodules(module: Path) -> str:
    """The generated block body for one module's submodule table."""
    subs = _subpackages(module)
    head = [
        f"`{module.name}` has **{len(subs)}** submodules.",
        "",
        "| Submodule | Purpose | Detail |",
        "|---|---|---|",
    ]
    rows = [
        f"| `{p.name}` | {_purpose(p).replace('|', chr(92) + '|')} | [docs/{p.name}.md](docs/{p.name}.md) |"
        for p in subs
    ]
    return "\n".join(head + rows)


def _apply(path: Path, begin: str, end: str, body: str, write: bool) -> tuple[int, bool]:
    """Rewrite or check one marked block; returns (exit code, whether it was stale)."""
    text = path.read_text()
    rel = path.relative_to(REPO)
    if begin not in text or end not in text:
        print(f"gen_modules_readme: markers missing in {rel}")
        return 1, False
    pre, rest = text.split(begin, 1)
    want = f"{pre}{begin}\n{body}\n{end}{rest.split(end, 1)[1]}"
    if want == text:
        return 0, False
    if write:
        path.write_text(want)
        print(f"wrote {rel}")
        return 0, True
    print(f"{rel} is stale. Regenerate with: make modules-readme")
    return 1, True


def _targets() -> list[tuple[Path, str, str, str]]:
    """Every marked block this generator owns: the modules index, then each module's submodule table."""
    out = [(README, BEGIN, END, render())]
    for d in _module_dirs():
        readme = d / "README.md"
        if readme.is_file() and SUB_BEGIN in readme.read_text():
            out.append((readme, SUB_BEGIN, SUB_END, render_submodules(d)))
    return out


def main() -> int:
    """Write or check every generated block."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    codes, stale = [], False
    for path, begin, end, body in _targets():
        code, was_stale = _apply(path, begin, end, body, args.write)
        codes.append(code)
        stale = stale or was_stale
    if any(codes):
        return 1
    if not stale:
        print("gen_modules_readme: every generated block is fresh.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
