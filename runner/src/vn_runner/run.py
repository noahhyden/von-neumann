"""Execute one run spec locally. SLICE B owns the bodies; signatures are fixed."""

from __future__ import annotations

from pathlib import Path

from vn_runner.spec import Progress, RunSpec


def needs_reexec(spec: RunSpec) -> bool:
    """True when the spec asks for -O and this interpreter is not already optimized."""
    raise NotImplementedError


def execute(spec: RunSpec, repo_root: Path, progress: Progress) -> int:
    """Resolve the entry callable, run it under the spec's runtime, return an exit code."""
    raise NotImplementedError
