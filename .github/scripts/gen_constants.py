#!/usr/bin/env python3
"""Generates vn_core/constants.py and frontend/src/constants.ts from constants.toml. Usage: no flag checks, --write rewrites."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "modules/core/src/vn_core/constants.toml"
PY_OUT = REPO / "modules/core/src/vn_core/constants.py"
TS_OUT = REPO / "frontend/src/constants.ts"
BANNER = "constants.toml is the single source; regenerate with `make constants`, do not edit by hand."
REQUIRED = ("value", "unit", "source", "basis", "verdict")
# Derived names are computed from the table rather than listed in it, so there is never a second literal to drift.
DERIVED_PY = '\nSECONDS_PER_JULIAN_YEAR: float = DAYS_PER_JULIAN_YEAR * SECONDS_PER_DAY\n'
DERIVED_TS = "\nexport const SECONDS_PER_JULIAN_YEAR = DAYS_PER_JULIAN_YEAR * SECONDS_PER_DAY;\n"


def load() -> dict[str, dict[str, object]]:
    """The constants table, validated: required fields present, and each literal parses and round-trips."""
    table = tomllib.loads(SOURCE.read_text())
    for name, entry in table.items():
        missing = [k for k in REQUIRED if not entry.get(k)]
        if missing:
            raise ValueError(f"{name} is missing {missing}; CLAUDE.md section 1 requires a source and a basis")
        literal = entry["value"]
        if not isinstance(literal, str):
            raise ValueError(f"{name}.value must be a quoted literal so the digits stay identical to the source")
        # Round-trip or the emitted digits would not be the number anyone cited.
        if float(repr(float(literal))) != float(literal):
            raise ValueError(f"{name}.value {literal!r} does not round-trip through float")
    return table


def render_py(table: dict[str, dict[str, object]]) -> str:
    """The generated Python module."""
    lines = [f'"""Defined physical constants. {BANNER}"""', "", "from __future__ import annotations", ""]
    for name, e in table.items():
        lines += ["", f"# {e['basis']} [{e['unit']}] {e['source']}", f"{name}: float = {e['value']}"]
    lines.append(DERIVED_PY.rstrip("\n"))
    names = sorted([*table, "SECONDS_PER_JULIAN_YEAR"])
    lines += ["", f"__all__ = {names!r}", ""]
    return "\n".join(lines)


def render_ts(table: dict[str, dict[str, object]]) -> str:
    """The generated TypeScript mirror, so a constant cannot drift across the language boundary."""
    lines = [f"// Defined physical constants. {BANNER}", ""]
    for name, e in table.items():
        lines += [f"// {e['basis']} [{e['unit']}] {e['source']}", f"export const {name} = {e['value']};", ""]
    lines.append(DERIVED_TS.strip())
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Write or check both generated files."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    table = load()
    stale = []
    for path, body in ((PY_OUT, render_py(table)), (TS_OUT, render_ts(table))):
        if path.is_file() and path.read_text() == body:
            continue
        stale.append(path)
        if args.write:
            path.write_text(body)
            print(f"wrote {path.relative_to(REPO)}")
    if not stale:
        print("gen_constants: generated constants are fresh.")
        return 0
    if args.write:
        return 0
    for path in stale:
        print(f"{path.relative_to(REPO)} is stale. Regenerate with: make constants")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
