"""Solar-environment physics: assert real numbers and edges, not just execution."""

import math

import pytest

from probe_sim.environment import (
    AU_DISTANCE,
    SOLAR_CONSTANT_1AU_W_M2,
    SolarArray,
    solar_irradiance_w_m2,
)


def test_irradiance_at_1au_is_the_solar_constant():
    assert solar_irradiance_w_m2(1.0) == pytest.approx(SOLAR_CONSTANT_1AU_W_M2)


def test_inverse_square_law():
    # Doubling distance quarters irradiance.
    assert solar_irradiance_w_m2(2.0) == pytest.approx(SOLAR_CONSTANT_1AU_W_M2 / 4)


def test_jupiter_is_about_50_w_m2():
    # Independent check against Borgue & Hein (2020): "~50 W/m^2 near Jupiter".
    assert solar_irradiance_w_m2(AU_DISTANCE["jupiter"]) == pytest.approx(50.3, abs=1.0)


def test_irradiance_decreases_monotonically_with_distance():
    distances = [1.0, 1.524, 2.0, 5.203, 9.5]
    vals = [solar_irradiance_w_m2(d) for d in distances]
    assert all(a > b for a, b in zip(vals, vals[1:]))


def test_nonpositive_distance_raises():
    with pytest.raises(ValueError):
        solar_irradiance_w_m2(0.0)
    with pytest.raises(ValueError):
        solar_irradiance_w_m2(-1.0)


def test_array_power_scales_with_area_efficiency_and_distance():
    array = SolarArray(area_m2=2.0, efficiency=0.30)
    # At 1 AU: S0 * area * efficiency.
    assert array.power_w(1.0) == pytest.approx(SOLAR_CONSTANT_1AU_W_M2 * 2.0 * 0.30)
    # Inverse-square carries through to delivered power.
    assert array.power_w(2.0) == pytest.approx(array.power_w(1.0) / 4)


def test_max_distance_is_the_inverse_of_power():
    array = SolarArray(area_m2=5.0, efficiency=0.30)
    demand = array.power_w(3.0)
    # The farthest distance meeting exactly that demand is where we measured it.
    assert array.max_distance_au(demand) == pytest.approx(3.0)


def test_max_distance_farther_array_reaches_farther():
    small = SolarArray(area_m2=2.0, efficiency=0.30)
    big = SolarArray(area_m2=8.0, efficiency=0.30)
    demand = 50.0  # W
    assert big.max_distance_au(demand) > small.max_distance_au(demand)
    # 4x area -> 2x reach (sqrt).
    assert big.max_distance_au(demand) == pytest.approx(2 * small.max_distance_au(demand))


def test_solar_array_rejects_invalid_config():
    with pytest.raises(ValueError):
        SolarArray(area_m2=0, efficiency=0.3)
    with pytest.raises(ValueError):
        SolarArray(area_m2=1.0, efficiency=1.5)
    with pytest.raises(ValueError):
        SolarArray(area_m2=1.0, efficiency=0.3).max_distance_au(0)
