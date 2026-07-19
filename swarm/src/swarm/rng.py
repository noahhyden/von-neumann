"""A tiny seeded PRNG, threaded through the fold - never ambient (CLAUDE.md §7).

Thin re-export of :mod:`vn_core.rng` (issue #29, descoped to just the RNG). The
mulberry32 body used to live here as a hand-copy of the same generator in
``multi_probe/rng.py`` and ``frontend/scripts/gen-diff.mjs``; the JS parity is
now pinned by ``core/tests/test_rng.py`` against a committed fixture, so there
is exactly one Python source of truth. Existing call sites (``from swarm.rng
import next_float, seed_state``, etc.) keep working unchanged.
"""

from __future__ import annotations

from vn_core.rng import next_float, next_u32, seed_state

__all__ = ["next_float", "next_u32", "seed_state"]
