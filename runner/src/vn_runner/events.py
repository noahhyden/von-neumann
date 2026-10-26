"""Append-only run event log: what HAPPENED during a run, beside the snapshot of where it is."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from vn_runner.spec import RunSpec

Severity = Literal["debug", "info", "warn", "error", "critical"]

# A consumer classifies on severity plus payload.type with digit runs normalised, so `type` names the KIND and the varying detail goes in sibling keys.
_TYPE_OK = set("abcdefghijklmnopqrstuvwxyz0123456789_")


def events_path(spec_name: str, repo_root: Path) -> Path:
    """The append-only log for one run. Never rewritten, unlike the status snapshot."""
    return Path(repo_root) / ".vn-runs" / f"{spec_name}.events.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Emitter:
    """Writes one JSON object per line, O_APPEND so forked workers can share the file."""

    def __init__(self, spec: RunSpec, repo_root: Path) -> None:
        self.spec = spec
        self.path = events_path(spec.name, repo_root)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, type: str, *, severity: Severity = "info", **payload: Any) -> None:
        """Append one event. `type` is a stable slug; put varying values in sibling keys."""
        if not type or set(type) - _TYPE_OK:
            raise ValueError(f"event type must be a lowercase slug, got {type!r}")
        line = json.dumps(
            {"ts": _now(), "severity": severity, "payload": {"type": type, **payload}},
            sort_keys=True,
        )
        # ponytail: one O_APPEND write per line, atomic under PIPE_BUF (4096) on Linux; a longer line could interleave across worker processes, which is the known ceiling.
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            # A crash can leave a truncated final line with no newline; lead with one so the next event starts clean instead of fusing onto it and losing both.
            size = os.lseek(fd, 0, os.SEEK_END)
            heal = "\n" if size and os.pread(fd, 1, size - 1) != b"\n" else ""
            os.write(fd, (heal + line + "\n").encode("utf-8"))
        finally:
            os.close(fd)

    def run_start(self) -> None:
        """Opens the log for a run, recording the configuration that shaped it."""
        rt = self.spec.runtime
        self.emit(
            "run_start",
            spec=self.spec.name,
            module=self.spec.module,
            entry=self.spec.entry,
            workers=rt.workers,
            optimize=rt.optimize,
            # False means the fold's __debug__ invariant checks were compiled out, so this run COULD NOT have reported one.
            invariants_active=not rt.optimize,
            backends={"rust": rt.backends.rust, "njit": rt.backends.njit},
        )

    def run_end(self, duration_s: float) -> None:
        self.emit("run_end", spec=self.spec.name, state="done", duration_s=round(duration_s, 3))

    def run_failed(self, exc: BaseException, duration_s: float) -> None:
        self.emit(
            "run_failed",
            severity="error",
            spec=self.spec.name,
            state="failed",
            error_type=type(exc).__name__,
            message=str(exc)[:2000],
            duration_s=round(duration_s, 3),
        )


def read_events(spec_name: str, repo_root: Path) -> list[dict[str, Any]]:
    """Parse one run's log, skipping any line a crash left half-written."""
    p = events_path(spec_name, repo_root)
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


__all__ = ["Emitter", "Severity", "events_path", "read_events"]
