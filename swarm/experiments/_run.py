"""Ensemble-run helpers - shared setup for scripts that invoke ``simulate_swarm``.

Small, dependency-free, imported at the top of every ``experiments/*.py`` script that
runs the fold. The one thing here is ``warn_if_no_optimize``: the swarm fold carries
``if __debug__:`` invariant checks at each step call site
(``sim._verify_step_invariants``); on a 20k-star run they cost roughly 60% of wall
time (the profile at N=20k in issue #33's PR body). Stripping them via ``python -O``
is bit-identical - the invariants only READ state and raise on mismatch; they never
mutate a number that the fold produces - but only the user picks whether to run
with ``-O``, so we WARN when an ensemble runs without it rather than silently pay
the tax. Also propagates ``PYTHONOPTIMIZE`` to child workers under
``multiprocessing`` spawn (macOS default), so a parent invoked with ``-O`` has
matching workers on every platform.

The rule (CLAUDE.md 7 + docs/HARDWARE.md "Assertion mode"):
- **Tests and interactive dev** run with invariants ON. Losing a bug because we
  forgot to check it in release is a 2 failure mode.
- **Ensemble runs** (Sobol sweeps, 200k-star paired coordination runs, anything
  measuring wall clock) run with ``-O``. Invariants are observational; they never
  change a result.
"""

from __future__ import annotations

import os
import sys


def warn_if_no_optimize(module: str) -> None:
    """Warn once to stderr if this ensemble entry point is running without ``-O``.

    ``module`` is the invocation form of the entry point (e.g.
    ``"experiments.measure"``) so the warning's suggested command is copy-pasteable.
    """
    if sys.flags.optimize == 0:
        sys.stderr.write(
            f"warning: `{module}` is running without `-O`; ensemble will spend\n"
            f"         ~60% of wall clock on debug invariants (see docs/HARDWARE.md).\n"
            f"         Bit-identical fix: `uv run python -O -m {module}`.\n"
        )
        sys.stderr.flush()
    else:
        # Under multiprocessing 'spawn' (macOS default) workers re-exec sys.executable
        # WITHOUT the parent's `-O` flag. Setting the env var makes them strip
        # invariants too, so parent and workers agree. On Linux 'fork' inherits
        # sys.flags.optimize directly, so this is a no-op there.
        os.environ.setdefault("PYTHONOPTIMIZE", str(sys.flags.optimize))
