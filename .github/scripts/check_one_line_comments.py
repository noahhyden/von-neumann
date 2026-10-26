#!/usr/bin/env python3
"""Explanation in code is capped at ONE line; the rest belongs in an AGENTS.d rule, a module README or REFERENCES.md - ported from pivi without its baseline ratchet, so this tree is enforced at zero and a new violation fails here."""

from __future__ import annotations

import argparse
import ast
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SKIP_PREFIXES: tuple[str, ...] = (
    "node_modules/",
    ".venv/",
    "target/",
)

PRAGMAS: tuple[str, ...] = (
    "noqa",
    "type: ignore",
    "pragma:",
    "ruff:",
    "mypy:",
    "nosec",
    "pylint:",
    "fmt:",
    "eslint-disable",
    "@ts-expect-error",
    "@ts-ignore",
    "@vitest-environment",
    "prettier-ignore",
    "biome-ignore",
    "DO NOT EDIT",
    "AUTO-GENERATED",
    "SPDX-",
    "Copyright",
    "!/usr/bin",
    "-*- coding",
)

GENERATED_MARKERS = re.compile(
    r"DO NOT EDIT|AUTO-?GENERATED|THIS FILE IS GENERATED|@generated|Generated\s*-\s*see",
    re.IGNORECASE,
)


def is_skipped(path: str) -> bool:
    """True when `path` is exempt by prefix."""
    return any(path.startswith(p) for p in SKIP_PREFIXES)


def is_generated(text: str) -> bool:
    """True when the first 40 lines claim the file is generated."""
    return bool(GENERATED_MARKERS.search("\n".join(text.split("\n")[:40])))


def has_pragma(lines: list[str]) -> bool:
    """True when any line in the run carries a tooling pragma."""
    return any(p in line for line in lines for p in PRAGMAS)


def python_violations(text: str) -> list[tuple[int, str]]:
    """Multi-line docstrings and multi-line standalone comment runs."""
    out: list[tuple[int, str]] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = node.body
        if not body:
            continue
        first = body[0]
        if not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            continue
        span = first.end_lineno - first.lineno + 1
        if span > 1:
            name = getattr(node, "name", "<module>")
            out.append((first.lineno, f"docstring spans {span} lines ({name})"))

    lines = text.split("\n")
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return out
    standalone = sorted(
        t.start[0]
        for t in toks
        if t.type == tokenize.COMMENT and not lines[t.start[0] - 1][: t.start[1]].strip()
    )
    out.extend(_runs(standalone, lines))
    return out


def ts_violations(text: str) -> list[tuple[int, str]]:
    """Multi-line JSDoc/block comments and multi-line `//` runs."""
    out: list[tuple[int, str]] = []
    lines = text.split("\n")
    standalone: list[int] = []
    in_block = False
    block_start = 0
    block_lines: list[str] = []
    for i, raw in enumerate(lines, start=1):
        s = raw.strip()
        if in_block:
            block_lines.append(raw)
            if "*/" in s:
                in_block = False
                if len(block_lines) > 1 and not has_pragma(block_lines):
                    out.append((block_start, f"block comment spans {len(block_lines)} lines"))
            continue
        if s.startswith("/*"):
            block_lines = [raw]
            block_start = i
            if "*/" not in s[2:]:
                in_block = True
            continue
        if s.startswith("//"):
            standalone.append(i)
    out.extend(_runs(standalone, lines))
    return out


BLOCK_SCALAR_RE = re.compile(r"^(\s*)\S.*:\s*[|>][+\-0-9]*\s*(#.*)?$")


def yaml_violations(text: str) -> list[tuple[int, str]]:
    """Multi-line standalone `#` comment runs, skipping block-scalar bodies (`run: |` scripts) where `#` is literal content, not a YAML comment."""
    out: list[tuple[int, str]] = []
    lines = text.split("\n")
    standalone: list[int] = []
    in_block = False
    block_parent_indent = 0
    for i, raw in enumerate(lines, start=1):
        if in_block:
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip(" "))
            if stripped == "" or indent > block_parent_indent:
                continue
            in_block = False
        m = BLOCK_SCALAR_RE.match(raw)
        if m:
            block_parent_indent = len(m.group(1))
            in_block = True
            continue
        if raw.strip().startswith("#"):
            standalone.append(i)
    out.extend(_runs(standalone, lines))
    return out


TRIPLE_QUOTES: tuple[str, ...] = ('"""', "'''")


