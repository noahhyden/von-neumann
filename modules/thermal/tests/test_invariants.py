"""Postcondition invariants for thermal (issue #48, phase B)."""

import pytest

from thermal.thermal import RadiatorResult, size_radiator


# --- [inv:th-radiator] flux > 0, area >= 0, mass >= 0 ---

def test_inv_th_radiator_positive():
    r = size_radiator(heat_w=1000.0, temp_k=300.0)
    assert r.flux_w_m2 > 0
    assert r.area_m2 >= 0
    assert r.mass_kg >= 0


def test_inv_th_radiator_zero_heat_load_is_legal():
    # A zero-heat call gives area=mass=0; flux is still positive (radiator can radiate).
    r = size_radiator(heat_w=0.0, temp_k=300.0)
    assert r.area_m2 == 0.0
    assert r.mass_kg == 0.0
    assert r.flux_w_m2 > 0


def test_inv_th_radiator_rejects_nonpositive_flux():
    with pytest.raises(ValueError, match=r"inv:th-radiator"):
        RadiatorResult(flux_w_m2=0.0, area_m2=1.0, mass_kg=1.0)
    with pytest.raises(ValueError, match=r"inv:th-radiator"):
        RadiatorResult(flux_w_m2=-1.0, area_m2=1.0, mass_kg=1.0)


def test_inv_th_radiator_rejects_negative_area():
    with pytest.raises(ValueError, match=r"inv:th-radiator"):
        RadiatorResult(flux_w_m2=1.0, area_m2=-1.0, mass_kg=1.0)


def test_inv_th_radiator_rejects_negative_mass():
    with pytest.raises(ValueError, match=r"inv:th-radiator"):
        RadiatorResult(flux_w_m2=1.0, area_m2=1.0, mass_kg=-1.0)
