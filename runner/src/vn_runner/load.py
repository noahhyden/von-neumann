"""Load and validate committed run specs."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from vn_runner.spec import BANNED_ENV, RunSpec

_SKIP = {".venv", "node_modules", ".git", ".claude"}


def load_spec(path: Path) -> RunSpec:
    """Parse one run.yaml into a RunSpec, raising ValueError naming the file on any fault."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text())
    except (yaml.YAMLError, OSError) as e:
        raise ValueError(f"{path}: cannot read YAML: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    try:
        spec = RunSpec(**data)
    except (ValidationError, TypeError) as e:
        raise ValueError(f"{path}: invalid run spec: {e}") from e
    if spec.name != path.stem:
        raise ValueError(f"{path}: name {spec.name!r} must equal the filename stem {path.stem!r}")
    return spec


def _paths(repo_root: Path) -> list[Path]:
    return sorted(
        p
        for d in Path(repo_root).iterdir()
        if d.is_dir() and d.name not in _SKIP
        for p in (d / "runs").glob("*.yaml")
    )


def discover(repo_root: Path) -> list[tuple[Path, RunSpec]]:
    """Every `<module>/runs/*.yaml` in the repo, sorted by path."""
    return [(p, load_spec(p)) for p in _paths(repo_root)]


def validate_tree(repo_root: Path) -> list[str]:
    """Human-readable problems across every spec; empty list means the tree is clean."""
    problems: list[str] = []
    seen: dict[str, Path] = {}
    for p in _paths(repo_root):
        try:
            spec = load_spec(p)
        except ValueError as e:
            problems.append(str(e))
            continue
        if spec.module != p.parent.parent.name:
            problems.append(f"{p}: module {spec.module!r} does not match directory {p.parent.parent.name!r}")
        if spec.name in seen:
            problems.append(f"{p}: duplicate name {spec.name!r}, also used by {seen[spec.name]}")
        else:
            seen[spec.name] = p
    return problems


def assert_clean_env() -> None:
    """Raise if any BANNED_ENV name is set: a stale export must not change a result."""
    bad = sorted(BANNED_ENV & os.environ.keys())
    if bad:
        raise RuntimeError(
            f"banned environment variables are set: {', '.join(bad)}. "
            "Unset them and put the value in the run.yaml instead."
        )