def _toml_scan_line(raw: str, in_string: bool, delim: str) -> tuple[bool, str]:
    """Walk one line left to right and return the triple-quoted-string state at its end."""
    i = 0
    while i < len(raw):
        if in_string:
            hit = raw.find(delim, i)
            if hit == -1:
                return True, delim
            in_string, delim, i = False, "", hit + len(delim)
            continue
        ch = raw[i]
        if ch == "#":
            return False, ""
        for d in TRIPLE_QUOTES:
            if raw.startswith(d, i):
                in_string, delim, i = True, d, i + len(d)
                break
        else:
            if ch in ("'", '"'):
                close = raw.find(ch, i + 1)
                i = len(raw) if close == -1 else close + 1
                continue
            i += 1
    return in_string, delim


def toml_violations(text: str) -> list[tuple[int, str]]:
    """Multi-line standalone `#` comment runs; TOML has no docstrings, so only the comment-run half applies, and a `#` inside an open triple-quoted string is literal content, not a comment."""
    out: list[tuple[int, str]] = []
    lines = text.split("\n")
    standalone: list[int] = []
    in_string = False
    delim = ""
    for i, raw in enumerate(lines, start=1):
        if in_string:
            in_string, delim = _toml_scan_line(raw, in_string, delim)
            continue
        if raw.strip().startswith("#"):
            standalone.append(i)
            continue
        in_string, delim = _toml_scan_line(raw, in_string, delim)
    out.extend(_runs(standalone, lines))
    return out


def _runs(linenos: list[int], lines: list[str]) -> list[tuple[int, str]]:
    """Consecutive comment lines grouped into runs longer than one line."""
    out: list[tuple[int, str]] = []
    run: list[int] = []
    for n in linenos:
        if run and n == run[-1] + 1:
            run.append(n)
            continue
        if len(run) > 1:
            body = [lines[k - 1] for k in run]
            if not has_pragma(body):
                out.append((run[0], f"comment run spans {len(run)} lines"))
        run = [n]
    if len(run) > 1:
        body = [lines[k - 1] for k in run]
        if not has_pragma(body):
            out.append((run[0], f"comment run spans {len(run)} lines"))
    return out


def scan(paths: list[str]) -> dict[str, list[tuple[int, str]]]:
    """Violations per path, skipping exempt and generated files."""
    found: dict[str, list[tuple[int, str]]] = {}
    for rel in paths:
        if is_skipped(rel) or not rel.endswith((".py", ".ts", ".tsx", ".yml", ".yaml", ".toml")):
            continue
        full = REPO_ROOT / rel
        if not full.is_file():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if is_generated(text):
            continue
        if rel.endswith(".py"):
            hits = python_violations(text)
        elif rel.endswith((".yml", ".yaml")):
            hits = yaml_violations(text)
        elif rel.endswith(".toml"):
            hits = toml_violations(text)
        else:
            hits = ts_violations(text)
        if hits:
            found[rel] = hits
    return found


def all_source_paths() -> list[str]:
    """Every tracked .py/.ts/.tsx/.yml/.yaml/.toml path."""
    out = subprocess.run(
        ["git", "ls-files", "*.py", "*.ts", "*.tsx", "*.yml", "*.yaml", "*.toml"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return [p for p in out.split("\n") if p]


def main() -> int:
    ap = argparse.ArgumentParser(description="Explanation in code is capped at ONE line.")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args()

    paths = args.files or all_source_paths()
    scanned = [p for p in paths if not is_skipped(p)]
    if not scanned:
        print("one-line-comments: no files matched - refusing to pass vacuously", file=sys.stderr)
        return 2
    found = scan(paths)
    total = sum(len(v) for v in found.values())
    if not found:
        print(f"one-line-comments: OK - {len(scanned)} file(s) scanned, 0 violation(s)")
        return 0
    print("one-line-comments: explanation in code is capped at ONE line.\n")
    for path in sorted(found):
        print(f"  {path}: {len(found[path])} violation(s)")
        for lineno, why in found[path][:4]:
            print(f"      {path}:{lineno}  {why}")
    print(
        f"\n{total} violation(s) in {len(found)} file(s) ({len(scanned)} scanned).\n"
        "A module, class or function gets a one-line docstring or none, and a run of\n"
        "standalone comments is one line. Move the rest into an AGENTS.d/ rule, the\n"
        "module README, or REFERENCES.md - markdown is never scanned. A run carrying a\n"
        "pragma (noqa / type: ignore / eslint-disable) is exempt."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
