"""Postcondition invariants for power_budget (issue #48, phase B)."""

import pytest

from power_budget.budget import PowerBudget, _verify_power_split


# --- [inv:pb-split] manufacturing_w + compute_w + housekeeping_w + unallocated_w == total_w ---

def test_inv_pb_split_positive():
    pb = PowerBudget(
        total_w=1000.0,
        fraction_manufacturing=0.5,
        fraction_compute=0.3,
        fraction_housekeeping=0.1,
    )
    _verify_power_split(pb)


def test_inv_pb_split_all_zero_fractions():
    pb = PowerBudget(total_w=1000.0)
    _verify_power_split(pb)
    assert pb.unallocated_w == pytest.approx(1000.0)


def test_inv_pb_split_full_allocation():
    pb = PowerBudget(
        total_w=100.0,
        fraction_manufacturing=0.5,
        fraction_compute=0.3,
        fraction_housekeeping=0.2,
    )
    _verify_power_split(pb)
    assert pb.unallocated_w == pytest.approx(0.0, abs=1e-9)


def test_inv_pb_split_over_allocation_rejected_at_construction():
    # The pydantic validator catches this before _verify_power_split is even called.
    with pytest.raises(Exception, match=r"over-allocated"):
        PowerBudget(
            total_w=100.0,
            fraction_manufacturing=0.6,
            fraction_compute=0.5,
            fraction_housekeeping=0.0,
        )


class _BadPB:
    """A stand-in that pretends to be a PowerBudget but breaks the partition."""
    total_w = 1000.0
    manufacturing_w = 400.0
    compute_w = 400.0
    housekeeping_w = 400.0  # sums to 1200 > total, illegal
    unallocated_w = 0.0


def test_inv_pb_split_rejects_broken_partition():
    with pytest.raises(AssertionError, match=r"inv:pb-split"):
        _verify_power_split(_BadPB())
