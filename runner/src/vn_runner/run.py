"""Execute one run spec locally."""

from __future__ import annotations

import importlib
import inspect
import os
import sys
import traceback
from pathlib import Path

from vn_runner import load
from vn_runner.spec import Progress, RunSpec


def needs_reexec(spec: RunSpec) -> bool:
    """True when the spec asks for -O and this interpreter is not already optimized."""
    return spec.runtime.optimize and sys.flags.optimize == 0


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


def execute(spec: RunSpec, repo_root: Path, progress: Progress) -> int:
    """Resolve the entry callable, run it under the spec's runtime, return an exit code."""
    load.assert_clean_env()
    module_dir = str(repo_root / spec.module)
    saved_env, saved_cwd, saved_path = dict(os.environ), os.getcwd(), list(sys.path)
    finish = getattr(progress, "finish", None)
    try:
        os.environ.update(_env_for(spec))
        os.chdir(module_dir)
        sys.path.insert(0, module_dir)
        mod_name, fn_name = spec.entry.split(":")
        fn = getattr(importlib.import_module(mod_name), fn_name)
        progress.update(step=0, label=f"start {spec.name}")
        kwargs = dict(spec.params)
        if "progress" in inspect.signature(fn).parameters:
            kwargs["progress"] = progress
        fn(**kwargs)
    except BaseException as e:  # noqa: BLE001 - label every failure with its spec
        if isinstance(e, KeyboardInterrupt):
            msg = "interrupted"
        else:
            msg = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        print(f"vn-run: spec {spec.name!r} failed: {msg}", file=sys.stderr)
        if finish:
            finish("failed", msg)
        return 1
    finally:
        os.environ.clear()
        os.environ.update(saved_env)
        os.chdir(saved_cwd)
        sys.path[:] = saved_path
    if finish:
        finish("done")
    return 0
