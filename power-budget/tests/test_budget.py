"""Power allocation and compute conversion. Assert the accounting and edges."""

import pytest
from pydantic import ValidationError

from power_budget.budget import PowerBudget, compute_capacity_flops


def test_allocations_split_the_total():
    b = PowerBudget(
        total_w=1000.0,
        fraction_manufacturing=0.6,
        fraction_compute=0.25,
        fraction_housekeeping=0.1,
    )
    assert b.manufacturing_w == pytest.approx(600.0)
    assert b.compute_w == pytest.approx(250.0)
    assert b.housekeeping_w == pytest.approx(100.0)
    # Remainder is spare margin.
    assert b.unallocated_w == pytest.approx(50.0)


def test_allocations_conserve_power():
    b = PowerBudget(
        total_w=750.0,
        fraction_manufacturing=0.5,
        fraction_compute=0.3,
        fraction_housekeeping=0.2,
    )
    parts = b.manufacturing_w + b.compute_w + b.housekeeping_w + b.unallocated_w
    assert parts == pytest.approx(b.total_w)
    assert b.unallocated_w == pytest.approx(0.0)


def test_over_allocation_is_rejected():
    with pytest.raises(ValidationError):
        PowerBudget(
            total_w=1000.0,
            fraction_manufacturing=0.7,
            fraction_compute=0.5,  # 1.2 > 1
        )


def test_nonpositive_total_rejected():
    with pytest.raises(ValidationError):
        PowerBudget(total_w=0.0)


def test_compute_capacity_scales_with_power_and_efficiency():
    # 250 W of compute at 1e11 FLOPS/W -> 2.5e13 FLOPS.
    assert compute_capacity_flops(250.0, 1e11) == pytest.approx(2.5e13)
    assert compute_capacity_flops(500.0, 1e11) == pytest.approx(2 * compute_capacity_flops(250.0, 1e11))


def test_compute_capacity_rejects_bad_inputs():
    with pytest.raises(ValueError):
        compute_capacity_flops(-1.0, 1e11)
    with pytest.raises(ValueError):
        compute_capacity_flops(100.0, 0.0)
