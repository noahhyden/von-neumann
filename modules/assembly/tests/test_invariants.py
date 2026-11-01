"""Postcondition invariants for assembly (issue #48, phase B)."""

import pytest

from assembly.rate import BuildRateBand, build_rate_band


# --- [inv:as-band] low > 0, low <= anchor <= high ---

def test_inv_as_band_positive():
    band = build_rate_band()
    assert band.low_kg_per_day > 0
    assert band.low_kg_per_day <= band.anchor_kg_per_day <= band.high_kg_per_day


def test_inv_as_band_rejects_zero_low():
    with pytest.raises(ValueError, match=r"inv:as-band"):
        BuildRateBand(low_kg_per_day=0.0, anchor_kg_per_day=1.0, high_kg_per_day=2.0)


def test_inv_as_band_rejects_negative_low():
    with pytest.raises(ValueError, match=r"inv:as-band"):
        BuildRateBand(low_kg_per_day=-1.0, anchor_kg_per_day=1.0, high_kg_per_day=2.0)


def test_inv_as_band_rejects_anchor_below_low():
    with pytest.raises(ValueError, match=r"inv:as-band"):
        BuildRateBand(low_kg_per_day=5.0, anchor_kg_per_day=1.0, high_kg_per_day=10.0)


def test_inv_as_band_rejects_anchor_above_high():
    with pytest.raises(ValueError, match=r"inv:as-band"):
        BuildRateBand(low_kg_per_day=1.0, anchor_kg_per_day=100.0, high_kg_per_day=10.0)
