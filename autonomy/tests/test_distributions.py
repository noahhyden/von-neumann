"""autonomy.distributions: sourced spreads for every REFERENCES.md number."""

import math

import pytest

from autonomy.autonomy import (
    HONEYBEE_BRAIN_FLOPS,
    MOUSE_BRAIN_FLOPS,
    SELF_DRIVING_OPS_PER_S,
)
from autonomy.distributions import (
    HONEYBEE_BRAIN_FLOPS_DIST,
    MOUSE_BRAIN_FLOPS_DIST,
    SELF_DRIVING_OPS_PER_S_DIST,
)
from vn_core.uq import LogUniform, Uniform, monte_carlo


def test_biological_flops_are_loguniform():
    # Multi-order-of-magnitude spreads must be LogUniform, not Uniform.
    assert isinstance(HONEYBEE_BRAIN_FLOPS_DIST, LogUniform)
    assert isinstance(MOUSE_BRAIN_FLOPS_DIST, LogUniform)


def test_engineering_op_rate_stays_uniform():
    # Tight band -> Uniform is fine.
    assert isinstance(SELF_DRIVING_OPS_PER_S_DIST, Uniform)


def test_point_values_sit_inside_their_bands():
    assert HONEYBEE_BRAIN_FLOPS_DIST.low < HONEYBEE_BRAIN_FLOPS < HONEYBEE_BRAIN_FLOPS_DIST.high
    assert MOUSE_BRAIN_FLOPS_DIST.low < MOUSE_BRAIN_FLOPS < MOUSE_BRAIN_FLOPS_DIST.high
    assert SELF_DRIVING_OPS_PER_S_DIST.low < SELF_DRIVING_OPS_PER_S < SELF_DRIVING_OPS_PER_S_DIST.high


def test_autonomy_band_ordering_survives_uq():
    # REFERENCES.md's story: honeybee < self-driving-car < mouse (roughly).
    # Under LogUniform on the biological ends, does the ORDERING hold in the
    # MC medians? Yes for the point values; UQ shouldn't accidentally flip it.
    r_bee = monte_carlo({"x": HONEYBEE_BRAIN_FLOPS_DIST}, lambda s: s["x"], n=2000, seed=131)
    r_mouse = monte_carlo({"x": MOUSE_BRAIN_FLOPS_DIST}, lambda s: s["x"], n=2000, seed=131)
    # Compare geometric means (log-space).
    bee_gmean = math.exp(sum(math.log(v) for v in r_bee.values) / r_bee.n)
    mouse_gmean = math.exp(sum(math.log(v) for v in r_mouse.values) / r_mouse.n)
    assert bee_gmean < mouse_gmean
