"""Load and validate committed run specs. SLICE A owns the bodies; signatures are fixed."""

from __future__ import annotations

from pathlib import Path

from vn_runner.spec import RunSpec


def load_spec(path: Path) -> RunSpec:
    """Parse one run.yaml into a RunSpec, raising ValueError naming the file on any fault."""
    raise NotImplementedError


def discover(repo_root: Path) -> list[tuple[Path, RunSpec]]:
    """Every `<module>/runs/*.yaml` in the repo, sorted by path."""
    raise NotImplementedError


def validate_tree(repo_root: Path) -> list[str]:
    """Human-readable problems across every spec; empty list means the tree is clean."""
    raise NotImplementedError


def assert_clean_env() -> None:
    """Raise if any BANNED_ENV name is set: a stale export must not change a result."""
    raise NotImplementedError
