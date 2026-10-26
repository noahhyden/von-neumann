"""Execute one run spec locally, inside the target module's own uv environment."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from vn_runner import load
from vn_runner.spec import Progress, RunSpec

# Runs in the child: rebuild the spec, resolve the entry, report progress, and label failures.
_BOOTSTRAP = """
import importlib, inspect, sys
root, spec_json = sys.argv[1], sys.argv[2]
sys.path[:0] = [root + "/runner/src", "."]
from pathlib import Path
from vn_runner.progress import FileProgress
from vn_runner.events import Emitter
from vn_runner.spec import RunSpec
import time
spec = RunSpec.model_validate_json(spec_json)
progress = FileProgress(spec, Path(root))
events = Emitter(spec, Path(root))
events.run_start()
t0 = time.monotonic()
try:
    mod, name = spec.entry.split(":")
    fn = getattr(importlib.import_module(mod), name)
    progress.update(step=0, label="start " + spec.name)
    kw = dict(spec.params)
    params = inspect.signature(fn).parameters
    if "progress" in params:
        kw["progress"] = progress
    if "events" in params:
        kw["events"] = events
    fn(**kw)
except BaseException as e:
    progress.finish("failed", f"{type(e).__name__}: {e}")
    events.run_failed(e, time.monotonic() - t0)
    print(f"vn-run: spec {spec.name!r} failed: {type(e).__name__}: {e}", file=sys.stderr)
    raise
progress.finish("done")
events.run_end(time.monotonic() - t0)
"""


def _env_for(spec: RunSpec) -> dict[str, str]:
    """The internal switches the fold reads at import; a human never sets these."""
    rt, env = spec.runtime, {}
    if not rt.backends.rust:
        env.update(SWARM_NO_RUST="1", SWARM_NO_RUST_FILL="1", SWARM_NO_RUST_FLAT="1")
    if not rt.backends.njit:
        env["SWARM_NO_NJIT"] = "1"
    if rt.workers is not None:
        env["SWARM_WORKERS"] = str(rt.workers)
    return env


def build_command(spec: RunSpec, repo_root: Path) -> list[str]:
    """argv for the child; -O goes here, so no re-exec of the CLI is ever needed."""
    py = ["python", "-O"] if spec.runtime.optimize else ["python"]
    return ["uv", "run", "--extra", "dev", *py, "-c", _BOOTSTRAP, str(repo_root), spec.model_dump_json()]


def execute(spec: RunSpec, repo_root: Path, progress: Progress) -> int:
    """Run the entry in a child under the module's env; the child owns progress, so `progress` is unused."""
    load.assert_clean_env()
    env = {**os.environ, **_env_for(spec)}
    try:
        return subprocess.run(build_command(spec, repo_root), cwd=repo_root / spec.module, env=env).returncode
    except (OSError, KeyboardInterrupt) as e:
        print(f"vn-run: spec {spec.name!r} failed to launch: {e!r}", file=sys.stderr)
        return 1
