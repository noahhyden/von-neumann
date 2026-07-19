"""A small seeded deterministic PRNG, carried as plain data.

`reliability` is the only module in the project that introduces randomness, and CLAUDE.md
7 is explicit about the trap: a stray `random.random()` or wall-clock seed *works* until
someone asks the model to reproduce or replay, then silently breaks everything. So the
generator here is a pure function of an explicit integer state, threaded through the fold
exactly like the JS folds elsewhere in the repo. Same seed in -> same stream out, forever.

This is splitmix64 (Vigna), a well-tested 64-bit generator: fast, tiny, and fully
deterministic. The state is a plain `int`; nothing hidden, no global, no clock.

Draws return ``(value, new_state)`` - value first, state second - matching the
one threading contract used everywhere else in the repo (``vn_core.rng``,
``swarm.rng``, ``multi_probe.rng``). splitmix64 stays the algorithm here because
`reliability` has no frontend/JS surface and so no mulberry32 parity requirement;
only the tuple order is shared, so a callsite moved between generators cannot
silently swap value and state (issue #65).
"""

from __future__ import annotations

_MASK64 = (1 << 64) - 1
_GOLDEN = 0x9E3779B97F4A7C15
_MIX_A = 0xBF58476D1CE4E5B9
_MIX_B = 0x94D049BB133111EB
_TWO_POW_64 = float(1 << 64)


def seed_state(seed: int) -> int:
    """Turn a user seed into an initial PRNG state (plain int)."""
    return seed & _MASK64


def next_uint64(state: int) -> tuple[int, int]:
    """Draw one uint64 from ``state``; return ``(value, new_state)``. Pure function."""
    state = (state + _GOLDEN) & _MASK64
    z = state
    z = ((z ^ (z >> 30)) * _MIX_A) & _MASK64
    z = ((z ^ (z >> 27)) * _MIX_B) & _MASK64
    z = z ^ (z >> 31)
    return z, state


def next_uniform(state: int) -> tuple[float, int]:
    """Draw one uniform in ``[0, 1)``; return ``(value, new_state)``. Pure function."""
    z, state = next_uint64(state)
    return z / _TWO_POW_64, state
