"""Behavioural + parity tests for `vn_core.rng` (mulberry32)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vn_core.rng import next_float, next_u32, seed_state

_MASK32 = 0xFFFFFFFF
_FIXTURE = Path(__file__).parent / "rng_js_fixture" / "fixture.json"


# --- basic contract ---------------------------------------------------------


class TestSeedState:
    def test_zero(self) -> None:
        assert seed_state(0) == 0

    def test_positive_within_mask(self) -> None:
        assert seed_state(42) == 42

    def test_at_upper_bound(self) -> None:
        assert seed_state(_MASK32) == _MASK32

    def test_masks_above_32_bits(self) -> None:
        # Python ints are unbounded; the seed must fit into 32 bits.
        assert seed_state(1 << 32) == 0
        assert seed_state((1 << 32) + 7) == 7

    def test_masks_negative_via_python_wrap(self) -> None:
        # Python's -1 & MASK32 == MASK32. Matches JS's `(-1) | 0 === -1` viewed as u32.
        assert seed_state(-1) == _MASK32


class TestNextU32:
    def test_returns_pair(self) -> None:
        v, s = next_u32(0)
        assert isinstance(v, int)
        assert isinstance(s, int)

    def test_value_in_u32_range(self) -> None:
        v, _ = next_u32(0)
        assert 0 <= v <= _MASK32

    def test_new_state_in_u32_range(self) -> None:
        _, s = next_u32(0xDEADBEEF)
        assert 0 <= s <= _MASK32

    def test_pure(self) -> None:
        # Same state in → same (value, new_state) out. Twice.
        assert next_u32(0) == next_u32(0)
        assert next_u32(0xDEADBEEF) == next_u32(0xDEADBEEF)

    def test_threading_is_deterministic(self) -> None:
        # Threading the state forward produces the same sequence every time.
        def stream(seed: int, n: int) -> list[int]:
            s = seed_state(seed)
            out: list[int] = []
            for _ in range(n):
                v, s = next_u32(s)
                out.append(v)
            return out

        assert stream(0, 16) == stream(0, 16)
        assert stream(42, 16) == stream(42, 16)

    def test_different_seeds_diverge(self) -> None:
        a = next_u32(seed_state(0))[0]
        b = next_u32(seed_state(1))[0]
        assert a != b


class TestNextFloat:
    def test_returns_pair(self) -> None:
        v, s = next_float(0)
        assert isinstance(v, float)
        assert isinstance(s, int)

    def test_range(self) -> None:
        # [0, 1) - the closed lower bound is achievable (state s where the u32
        for seed in range(32):
            v, _ = next_float(seed)
            assert 0.0 <= v < 1.0

    def test_matches_u32_over_2_32(self) -> None:
        # next_float MUST be `next_u32() / 2^32`, not / (2^32 - 1) or / 2^32 + 1.
        v_u32, _ = next_u32(0)
        v_f, _ = next_float(0)
        assert v_f == v_u32 / 4294967296.0

    def test_shared_state_advance(self) -> None:
        # next_float advances state identically to next_u32.
        _, s_u32 = next_u32(0)
        _, s_f = next_float(0)
        assert s_u32 == s_f


# --- JS parity: bit-identical to the frontend mulberry32 --------------------

# Python-side parity with swarm.rng and multi_probe.rng is verified two ways:


def _load_fixture() -> dict:
    with open(_FIXTURE) as f:
        return json.load(f)


class TestJSParity:
    """vn_core.rng u32 and float streams match the JS mulberry32 in the frontend."""

    def test_u32_stream_matches_fixture(self) -> None:
        fixture = _load_fixture()
        for seed_key, expected in fixture["seeds"].items():
            seed = int(seed_key)
            state = seed_state(seed)
            for i, want in enumerate(expected["u32"]):
                v, state = next_u32(state)
                assert v == want, f"u32 mismatch at seed={seed}, i={i}: {v} != {want}"

    def test_float_stream_matches_fixture(self) -> None:
        fixture = _load_fixture()
        for seed_key, expected in fixture["seeds"].items():
            seed = int(seed_key)
            state = seed_state(seed)
            for i, want in enumerate(expected["float"]):
                v, state = next_float(state)
                # Both sides divide a u32 by 2^32 in IEEE 754 double: bit-exact.
                assert v == want, f"float mismatch at seed={seed}, i={i}: {v} != {want}"


# --- corner cases the mask width and shift widths would trip on -------------


class TestMaskAndShiftInvariants:
    def test_state_wrap_at_boundary(self) -> None:
        # A state that would overflow u32 before masking: seed = MASK32, the largest legal state, must still yield u32 outputs.
        v, s = next_u32(_MASK32)
        assert 0 <= v <= _MASK32
        assert 0 <= s <= _MASK32

    def test_sequence_stays_u32_for_many_steps(self) -> None:
        # Advance the generator far enough that any missing mask would leak a value above 2**32 - 1.
        state = seed_state(1)
        for _ in range(4096):
            v, state = next_u32(state)
            assert 0 <= v <= _MASK32
            assert 0 <= state <= _MASK32


# --- guardrail: the fixture is non-trivial ---------------------------------


def test_fixture_covers_the_declared_seeds() -> None:
    fixture = _load_fixture()
    assert set(fixture["seeds"].keys()) == {"0", "1", "42", "2147483648", "4294967295"}
    for seed_key, entry in fixture["seeds"].items():
        assert len(entry["u32"]) == 32
        assert len(entry["float"]) == 32
        # A degenerate fixture (all zeros) would make the parity test pass vacuously.
        assert len(set(entry["u32"])) > 1, f"seed {seed_key} u32 stream is constant"
