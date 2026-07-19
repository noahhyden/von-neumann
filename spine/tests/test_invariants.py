"""Aggregator invariants for spine.run_spine (issue #48, phase B)."""

from dataclasses import replace

import pytest

from spine import SpineScenario, run_spine
from spine.run import _verify_spine_result


def _result():
    return run_spine(SpineScenario.default())


def test_inv_sp_scale_order_positive():
    r = _result()
    _verify_spine_result(r)


def test_inv_sp_closure_out_of_range_negative():
    r = _result()
    bad = replace(r, closure_ratio=-0.1)
    with pytest.raises(AssertionError, match=r"inv:sp-scale-order"):
        _verify_spine_result(bad)


def test_inv_sp_copy_time_nonpositive_negative():
    r = _result()
    bad = replace(r, copy_time_days=0.0)
    with pytest.raises(AssertionError, match=r"inv:sp-scale-order"):
        _verify_spine_result(bad)


def test_inv_sp_settle_time_year_derivation_negative():
    # settle_time_years is DERIVED from copy_time_days; drifting it is illegal.
    r = _result()
    bad = replace(r, settle_time_years=r.settle_time_years + 100.0)
    with pytest.raises(AssertionError, match=r"inv:sp-scale-order"):
        _verify_spine_result(bad)


def test_inv_sp_final_settled_exceeds_n_stars_negative():
    r = _result()
    bad = replace(r, final_settled=r.n_stars + 1)
    with pytest.raises(AssertionError, match=r"inv:sp-scale-order"):
        _verify_spine_result(bad)


def test_inv_sp_dwell_negative_rejected():
    r = _result()
    if r.dwell_fraction_of_t100 is not None:
        bad = replace(r, dwell_fraction_of_t100=-0.5)
        with pytest.raises(AssertionError, match=r"inv:sp-dwell-nonneg"):
            _verify_spine_result(bad)
