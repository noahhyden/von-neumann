"""A small seeded deterministic PRNG, carried as plain data."""

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
