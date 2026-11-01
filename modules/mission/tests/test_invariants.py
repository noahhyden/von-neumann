"""Aggregator invariants for mission.run_mission (issue #48, phase B)."""

from dataclasses import replace

import pytest

from mission import default_mission_scenario, run_mission
from mission.run import _verify_mission_result


def test_inv_ms_composite_positive():
    r = run_mission(default_mission_scenario())
    _verify_mission_result(r)


def test_inv_ms_closure_out_of_range_negative():
    r = run_mission(default_mission_scenario())
    bad = replace(r, closure_ratio=1.5)
    with pytest.raises(AssertionError, match=r"inv:ms-composite-closure"):
        _verify_mission_result(bad)


def test_inv_ms_dv_sign_negative():
    r = run_mission(default_mission_scenario())
    bad = replace(r, delta_v_m_s=-1.0)
    with pytest.raises(AssertionError, match=r"inv:ms-dv-sign"):
        _verify_mission_result(bad)


def test_inv_ms_negative_mass_rejected():
    r = run_mission(default_mission_scenario())
    bad = replace(r, seed_mass_kg=-1.0)
    with pytest.raises(AssertionError, match=r"inv:ms-dv-sign"):
        _verify_mission_result(bad)


def test_inv_ms_split_exceeds_delivered_negative():
    r = run_mission(default_mission_scenario())
    bad = replace(r, manufacturing_w=r.delivered_power_w * 2.0)
    with pytest.raises(AssertionError, match=r"inv:ms-composite-closure"):
        _verify_mission_result(bad)
