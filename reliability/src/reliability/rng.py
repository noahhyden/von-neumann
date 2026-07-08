"""A small seeded deterministic PRNG, carried as plain data.

`reliability` is the only module in the project that introduces randomness, and CLAUDE.md
7 is explicit about the trap: a stray `random.random()` or wall-clock seed *works* until
someone asks the model to reproduce or replay, then silently breaks everything. So the
generator here is a pure function of an explicit integer state, threaded through the fold
exactly like the JS folds elsewhere in the repo. Same seed in -> same stream out, forever.

This is splitmix64 (Vigna), a well-tested 64-bit generator: fast, tiny, and fully
deterministic. The state is a plain `int`; nothing hidden, no global, no clock.
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
    """Advance the generator: returns (new_state, 64-bit output). Pure function."""
    state = (state + _GOLDEN) & _MASK64
    z = state
    z = ((z ^ (z >> 30)) * _MIX_A) & _MASK64
    z = ((z ^ (z >> 27)) * _MIX_B) & _MASK64
    z = z ^ (z >> 31)
    return state, z


def next_uniform(state: int) -> tuple[int, float]:
    """Advance the generator: returns (new_state, uniform in [0, 1)). Pure function."""
    state, z = next_uint64(state)
    return state, z / _TWO_POW_64
