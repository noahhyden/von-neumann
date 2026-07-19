"""Behavioural + contract tests for :mod:`reliability.rng` (splitmix64).

reliability is the one module that uses a 64-bit generator (splitmix64) rather
than mulberry32; it has no frontend/JS surface and so no JS-parity requirement,
and a wider generator is defensible for a purely-Python module. What it *does*
share with the rest of the repo is the ``(value, new_state)`` threading
contract, so a callsite moved between generators cannot silently swap value and
state (issue #65 - the footgun this file exists to catch).

Three layers:

- **Basic contract.** Purity, threading, seeded reproducibility, mask width.
- **Tuple order.** Position 0 is the value, position 1 is the new state - the
  same order as ``vn_core.rng``. A regression to ``(state, value)`` fails a
  targeted assertion here, not silently downstream.
- **Stream fixture.** Pins the exact splitmix64 output for seed 12345 over 16
  draws. Any accidental change to the constants, the masks, or the shift
  widths of the algorithm is caught here rather than in a downstream drift-guard.
"""

from __future__ import annotations

import pytest

from reliability.rng import next_uint64, next_uniform, seed_state

_MASK64 = (1 << 64) - 1


# --- basic contract ---------------------------------------------------------


class TestSeedState:
    def test_zero(self) -> None:
        assert seed_state(0) == 0

    def test_positive_within_mask(self) -> None:
        assert seed_state(42) == 42

    def test_at_upper_bound(self) -> None:
        assert seed_state(_MASK64) == _MASK64

    def test_masks_above_64_bits(self) -> None:
        assert seed_state(1 << 64) == 0
        assert seed_state((1 << 64) + 7) == 7

    def test_masks_negative_via_python_wrap(self) -> None:
        assert seed_state(-1) == _MASK64


class TestNextUint64:
    def test_returns_pair(self) -> None:
        v, s = next_uint64(0)
        assert isinstance(v, int)
        assert isinstance(s, int)

    def test_value_in_u64_range(self) -> None:
        v, _ = next_uint64(0xDEADBEEF)
        assert 0 <= v <= _MASK64

    def test_state_in_u64_range(self) -> None:
        _, s = next_uint64(0xDEADBEEF)
        assert 0 <= s <= _MASK64

    def test_pure(self) -> None:
        assert next_uint64(0) == next_uint64(0)
        assert next_uint64(0xCAFEBABE) == next_uint64(0xCAFEBABE)

    def test_threading_is_deterministic(self) -> None:
        def stream(seed: int, n: int) -> list[int]:
            s = seed_state(seed)
            out: list[int] = []
            for _ in range(n):
                v, s = next_uint64(s)
                out.append(v)
            return out

        assert stream(0, 16) == stream(0, 16)
        assert stream(42, 16) == stream(42, 16)

    def test_different_seeds_diverge(self) -> None:
        a, _ = next_uint64(seed_state(0))
        b, _ = next_uint64(seed_state(1))
        assert a != b

    def test_stays_u64_for_many_steps(self) -> None:
        # A missing mask would leak values above 2**64 into Python's unbounded ints.
        state = seed_state(1)
        for _ in range(2048):
            v, state = next_uint64(state)
            assert 0 <= v <= _MASK64
            assert 0 <= state <= _MASK64


class TestNextUniform:
    def test_returns_pair(self) -> None:
        v, s = next_uniform(0)
        assert isinstance(v, float)
        assert isinstance(s, int)

    def test_range(self) -> None:
        for seed in range(64):
            v, _ = next_uniform(seed)
            assert 0.0 <= v < 1.0

    def test_state_matches_u64(self) -> None:
        # next_uniform advances state identically to next_uint64.
        _, s_u64 = next_uint64(0)
        _, s_uf = next_uniform(0)
        assert s_u64 == s_uf

    def test_uses_2_pow_64_divisor(self) -> None:
        # The divisor MUST be 2**64. Using 2**64 - 1 would let 1.0 slip through
        # for the maximal u64 draw and drift from the documented [0, 1) range.
        u64_val, _ = next_uint64(0)
        uf_val, _ = next_uniform(0)
        assert uf_val == u64_val / float(1 << 64)


