"""Seeded, deterministic mulberry32 - the shared RNG for the von-neumann repo.

Threaded through the fold, never ambient: the caller carries the 32-bit state,
passes it in, and receives ``(value, new_state)``. This is the one discipline
CLAUDE.md §7 flags as silently breaking everything downstream if ignored -
`Math.random()` or a wall-clock seed *works* until someone asks the fold to
`speculate` or replay, then quietly diverges.

Bit-identical to the mulberry32 in ``frontend/src/swarm.ts``,
``frontend/src/multi-probe.ts``, and ``frontend/scripts/gen-diff.mjs``, so a
Python fold and its TypeScript port produce identical star fields, choices, and
outputs. That parity is pinned by ``tests/test_rng.py`` against a committed
JS-generated fixture (see ``tests/rng_js_fixture/``); any drift in either
language is a test failure, not a downstream simulation puzzle.

The 32-bit mask on ``_imul`` and on every intermediate matches JS's
``Math.imul`` / ``| 0`` / ``>>>`` semantics under Python's unbounded ints.
"""

from __future__ import annotations

_MASK32 = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    return (a * b) & _MASK32


def seed_state(seed: int) -> int:
    """Normalize a seed (any Python int) into an initial 32-bit state."""
    return seed & _MASK32


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
    """Draw one float in ``[0, 1)``; return ``(value, new_state)``.

    Both this Python impl and the JS impls divide a uint32 by ``2**32`` in
    IEEE 754 double, so ``next_float`` is bit-exact across the language boundary.
    """
    value, new_state = next_u32(state)
    return value / 4294967296.0, new_state


__all__ = ["next_float", "next_u32", "seed_state"]
