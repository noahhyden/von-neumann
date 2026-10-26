#!/usr/bin/env python3
"""CLAUDE.md section 5: no em-dash (U+2014) and no emoji in tracked text files."""

from __future__ import annotations

import sys
from pathlib import Path

EM_DASH = "—"

# Emoji only. Greek letters, arrows and the math symbols CLAUDE.md allows sit below U+2600 and are deliberately absent.
_EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),
    (0x1F000, 0x1F2FF),
    (0x2600, 0x27BF),
    (0xFE0F, 0xFE0F),
    (0x1F1E6, 0x1F1FF),
)

# The astronomy block sits inside U+2600-U+27BF: CLAUDE.md section 5 names these as meaningful, not decorative.
_ASTRONOMY = frozenset(
    [0x2609, 0x26E2] + list(range(0x263D, 0x2648))
)

# A line may carry this marker when the character is the subject of the code, not decoration (e.g. the regex that enforces this very rule).
PRAGMA = "typography-allow"

# Lock files and binaries carry upstream bytes we do not control.
_SKIP_SUFFIX = {".lock", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".zip", ".bib"}
_SKIP_NAME = {"package-lock.json", "uv.lock", "Cargo.lock"}


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    if cp in _ASTRONOMY:
        return False
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def scan(path: Path) -> list[str]:
    """Return one message per offending line in `path`."""
    if path.name in _SKIP_NAME or path.suffix.lower() in _SKIP_SUFFIX:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
        return []
    out: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        if PRAGMA in line:
            continue
        if EM_DASH in line:
            out.append(f"{path}:{n}: em-dash (U+2014); use a plain ASCII hyphen")
        bad = sorted({c for c in line if is_emoji(c)})
        if bad:
            out.append(f"{path}:{n}: emoji {' '.join(repr(c) for c in bad)}")
    return out


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--selftest":
        return selftest()
    if not argv:
        print("usage: check_typography.py <changed-files-list>", file=sys.stderr)
        return 2
    listing = Path(argv[0])
    paths = [Path(p) for p in listing.read_text().split() if p]
    failures = [m for p in paths for m in scan(p)]
    for m in failures:
        print(f"::error::{m}")
    print(f"typography: scanned {len(paths)} files, {len(failures)} violations")
    return 1 if failures else 0


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        clean = Path(d) / "clean.py"
        clean.write_text("# a plain hyphen - is fine, and so is 1e18 FLOPS\nx = 1\n")
        assert scan(clean) == [], scan(clean)

        # Math and astronomy symbols must NOT trip the guard; CLAUDE.md section 5 names these explicitly.
        symbols = Path(d) / "symbols.md"
        symbols.write_text("α ≈ 0.5 M☉, ≫ 1 AU, x², → Mars ♂\n")
        assert scan(symbols) == [], scan(symbols)

        # A real emoji in the same block must still be caught.
        tick = Path(d) / "tick.md"
        tick.write_text("done ✅\n")
        assert len(scan(tick)) == 1, scan(tick)

        allowed = Path(d) / "fixture.ts"
        allowed.write_text(f"const emdash = /{EM_DASH}/; // {PRAGMA}: the rule's own test\n")
        assert scan(allowed) == [], scan(allowed)

        dashed = Path(d) / "dashed.md"
        dashed.write_text("this — that\n")
        assert len(scan(dashed)) == 1, scan(dashed)

        emo = Path(d) / "emo.ts"
        emo.write_text("const ok = 1; // \U0001f680\n")
        assert len(scan(emo)) == 1, scan(emo)

        lock = Path(d) / "uv.lock"
        lock.write_text("this — that\n")
        assert scan(lock) == [], "lock files are exempt"
    print("check_typography selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
