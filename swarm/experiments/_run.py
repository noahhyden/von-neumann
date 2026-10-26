"""Ensemble-run helpers - shared setup for scripts that invoke ``simulate_swarm``."""

from __future__ import annotations

import os
import sys


def warn_if_no_optimize(module: str) -> None:
    """Warn once to stderr if this ensemble entry point is running without ``-O``."""
    if sys.flags.optimize == 0:
        sys.stderr.write(
            f"warning: `{module}` is running without `-O`; ensemble will spend\n"
            f"         ~60% of wall clock on debug invariants (see docs/HARDWARE.md).\n"
            f"         Bit-identical fix: `uv run python -O -m {module}`.\n"
        )
        sys.stderr.flush()
    else:
        # Under multiprocessing 'spawn' (macOS default) workers re-exec sys.executable WITHOUT the parent's `-O` flag.
        os.environ.setdefault("PYTHONOPTIMIZE", str(sys.flags.optimize))
