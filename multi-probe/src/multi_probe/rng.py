"""A tiny seeded PRNG, threaded through the fold — never ambient (CLAUDE.md §7).

`mulberry32`: 32-bit state, one multiply-xor-shift round per draw. We carry the state
*in* the fleet state and return a new state on every draw, so the whole simulation is
a pure function of (params, seed): fix the seed → bit-exact reproducibility → exact
`speculate` and replay. This is the one discipline the roadmap flags as silently
breaking everything downstream if ignored.

The algorithm is byte-for-byte the mulberry32 already used in
`frontend/scripts/gen-diff.mjs`, so a future TypeScript port of this module produces
identical sequences (all ops masked to unsigned 32-bit to match JS `|0`/`>>>`/imul).
"""

from __future__ import annotations

_MASK32 = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    """32-bit integer multiply (low 32 bits), matching JS ``Math.imul`` bit pattern."""
    return (a * b) & _MASK32


def next_u32(state: int) -> tuple[int, int]:
    """Draw one uint32 from ``state``; return ``(value, new_state)``.

    Pure: the caller threads ``new_state`` forward. Mirrors mulberry32 exactly.
    """
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
    """Normalize a seed into an initial 32-bit state."""
    return seed & _MASK32
