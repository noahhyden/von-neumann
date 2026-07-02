"""Compute headroom vs distance — the probe-sim × power-budget coupling."""

import pytest

from probe_sim.autonomy import compute_headroom_at, max_distance_for_compute
from probe_sim.environment import SolarArray


def test_headroom_composes_delivered_power_allocation_and_efficiency():
    array = SolarArray(area_m2=10.0, efficiency=0.30)
    h = compute_headroom_at(
        array, 1.0, compute_fraction=0.20, efficiency_flops_per_w=1e11
    )
    # Delivered power is the array's output; compute share is the fraction of it.
    assert h.delivered_power_w == pytest.approx(array.power_w(1.0))
    assert h.compute_power_w == pytest.approx(0.20 * h.delivered_power_w)
    assert h.compute_flops == pytest.approx(h.compute_power_w * 1e11)
    assert h.brain_equivalents == pytest.approx(h.compute_flops / 1e18)


def test_headroom_falls_as_inverse_square():
    array = SolarArray(area_m2=10.0, efficiency=0.30)
    near = compute_headroom_at(array, 1.0, compute_fraction=0.2, efficiency_flops_per_w=1e11)
    far = compute_headroom_at(array, 2.0, compute_fraction=0.2, efficiency_flops_per_w=1e11)
    assert far.compute_flops == pytest.approx(near.compute_flops / 4)


def test_max_distance_for_compute_roundtrips():
    array = SolarArray(area_m2=10.0, efficiency=0.30)
    required = 1e13
    d = max_distance_for_compute(
        array, required, compute_fraction=0.20, efficiency_flops_per_w=1e11
    )
    # At that distance, the afforded compute equals the requirement.
    h = compute_headroom_at(array, d, compute_fraction=0.20, efficiency_flops_per_w=1e11)
    assert h.compute_flops == pytest.approx(required, rel=1e-6)


def test_higher_compute_demand_shrinks_range():
    array = SolarArray(area_m2=10.0, efficiency=0.30)
    lax = max_distance_for_compute(array, 1e13, compute_fraction=0.2, efficiency_flops_per_w=1e11)
    strict = max_distance_for_compute(array, 4e13, compute_fraction=0.2, efficiency_flops_per_w=1e11)
    assert strict < lax
    # 4x the compute demand -> half the reach (inverse-square).
    assert strict == pytest.approx(lax / 2, rel=1e-6)


def test_invalid_inputs_raise():
    array = SolarArray(area_m2=10.0, efficiency=0.30)
    with pytest.raises(ValueError):
        max_distance_for_compute(array, 0.0, compute_fraction=0.2, efficiency_flops_per_w=1e11)
    with pytest.raises(ValueError):
        max_distance_for_compute(array, 1e13, compute_fraction=0.0, efficiency_flops_per_w=1e11)
    with pytest.raises(ValueError):
        max_distance_for_compute(array, 1e13, compute_fraction=0.2, efficiency_flops_per_w=0.0)
