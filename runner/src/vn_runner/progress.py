"""Expose running simulations and their progress. SLICE C owns the bodies; signatures are fixed."""

from __future__ import annotations

from pathlib import Path

from vn_runner.spec import RunSpec, RunStatus


def status_dir(repo_root: Path) -> Path:
    """Where live run status files are written; created on demand."""
    raise NotImplementedError


class FileProgress:
    """A Progress implementation that writes RunStatus atomically for `vn-run ps` to read."""

    def __init__(self, spec: RunSpec, repo_root: Path) -> None:
        raise NotImplementedError

    def update(self, *, step: int, total: int | None = None, label: str = "") -> None:
        raise NotImplementedError

    def finish(self, state: str, error: str | None = None) -> None:
        raise NotImplementedError


def read_all(repo_root: Path) -> list[RunStatus]:
    """Every status file, newest first, with dead PIDs reported as failed rather than running."""
    raise NotImplementedError


def format_table(rows: list[RunStatus]) -> str:
    """Plain ASCII table for the terminal; no colour, no box drawing."""
    raise NotImplementedError
