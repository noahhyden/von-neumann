"""The `run.yaml` contract: what a simulation run IS, with no environment variables."""

from __future__ import annotations

import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A run declares the whole of its own configuration. These names were the old surface and are now rejected, not ignored, so a stale export cannot quietly change a result.
BANNED_ENV = frozenset(
    {
        "SWARM_WORKERS",
        "SWARM_NO_NJIT",
        "SWARM_NO_RUST",
        "SWARM_NO_RUST_FILL",
        "SWARM_NO_RUST_FLAT",
        "SWARM_P2_N_OVERRIDE",
        "PYTHONOPTIMIZE",
    }
)

_ENTRY = re.compile(r"^[a-zA-Z_][\w.]*:[a-zA-Z_]\w*$")
_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


class Backends(BaseModel):
    """Which accelerated kernels may be used; all true is the shipped default."""

    model_config = ConfigDict(extra="forbid")

    rust: bool = True
    njit: bool = True


class Runtime(BaseModel):
    """How the run executes. Never what it computes - that is `params`."""

    model_config = ConfigDict(extra="forbid")

    # None means every core. The cap exists because a big-N sweep is RAM-bound, not CPU-bound.
    workers: int | None = Field(default=None, ge=1)
    # True re-execs under -O, which strips the fold's __debug__ invariants; bit-identical, ~2-3x faster.
    optimize: bool = True
    backends: Backends = Backends()


class RunSpec(BaseModel):
    """One simulation run, loaded from a committed `run.yaml`."""

    model_config = ConfigDict(extra="forbid")

    name: str
    module: str
    # "experiments.measure:m_lambda_sweep" - an importable module path and a zero-argument callable.
    entry: str
    description: str
    runtime: Runtime = Runtime()
    # Passed through to the entry callable as keyword arguments; the callable owns their meaning.
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _name_is_a_slug(cls, v: str) -> str:
        if not _NAME.match(v):
            raise ValueError(f"name must be a lowercase slug, got {v!r}")
        return v

    @field_validator("entry")
    @classmethod
    def _entry_is_module_colon_callable(cls, v: str) -> str:
        if not _ENTRY.match(v):
            raise ValueError(f"entry must be 'module.path:callable', got {v!r}")
        return v


class Progress(Protocol):
    """The seam the runner hands to a running experiment so it can report advance."""

    def update(self, *, step: int, total: int | None = None, label: str = "") -> None:
        ...


class RunStatus(BaseModel):
    """A live run, as written to the status file that `vn-run ps` reads."""

    model_config = ConfigDict(extra="forbid")

    name: str
    pid: int
    started_at: str
    updated_at: str
    state: Literal["running", "done", "failed"]
    step: int = 0
    total: int | None = None
    label: str = ""
    error: str | None = None


__all__ = [
    "BANNED_ENV",
    "Backends",
    "Progress",
    "RunSpec",
    "RunStatus",
    "Runtime",
]
