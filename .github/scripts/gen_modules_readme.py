#!/usr/bin/env python3
"""Regenerates the inventory table in modules/README.md. Usage: no flag checks, --write rewrites."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODULES = REPO / "modules"
README = MODULES / "README.md"
BEGIN = "<!-- BEGIN GENERATED:inventory -->"
END = "<!-- END GENERATED:inventory -->"


def loc(src: Path) -> int:
    """Lines across every .py file under src."""
    return sum(len(p.read_text().splitlines()) for p in src.rglob("*.py") if "__pycache__" not in p.parts)


def render() -> str:
    """The generated block body: a count line and the table."""
    rows = []
    for d in sorted(p for p in MODULES.iterdir() if (p / "pyproject.toml").is_file()):
        proj = tomllib.loads((d / "pyproject.toml").read_text())["project"]
        tests = len(list((d / "tests").rglob("test_*.py")))
        purpose = " ".join(proj.get("description", "-").split()).replace("|", "\\|")
        rows.append(f"| `{d.name}/` | `{proj['name']}` | {loc(d / 'src')} | {tests} | {purpose} |")
    head = [f"`modules/` has **{len(rows)}** modules.", "", "| Module | Package | LOC | Tests | Purpose |", "|---|---|---|---|---|"]
    return "\n".join(head + rows)


def main() -> int:
    """Write or check the generated block."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    text = README.read_text()
    if BEGIN not in text or END not in text:
        print(f"gen_modules_readme: markers missing in {README.relative_to(REPO)}")
        return 1
    pre, rest = text.split(BEGIN, 1)
    post = rest.split(END, 1)[1]
    want = f"{pre}{BEGIN}\n{render()}\n{END}{post}"
    if want == text:
        print("gen_modules_readme: modules/README.md is fresh.")
        return 0
    if args.write:
        README.write_text(want)
        print("wrote modules/README.md")
        return 0
    print("modules/README.md is stale. Regenerate with: make modules-readme")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
