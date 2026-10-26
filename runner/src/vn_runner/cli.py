"""`vn-run` entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vn_runner import load, progress, run

REPO_ROOT = Path(__file__).resolve().parents[3]


class _ChildOwnsProgress:
    """The child process writes the status file; the parent has nothing to report."""

    def update(self, *, step: int, total: int | None = None, label: str = "") -> None:
        pass


def _ls() -> int:
    for _, s in load.discover(REPO_ROOT):
        first = s.description.strip().splitlines()[0] if s.description.strip() else ""
        print(f"{s.name}\t{s.module}\t{s.entry}\t{first}")
    return 0


def _ps() -> int:
    print(progress.format_table(progress.read_all(REPO_ROOT)))
    return 0


def _validate() -> int:
    problems = load.validate_tree(REPO_ROOT)
    for p in problems:
        print(p)
    return 1 if problems else 0


def _run(path: Path) -> int:
    try:
        spec = load.load_spec(path)
    except ValueError as e:
        print(f"vn-run: {e}", file=sys.stderr)
        return 2
    return run.execute(spec, REPO_ROOT, _ChildOwnsProgress())


def main(argv: list[str] | None = None) -> int:
    """vn-run <spec.yaml> | vn-run ls | vn-run ps | vn-run validate"""
    p = argparse.ArgumentParser(prog="vn-run", description=main.__doc__)
    p.add_argument("target", help="path to a run.yaml, or one of: ls, ps, validate")
    t = p.parse_args(argv).target
    if t == "ls":
        return _ls()
    if t == "ps":
        return _ps()
    if t == "validate":
        return _validate()
    return _run(Path(t))


if __name__ == "__main__":
    sys.exit(main())