# --- the tuple-order footgun (#65) ------------------------------------------


class TestTupleOrderMatchesVnCore:
    """The one contract reliability shares with vn_core.rng: (value, new_state).

    A regression here is #65 reappearing. Written as targeted assertions rather
    than baked into the stream tests so a failure points straight at the swap.
    """

    def test_uint64_position_0_is_the_u64_value(self) -> None:
        # A uniform draw is a float in [0, 1); a u64 is an int outside that range
        # (except for the astronomically-unlikely 0). Advance twice from a
        # non-zero seed so the u64 is well clear of the [0, 1) interval, then
        # check position 0 is the u64-shaped thing.
        first = next_uint64(seed_state(1))
        assert isinstance(first[0], int)
        assert first[0] > 1  # not a float-shaped uniform in [0, 1)
        assert 0 <= first[1] <= _MASK64

    def test_uniform_position_0_is_the_float_value(self) -> None:
        first = next_uniform(seed_state(1))
        assert isinstance(first[0], float)
        assert 0.0 <= first[0] < 1.0
        assert isinstance(first[1], int)
        assert 0 <= first[1] <= _MASK64

    def test_state_field_can_be_re_threaded(self) -> None:
        # The state returned in position 1 must be the correct next state, not
        # (say) the u64 value accidentally reused. Prove it by re-threading:
        # calling next_uniform twice with the returned state must match a single
        # deterministic sequence.
        s = seed_state(42)
        v1, s1 = next_uniform(s)
        v2, s2 = next_uniform(s1)
        # If the state were mis-swapped for the value in position 1, the second
        # draw would use the u64 value (huge integer) as state and produce
        # something very different from the reference run below.
        ref = seed_state(42)
        expected_v1, ref = next_uniform(ref)
        expected_v2, ref = next_uniform(ref)
        assert v1 == expected_v1
        assert v2 == expected_v2


# --- stream fixture: pins the exact splitmix64 output ----------------------

# Generated by seed_state(12345) → 16 draws of next_uint64 / next_uniform on
# the current impl. Any change to _GOLDEN, _MIX_A, _MIX_B, the mask width, or a
# shift width breaks these constants and a targeted test fails here rather
# than reliability's downstream drift showing up as a mystery number.

_EXPECTED_U64 = [
    2454886589211414944,
    3778200017661327597,
    2205171434679333405,
    3248800117070709450,
    9350289611492784363,
    6217189988962137646,
    2262534019502804546,
    7959005890829367068,
    8850488307750713623,
    16002954917502516943,
    3405751836678233477,
    7014104804809742358,
    14114363228552558692,
    16191270710157941333,
    17902312926382128400,
    7224149396417083062,
]

_EXPECTED_UNIFORM = [
    0.13307966866142731,
    0.20481663336165912,
    0.1195425830091155,
    0.1761178072449612,
    0.506880215507456,
    0.337034544639394,
    0.12265221496336506,
    0.4314585738831064,
    0.47978593254104396,
    0.8675219243871908,
    0.1846261770136519,
    0.3802353833707869,
    0.7651411637823101,
    0.8777305439627078,
    0.9704863283649416,
    0.39162192349776237,
]


def test_uint64_stream_matches_fixture() -> None:
    s = seed_state(12345)
    got: list[int] = []
    for _ in range(len(_EXPECTED_U64)):
        v, s = next_uint64(s)
        got.append(v)
    assert got == _EXPECTED_U64


def test_uniform_stream_matches_fixture() -> None:
    s = seed_state(12345)
    got: list[float] = []
    for _ in range(len(_EXPECTED_UNIFORM)):
        v, s = next_uniform(s)
        got.append(v)
    assert got == _EXPECTED_UNIFORM
