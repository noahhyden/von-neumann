"""thermal validation: Stefan-Boltzmann sizing, the ISS anchor, T^4 leverage, distance.

The ISS External Active Thermal Control System (70 kW total, 35 kW/loop, ~275 K coolant,
70.3 m^2 radiator assembly) is the flight anchor. See REFERENCES.md.
"""

import pytest

from thermal.thermal import (
    ISS_HEAT_REJECTION_PER_LOOP_KW,
    ISS_RADIATOR_ASSEMBLY_AREA_M2,
    ISS_RADIATOR_TEMP_K,
    RADIATOR_SPECIFIC_MASS_KG_M2,
    STEFAN_BOLTZMANN_W_M2_K4,
    mass_per_kw_kg,
    net_flux_with_solar_load_w_m2,
    radiated_flux_w_m2,
    radiator_area_m2,
    radiator_mass_kg,
    size_radiator,
)


def test_stefan_boltzmann_constant():
    assert STEFAN_BOLTZMANN_W_M2_K4 == pytest.approx(5.670374419e-8)


def test_flux_at_iss_temperature():
    # Two-sided radiator at 275 K, eps 0.8, deep-space sink: ~519 W/m^2.
    q = radiated_flux_w_m2(ISS_RADIATOR_TEMP_K, emissivity=0.8, sink_temp_k=0.0, sides=2)
    assert q == pytest.approx(518.9, rel=1e-3)


def test_flux_scales_as_t_fourth():
    q1 = radiated_flux_w_m2(300.0)
    q2 = radiated_flux_w_m2(600.0)
    assert q2 / q1 == pytest.approx(16.0, rel=1e-9)  # (600/300)^4 = 16


def test_iss_assembly_area_reproduces_per_loop_capacity():
    # One ISS radiator assembly (8 panels of 3.33 x 2.64 m) = 70.3 m^2.
    assert ISS_RADIATOR_ASSEMBLY_AREA_M2 == pytest.approx(70.33, rel=1e-3)
    # Stefan-Boltzmann sizing for 35 kW at 275 K needs ~67.5 m^2 - within ~4% of the
    # real assembly, which rejects ~35 kW per loop. A genuine flight anchor.
    area = radiator_area_m2(
        ISS_HEAT_REJECTION_PER_LOOP_KW * 1000.0, ISS_RADIATOR_TEMP_K, emissivity=0.8
    )
    assert area == pytest.approx(67.5, rel=1e-2)
    assert abs(area - ISS_RADIATOR_ASSEMBLY_AREA_M2) / ISS_RADIATOR_ASSEMBLY_AREA_M2 < 0.10


def test_hot_radiator_is_about_10x_lighter_per_kw():
    # (533/300)^4 = 9.96: a ~530 K smelting radiator is ~10x lighter per kW than a
    # ~300 K electronics radiator - why one radiator temperature for all is wrong.
    cold = mass_per_kw_kg(300.0)
    hot = mass_per_kw_kg(533.0)
    assert hot < cold
    assert cold / hot == pytest.approx((533.0 / 300.0) ** 4, rel=1e-9)
    assert cold / hot == pytest.approx(9.96, rel=1e-2)


def test_mass_is_area_times_specific_mass():
    r = size_radiator(35_000.0, 275.0, emissivity=0.8)
    assert r.mass_kg == pytest.approx(r.area_m2 * RADIATOR_SPECIFIC_MASS_KG_M2)
    assert radiator_mass_kg(100.0) == pytest.approx(300.0)  # 3 kg/m^2 target


def test_solar_load_makes_radiators_worse_near_the_sun():
    # Net flux rises with distance as the parasitic solar load falls as 1/d^2.
    near = net_flux_with_solar_load_w_m2(300.0, distance_au=1.0, absorptivity=0.2)
    far = net_flux_with_solar_load_w_m2(300.0, distance_au=5.0, absorptivity=0.2)
    assert far > near
    # Far out it approaches the full two-sided T^4 flux (no parasitic load).
    gross = radiated_flux_w_m2(300.0, emissivity=0.8, sides=2)
    assert far == pytest.approx(gross, rel=0.02)
    # So the radiator area to reject a fixed load is larger near the Sun.
    q = 20_000.0
    assert q / near > q / far


def test_cold_radiator_cannot_reject_heat_too_close_to_sun():
    # A 300 K radiator at 0.3 AU absorbs more sunlight than it emits -> refuse.
    with pytest.raises(ValueError):
        net_flux_with_solar_load_w_m2(300.0, distance_au=0.3, absorptivity=0.2)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        radiated_flux_w_m2(0.0)  # non-positive temp
    with pytest.raises(ValueError):
        radiated_flux_w_m2(300.0, emissivity=1.5)  # emissivity > 1
    with pytest.raises(ValueError):
        radiated_flux_w_m2(300.0, sink_temp_k=350.0)  # sink hotter than radiator
    with pytest.raises(ValueError):
        radiated_flux_w_m2(300.0, sides=3)  # not 1 or 2
    with pytest.raises(ValueError):
        radiator_mass_kg(100.0, specific_mass_kg_m2=0.0)
