#!/usr/bin/env python3
"""Run the pytest suite of every module this change reaches, via scripts/depgraph.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import depgraph  # noqa: E402


def affected_modules(changed_paths: list[str]) -> list[str]:
    """Reverse-reachability over the import DAG: the touched modules plus every importer."""
    graph = depgraph.Graph(REPO)
    changed = depgraph.resolve_changed(REPO, changed_paths, set(graph.modules))
    if not changed:
        return []
    return list(graph.impact(changed)["test_impact"])


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--selftest":
        return selftest()
    if not argv:
        print("usage: run_affected.py <changed-files-list>", file=sys.stderr)
        return 2
    paths = [p for p in Path(argv[0]).read_text().split() if p]
    modules = affected_modules(paths)
    if not modules:
        print("no module reached by this change; nothing to run")
        return 0
    print(f"modules reached: {' '.join(modules)}")
    failed: list[str] = []
    for m in modules:
        print(f"\n== {m} ==", flush=True)
        rc = subprocess.run(
            ["uv", "run", "--extra", "dev", "pytest", "-q"], cwd=REPO / m
        ).returncode
        if rc != 0:
            failed.append(m)
    print(f"\nran {len(modules)} module suites, {len(failed)} failed")
    for m in failed:
        print(f"::error::module suite failed: {m}")
    return 1 if failed else 0


def selftest() -> int:
    # A change to core must reach every module; a change to comms must not reach closure-sim.
    everything = affected_modules(["core/src/vn_core/rng.py"])
    assert len(everything) > 15, everything
    assert "swarm" in everything and "comms" in everything, everything

    narrow = affected_modules(["comms/src/comms/link.py"])
    assert "comms" in narrow, narrow
    assert "closure-sim" not in narrow, narrow

    assert affected_modules(["README.md"]) == [], "a docs-only change reaches no module"
    print("run_affected selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
