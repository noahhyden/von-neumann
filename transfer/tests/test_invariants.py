"""Postcondition invariants for transfer.HohmannResult (issue #48, phase B)."""

import pytest

from transfer.orbits import HohmannResult, hohmann_transfer


# --- [inv:tr-hohmann] dv_total >= 0, matches |dv1|+|dv2|; transfer_time_days > 0 ---

def test_inv_tr_hohmann_positive():
    r = hohmann_transfer(r1_au=1.0, r2_au=1.5)
    assert r.dv_total_m_s > 0
    assert r.transfer_time_days > 0
    assert abs(r.dv_total_m_s - (abs(r.dv1_m_s) + abs(r.dv2_m_s))) < 1e-6


def test_inv_tr_hohmann_inward_transfer():
    r = hohmann_transfer(r1_au=1.5, r2_au=1.0)
    assert r.dv_total_m_s > 0
    assert r.transfer_time_days > 0


def test_inv_tr_hohmann_rejects_negative_total():
    with pytest.raises(ValueError, match=r"inv:tr-hohmann"):
        HohmannResult(dv1_m_s=1.0, dv2_m_s=1.0, dv_total_m_s=-1.0, transfer_time_days=10.0)


def test_inv_tr_hohmann_rejects_inconsistent_total():
    with pytest.raises(ValueError, match=r"inv:tr-hohmann"):
        HohmannResult(dv1_m_s=100.0, dv2_m_s=100.0, dv_total_m_s=50.0, transfer_time_days=10.0)


def test_inv_tr_hohmann_rejects_nonpositive_time():
    with pytest.raises(ValueError, match=r"inv:tr-hohmann"):
        HohmannResult(dv1_m_s=1.0, dv2_m_s=1.0, dv_total_m_s=2.0, transfer_time_days=0.0)
    with pytest.raises(ValueError, match=r"inv:tr-hohmann"):
        HohmannResult(dv1_m_s=1.0, dv2_m_s=1.0, dv_total_m_s=2.0, transfer_time_days=-1.0)
