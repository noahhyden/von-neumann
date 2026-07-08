"""Low-thrust (SEP / Edelbaum) validation.

Checks: Edelbaum coplanar reduces to |V1-V2| and exceeds the impulsive Hohmann total;
the 1/d^2 power law; the F/P ~ 60 mN/kW cross-check against Psyche; propellant
round-trips against launch-economics; and the Δv -> 0 edge. See transfer-SPEC.md.
"""

import pytest

from launch_economics.launch import propellant_fraction as le_propellant_fraction

from transfer.low_thrust import (
    available_power_w,
    edelbaum_delta_v_m_s,
    sep_thrust_n,
    sep_transfer,
)
from transfer.orbits import BODY_SEMI_MAJOR_AXIS_AU, hohmann_transfer

EARTH = BODY_SEMI_MAJOR_AXIS_AU["earth"]
MARS = BODY_SEMI_MAJOR_AXIS_AU["mars"]
CERES = BODY_SEMI_MAJOR_AXIS_AU["ceres"]
JUPITER = BODY_SEMI_MAJOR_AXIS_AU["jupiter"]


def test_edelbaum_coplanar_earth_mars():
    dv = edelbaum_delta_v_m_s(EARTH, MARS)
    # |V1 - V2| = 29784.8 - 24129 = ~5656 m/s.
    assert dv == pytest.approx(5655.8, rel=1e-3)


def test_edelbaum_coplanar_at_least_impulsive():
    # A continuous spiral is less efficient than a two-burn Hohmann: edelbaum >= total.
    for target in (MARS, CERES, JUPITER):
        edel = edelbaum_delta_v_m_s(EARTH, target)
        hoh = hohmann_transfer(EARTH, target).dv_total_m_s
        assert edel >= hoh


def test_edelbaum_plane_change_adds_delta_v():
    coplanar = edelbaum_delta_v_m_s(EARTH, MARS, plane_change_deg=0.0)
    inclined = edelbaum_delta_v_m_s(EARTH, MARS, plane_change_deg=10.0)
    assert inclined > coplanar


def test_power_law_is_inverse_square():
    p0 = 10_000.0  # 10 kW at 1 AU
    assert available_power_w(p0, 1.0) == pytest.approx(p0, rel=1e-9)
    # At 2.77 AU: 1/2.77^2 = 0.1303 of the 1 AU value.
    assert available_power_w(p0, CERES) == pytest.approx(p0 / CERES**2, rel=1e-9)
    assert available_power_w(p0, CERES) / p0 == pytest.approx(0.1303, rel=1e-3)
    # At 5.2 AU: 1/5.2^2 = 0.0370.
    assert available_power_w(p0, 5.2) / p0 == pytest.approx(0.03698, rel=1e-3)


def test_thrust_to_power_matches_psyche():
    # Psyche Hall thruster: ~60 mN/kW. F/P = 2*eta/(g0*Isp). At Isp 1820 s, eta 0.5:
    # F/P = 2*0.5/(9.80665*1820) = 5.60e-5 N/W = 56 mN/kW - matches ~60 mN/kW.
    f = sep_thrust_n(power_w=1000.0, isp_s=1820.0, efficiency=0.5)
    # 56 mN/kW = 56e-3 N / 1000 W = 5.6e-5 N/W.
    assert f / 1000.0 == pytest.approx(5.6e-5, rel=0.05)
    # And per kW it is ~56 mN, within ~10% of Psyche's quoted ~60 mN/kW.
    assert f == pytest.approx(60e-3, rel=0.10)


def test_higher_isp_gives_less_thrust_per_watt():
    # For fixed power, thrust falls as 1/Isp (high-Isp trades thrust for economy).
    low = sep_thrust_n(1000.0, isp_s=1500.0, efficiency=0.5)
    high = sep_thrust_n(1000.0, isp_s=4000.0, efficiency=0.5)
    assert high < low
    assert low / high == pytest.approx(4000.0 / 1500.0, rel=1e-9)


def test_sep_trip_time_grows_with_distance():
    # Same leg Δv, but thrust falls with distance, so the trip stretches.
    dv = edelbaum_delta_v_m_s(EARTH, MARS)
    near = sep_transfer(dv, isp_s=3000.0, dry_mass_kg=1000.0,
                        power_w_at_1au=10_000.0, distance_au=1.0, efficiency=0.6)
    far = sep_transfer(dv, isp_s=3000.0, dry_mass_kg=1000.0,
                       power_w_at_1au=10_000.0, distance_au=CERES, efficiency=0.6)
    assert far.power_at_distance_w < near.power_at_distance_w
    assert far.trip_time_days > near.trip_time_days


def test_sep_propellant_round_trips_launch_economics():
    # propellant_mass / wet_mass must equal launch-economics' propellant_fraction
    # for the same (Δv, Isp) - single source of truth for Tsiolkovsky.
    dv, isp, dry = 5655.8, 3000.0, 1000.0
    r = sep_transfer(dv, isp_s=isp, dry_mass_kg=dry,
                     power_w_at_1au=10_000.0, distance_au=1.0, efficiency=0.6)
    wet = dry + r.propellant_mass_kg
    ve = isp * 9.80665
    assert r.propellant_mass_kg / wet == pytest.approx(
        le_propellant_fraction(dv, ve), rel=1e-9
    )


def test_sep_propellant_far_below_chemical():
    # High-Isp SEP uses a fraction of the reaction mass a chemical stage would for the
    # same Δv. Compare propellant per kg of dry mass.
    dv, dry = 5655.8, 1000.0
    sep = sep_transfer(dv, isp_s=3000.0, dry_mass_kg=dry,
                       power_w_at_1au=10_000.0, distance_au=1.0, efficiency=0.6)
    chem = sep_transfer(dv, isp_s=450.0, dry_mass_kg=dry,
                        power_w_at_1au=10_000.0, distance_au=1.0, efficiency=0.6)
    ratio = sep.propellant_mass_kg / chem.propellant_mass_kg
    # SEP reaction mass is well under a fifth of the chemical case here.
    assert ratio < 0.2
    assert ratio > 0.0


def test_zero_delta_v_means_zero_propellant_and_time():
    r = sep_transfer(0.0, isp_s=3000.0, dry_mass_kg=1000.0,
                     power_w_at_1au=10_000.0, distance_au=1.0, efficiency=0.6)
    assert r.propellant_mass_kg == 0.0  # exp(0) - 1 = 0
    assert r.trip_time_days == 0.0


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        sep_transfer(-1.0, 3000.0, 1000.0, 10_000.0, 1.0, 0.6)
    with pytest.raises(ValueError):
        sep_transfer(100.0, 3000.0, 0.0, 10_000.0, 1.0, 0.6)
    with pytest.raises(ValueError):
        sep_thrust_n(1000.0, 3000.0, efficiency=1.5)
    with pytest.raises(ValueError):
        available_power_w(-1.0, 1.0)
