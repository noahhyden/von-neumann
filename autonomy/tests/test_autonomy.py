"""autonomy validation: the demand band, the derived split, and the autonomy wall.

Anchors: honeybee brain ~1e13, self-driving car ~1.4e14 ops/s, mouse brain ~1e15. The
wall must equal probe-sim's supply-side max_distance_for_compute (loop closed). See
REFERENCES.md.
"""

import math

import pytest

from power_budget.budget import compute_capacity_flops
from probe_sim.autonomy import max_distance_for_compute
from probe_sim.environment import SolarArray

from autonomy.autonomy import (
    HONEYBEE_BRAIN_FLOPS,
    MOUSE_BRAIN_FLOPS,
    SELF_DRIVING_OPS_PER_S,
    affordable_compute_at,
    autonomy_wall_au,
    compute_fraction_needed,
    required_compute_band,
    required_compute_power_w,
)


def test_three_lines_converge_on_the_same_band():
    band = required_compute_band()
    # honeybee < self-driving car < mouse: the central engineered anchor lands between
    # the two independent brain estimates.
    assert band.low_flops == HONEYBEE_BRAIN_FLOPS == 1e13
    assert band.high_flops == MOUSE_BRAIN_FLOPS == 1e15
    assert band.central_flops == SELF_DRIVING_OPS_PER_S == 1.4e14
    assert band.low_flops < band.central_flops < band.high_flops
    # The band spans two orders of magnitude - the honest uncertainty.
    assert band.high_flops / band.low_flops == pytest.approx(100.0)


def test_required_power_is_inverse_of_capacity():
    # required_compute_power_w is the inverse of power_budget.compute_capacity_flops.
    w = required_compute_power_w(1.4e14, efficiency_flops_per_w=1e10)
    assert w == pytest.approx(1.4e4)
    assert compute_capacity_flops(w, 1e10) == pytest.approx(1.4e14, rel=1e-9)


def test_compute_fraction_is_derived_not_the_free_0_70_split():
    # 140 TOPS at 1e10 FLOPS/W needs 14 kW; of a 100 kW bus that is a 0.14 compute
    # fraction - DERIVED, replacing the hand-set 0.30 (the complement of 0.70 manuf).
    frac = compute_fraction_needed(1.4e14, total_power_w=100_000.0, efficiency_flops_per_w=1e10)
    assert frac == pytest.approx(0.14, rel=1e-9)
    assert frac != 0.30  # it is not the assumed split


def test_compute_fraction_raises_when_demand_exceeds_budget():
    # Mouse-brain demand at low efficiency on a small bus is infeasible.
    with pytest.raises(ValueError):
        compute_fraction_needed(1e15, total_power_w=1000.0, efficiency_flops_per_w=1e10)


def test_affordable_compute_falls_as_inverse_square():
    s0 = 1e15
    assert affordable_compute_at(s0, 1.0) == pytest.approx(s0)
    assert affordable_compute_at(s0, 2.0) == pytest.approx(s0 / 4.0)
    assert affordable_compute_at(s0, 5.0) == pytest.approx(s0 / 25.0)


def test_autonomy_wall_and_demand_ordering():
    # Supply 1e15 at 1 AU. Higher demand -> closer wall.
    supply = 1e15
    wall_bee = autonomy_wall_au(supply, HONEYBEE_BRAIN_FLOPS)   # sqrt(100) = 10 AU
    wall_car = autonomy_wall_au(supply, SELF_DRIVING_OPS_PER_S)  # sqrt(7.14) = 2.67 AU
    wall_mouse = autonomy_wall_au(supply, MOUSE_BRAIN_FLOPS)    # sqrt(1) = 1 AU
    assert wall_bee == pytest.approx(10.0)
    assert wall_car == pytest.approx(math.sqrt(1e15 / 1.4e14), rel=1e-9)
    assert wall_mouse == pytest.approx(1.0)
    assert wall_bee > wall_car > wall_mouse  # heavier brains hit the wall sooner


def test_wall_closes_probe_sims_supply_loop():
    # The wall computed here must equal probe-sim's supply-side max_distance_for_compute
    # when fed the same array, split, and efficiency - the loop closure.
    array = SolarArray(area_m2=10.0, efficiency=0.30)
    compute_fraction = 0.30
    efficiency = 1e10
    required = 1e12

    supply_1au = array.power_w(1.0) * compute_fraction * efficiency
    wall_here = autonomy_wall_au(supply_1au, required)
    wall_probe_sim = max_distance_for_compute(
        array, required, compute_fraction=compute_fraction, efficiency_flops_per_w=efficiency
    )
    assert wall_here == pytest.approx(wall_probe_sim, rel=1e-9)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        required_compute_power_w(0.0, 1e10)
    with pytest.raises(ValueError):
        autonomy_wall_au(0.0, 1e13)
    with pytest.raises(ValueError):
        affordable_compute_at(1e15, 0.0)
