"""shielding validation: mass conversion, the Juno anchor, GCR non-monotonicity, closure.

Anchors: Juno vault ~200 kg (1 cm Ti, ~800x TID reduction), Europa Clipper 150 kg, GCR
dose-equivalent minimum ~20 g/cm^2 Al. See REFERENCES.md.
"""

import math

import pytest

from shielding.radenv import (
    EUROPA_CLIPPER_VAULT_MASS_KG,
    GCR_DOSE_MIN_AREAL_DENSITY_G_CM2,
    JUNO_ANTICIPATED_TID_RAD,
    JUNO_VAULT_ATTENUATION_FACTOR,
    JUNO_VAULT_MASS_KG,
    TITANIUM_DENSITY_G_CM3,
    jovian_tid_attenuation_length_g_cm2,
    juno_ti_wall_areal_density_g_cm2,
)
from shielding.shielding import (
    areal_density_for_tid_budget,
    areal_density_from_thickness,
    closure_contribution_kg,
    gcr_shielding_is_counterproductive,
    recommend_gcr_areal_density,
    regolith_thickness_for_areal_density_cm,
    shield_mass_kg,
    tid_attenuation_factor,
)


def test_areal_density_and_mass_conversion():
    # 1 cm titanium = 4.51 g/cm^2.
    assert areal_density_from_thickness(1.0, TITANIUM_DENSITY_G_CM3) == pytest.approx(4.51)
    # 1 g/cm^2 over 1 m^2 = 10 kg.
    assert shield_mass_kg(1.0, 1.0) == pytest.approx(10.0)


def test_juno_vault_mass_reproduced_from_geometry():
    # Juno: 1 cm Ti walls; ~4.4 m^2 of wall gives its ~200 kg vault.
    ti = juno_ti_wall_areal_density_g_cm2()
    area_for_200kg = JUNO_VAULT_MASS_KG / (ti * 10.0)
    assert shield_mass_kg(ti, area_for_200kg) == pytest.approx(JUNO_VAULT_MASS_KG, rel=1e-6)
    # A full 6-face 1 m^2 cube of 1 cm Ti is ~270 kg - same order as the real 200 kg.
    cube = shield_mass_kg(ti, 6.0)
    assert 150.0 < cube < 350.0
    # Europa Clipper's vault is lighter than Juno's (composite vs all-titanium).
    assert EUROPA_CLIPPER_VAULT_MASS_KG < JUNO_VAULT_MASS_KG


def test_tid_attenuation_reproduces_juno_800x():
    # By construction lambda is fit so 4.51 g/cm^2 gives an 800x reduction.
    ti = juno_ti_wall_areal_density_g_cm2()
    factor = tid_attenuation_factor(ti)
    assert factor == pytest.approx(1.0 / JUNO_VAULT_ATTENUATION_FACTOR, rel=1e-9)
    assert jovian_tid_attenuation_length_g_cm2() == pytest.approx(4.51 / math.log(800.0), rel=1e-9)


def test_tid_is_monotonic_more_shield_less_dose():
    thin = tid_attenuation_factor(2.0)
    thick = tid_attenuation_factor(6.0)
    assert thick < thin  # more areal density lets less dose through
    assert 0 < thick < thin <= 1.0


def test_areal_density_for_tid_budget():
    # To cut 20 Mrad to the vault-internal level (800x) needs Juno's 4.51 g/cm^2.
    sigma = areal_density_for_tid_budget(
        JUNO_ANTICIPATED_TID_RAD, JUNO_ANTICIPATED_TID_RAD / JUNO_VAULT_ATTENUATION_FACTOR
    )
    assert sigma == pytest.approx(juno_ti_wall_areal_density_g_cm2(), rel=1e-9)
    # Already within budget -> no shielding needed.
    assert areal_density_for_tid_budget(1000.0, 2000.0) == 0.0


def test_gcr_dose_is_non_monotonic_and_capped():
    # The crucial trap: beyond ~20 g/cm^2 Al, thicker shielding is WORSE for GCR.
    assert GCR_DOSE_MIN_AREAL_DENSITY_G_CM2 == 20.0
    assert gcr_shielding_is_counterproductive(25.0)
    assert not gcr_shielding_is_counterproductive(15.0)
    assert not gcr_shielding_is_counterproductive(20.0)
    # The module refuses to recommend more than the minimum.
    assert recommend_gcr_areal_density(50.0) == 20.0
    assert recommend_gcr_areal_density(10.0) == 10.0


def test_regolith_substitutes_for_metal_at_equal_areal_density():
    # 1 cm Ti (4.51 g/cm^2) is matched by ~2.82 cm of regolith (density 1.6).
    ti = juno_ti_wall_areal_density_g_cm2()
    regolith_cm = regolith_thickness_for_areal_density_cm(ti)
    assert regolith_cm == pytest.approx(4.51 / 1.6, rel=1e-9)
    assert regolith_cm > 1.0  # lower density -> more thickness for the same shielding
    # First-order, the same areal density gives the same TID attenuation either way.
    assert tid_attenuation_factor(regolith_cm * 1.6) == pytest.approx(
        tid_attenuation_factor(ti), rel=1e-9
    )


def test_local_shielding_raises_closure_imported_does_not():
    mass = shield_mass_kg(20.0, 3.0)  # a big regolith GCR shield
    assert closure_contribution_kg(mass, locally_producible=True) == pytest.approx(mass)
    assert closure_contribution_kg(mass, locally_producible=False) == 0.0


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        areal_density_from_thickness(1.0, 0.0)
    with pytest.raises(ValueError):
        shield_mass_kg(-1.0, 1.0)
    with pytest.raises(ValueError):
        areal_density_for_tid_budget(0.0, 100.0)
    with pytest.raises(ValueError):
        regolith_thickness_for_areal_density_cm(4.51, regolith_density_g_cm3=0.0)
