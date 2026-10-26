"""Expose running simulations and their progress: one atomic JSON status file per run."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from vn_runner.spec import RunSpec, RunStatus

# At most one disk write per second from update(); state changes always write through.
_MIN_INTERVAL_S = 1.0


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def status_dir(repo_root: Path) -> Path:
    """Where live run status files are written; created on demand."""
    d = repo_root / ".vn-runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


class FileProgress:
    """A Progress implementation that writes RunStatus atomically for `vn-run ps` to read."""

    def __init__(self, spec: RunSpec, repo_root: Path) -> None:
        self._path = status_dir(repo_root) / f"{spec.name}.json"
        now = _now()
        self._status = RunStatus(
            name=spec.name, pid=os.getpid(), started_at=now, updated_at=now, state="running"
        )
        self._last_write = float("-inf")
        self._write()

    def _write(self) -> None:
        self._status.updated_at = _now()
        tmp = self._path.with_name(f"{self._path.name}.{os.getpid()}.tmp")
        tmp.write_text(self._status.model_dump_json())
        os.replace(tmp, self._path)  # same directory, so the swap is atomic
        self._last_write = time.monotonic()

    def update(self, *, step: int, total: int | None = None, label: str = "") -> None:
        self._status.step, self._status.total, self._status.label = step, total, label
        if time.monotonic() - self._last_write >= _MIN_INTERVAL_S:
            self._write()

    def finish(self, state: str, error: str | None = None) -> None:
        self._status.state = cast(Literal["running", "done", "failed"], state)
        self._status.error = error
        self._write()


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    return True


def read_all(repo_root: Path) -> list[RunStatus]:
    """Every status file, newest first, with dead PIDs reported as failed rather than running."""
    rows: list[RunStatus] = []
    for p in status_dir(repo_root).glob("*.json"):
        try:
            s = RunStatus.model_validate_json(p.read_text())
        except (OSError, ValidationError):
            continue  # unreadable or foreign file: skip rather than crash the view
        if s.state == "running" and not _alive(s.pid):
            s = s.model_copy(update={"state": "failed", "error": "process died"})
        rows.append(s)
    return sorted(rows, key=lambda s: s.started_at, reverse=True)


def _elapsed(s: RunStatus) -> str:
    start = datetime.fromisoformat(s.started_at)
    end = datetime.now(UTC) if s.state == "running" else datetime.fromisoformat(s.updated_at)
    secs = max(0, int((end - start).total_seconds()))
    h, rem = divmod(secs, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h{m:02d}m{sec:02d}s" if h else f"{m}m{sec:02d}s"


def format_table(rows: list[RunStatus]) -> str:
    """Plain ASCII table for the terminal; no colour, no box drawing."""
    if not rows:
        return "no runs"
    body = [
        [
            s.name,
            s.state,
            str(s.step) if s.total is None else f"{s.step}/{s.total}",
            _elapsed(s),
            s.label or (s.error or ""),
        ]
        for s in rows
    ]
    table = [["NAME", "STATE", "PROGRESS", "ELAPSED", "LABEL"], *body]
    widths = [max(len(r[i]) for r in table) for i in range(5)]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in table)
