"""The physics floor: Landauer limit and the brain scale. Real numbers, edges."""

import math

import pytest

from power_budget.physics import (
    BOLTZMANN_J_PER_K,
    BRAIN_COMPUTE_FLOPS_ESTIMATE,
    HUMAN_BRAIN_POWER_W,
    brain_equivalents,
    landauer_limit_j_per_bit,
    max_bit_operations_per_joule,
)


def test_landauer_limit_at_300k():
    # k_B * 300 * ln2 = 2.871e-21 J/bit.
    assert landauer_limit_j_per_bit(300.0) == pytest.approx(2.8710e-21, rel=1e-3)


def test_landauer_is_derived_not_hardcoded():
    # Must equal the formula exactly for an arbitrary temperature.
    T = 77.0
    assert landauer_limit_j_per_bit(T) == pytest.approx(BOLTZMANN_J_PER_K * T * math.log(2))


def test_landauer_scales_linearly_with_temperature():
    assert landauer_limit_j_per_bit(600.0) == pytest.approx(2 * landauer_limit_j_per_bit(300.0))


def test_nonpositive_temperature_raises():
    with pytest.raises(ValueError):
        landauer_limit_j_per_bit(0.0)
    with pytest.raises(ValueError):
        landauer_limit_j_per_bit(-10.0)


def test_max_bit_operations_per_joule_is_inverse_of_landauer():
    T = 300.0
    assert max_bit_operations_per_joule(T) == pytest.approx(1.0 / landauer_limit_j_per_bit(T))
    # ~3.5e20 irreversible bit-ops per joule at room temperature.
    assert max_bit_operations_per_joule(300.0) == pytest.approx(3.48e20, rel=1e-2)


def test_brain_power_scale():
    assert HUMAN_BRAIN_POWER_W == pytest.approx(20.0)


def test_brain_equivalents():
    assert brain_equivalents(BRAIN_COMPUTE_FLOPS_ESTIMATE) == pytest.approx(1.0)
    assert brain_equivalents(5 * BRAIN_COMPUTE_FLOPS_ESTIMATE) == pytest.approx(5.0)
    with pytest.raises(ValueError):
        brain_equivalents(1e18, brain_flops=0)
