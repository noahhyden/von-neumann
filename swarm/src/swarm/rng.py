"""A tiny seeded PRNG, threaded through the fold - never ambient (CLAUDE.md §7)."""

from __future__ import annotations

from vn_core.rng import next_float, next_u32, seed_state

__all__ = ["next_float", "next_u32", "seed_state"]
