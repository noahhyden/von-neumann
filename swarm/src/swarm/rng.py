"""A tiny seeded PRNG, threaded through the fold - never ambient (CLAUDE.md §7).

mulberry32, identical to `multi_probe/rng.py` and `frontend/scripts/gen-diff.mjs`, so a
future TypeScript SoA port of the swarm produces the same star fields and choices. Each
module stays independently runnable (§4), so this 15-line standard generator is
deliberately duplicated rather than shared through a cross-module dependency.
"""

from __future__ import annotations

_MASK32 = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    return (a * b) & _MASK32


def next_u32(state: int) -> tuple[int, int]:
    """Draw one uint32 from ``state``; return ``(value, new_state)`` (pure)."""
    s = (state + 0x6D2B79F5) & _MASK32
    t = _imul(s ^ (s >> 15), 1 | s)
    t = (((t + _imul(t ^ (t >> 7), 61 | t)) & _MASK32) ^ t) & _MASK32
    value = (t ^ (t >> 14)) & _MASK32
    return value, s


def next_float(state: int) -> tuple[float, int]:
    """Draw one float in [0, 1); return ``(value, new_state)``."""
    value, new_state = next_u32(state)
    return value / 4294967296.0, new_state


def seed_state(seed: int) -> int:
    return seed & _MASK32
