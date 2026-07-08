"""propellant validation: reaction mass, production energy, and propellant closure.

Cross-checks against launch-economics (Tsiolkovsky) and transfer (Delta-v). Anchors:
HHV(H2)=39.4 kWh/kg -> 4.41 kWh/kg water; xenon world supply ~40-60 t/yr (NASA: 10 t is
>10% of it). See REFERENCES.md.
"""

import pytest

from launch_economics.launch import exhaust_velocity_m_s, propellant_fraction

from transfer.low_thrust import edelbaum_delta_v_m_s
from transfer.low_thrust import sep_transfer
from transfer.orbits import BODY_SEMI_MAJOR_AXIS_AU

from propellant.propellant import (
    KORNUTA_FULL_CHAIN_KWH_PER_KG,
    LOX_LH2_FROM_WATER,
    WATER_RESISTOJET,
    XENON_HALL_EP,
    XENON_ION_EP,
    XENON_WORLD_SUPPLY_T_PER_YR,
    compare_routes,
    propellant_closure,
    reaction_mass_kg,
    water_electrolysis_hhv_min_kwh_per_kg,
    xenon_supply_fraction,
)

EARTH = BODY_SEMI_MAJOR_AXIS_AU["earth"]
MARS = BODY_SEMI_MAJOR_AXIS_AU["mars"]


def test_water_electrolysis_hhv_floor_is_4_41():
    # 39.4 kWh/kg H2 x 0.1119 (H2 mass fraction of water) = 4.41 kWh/kg water.
    assert water_electrolysis_hhv_min_kwh_per_kg() == pytest.approx(4.41, rel=1e-2)


def test_full_chain_costs_more_than_the_thermodynamic_floor():
    # Kornuta's mining-to-liquefaction chain must exceed the electrolysis-only floor.
    assert KORNUTA_FULL_CHAIN_KWH_PER_KG > water_electrolysis_hhv_min_kwh_per_kg()


def test_reaction_mass_round_trips_launch_economics():
    dv, isp, dry = 5000.0, 450.0, 1000.0
    m = reaction_mass_kg(dv, isp, dry)
    ve = exhaust_velocity_m_s(isp)
    # m_prop / (m_dry + m_prop) must equal launch-economics' propellant_fraction.
    assert m / (dry + m) == pytest.approx(propellant_fraction(dv, ve), rel=1e-12)


def test_reaction_mass_round_trips_transfer_sep():
    # transfer.sep_transfer and propellant.reaction_mass share the same Tsiolkovsky.
    dv = edelbaum_delta_v_m_s(EARTH, MARS)
    dry = 1000.0
    sep = sep_transfer(dv, isp_s=3000.0, dry_mass_kg=dry,
                       power_w_at_1au=10_000.0, distance_au=1.0, efficiency=0.6)
    assert reaction_mass_kg(dv, 3000.0, dry) == pytest.approx(
        sep.propellant_mass_kg, rel=1e-9
    )


def test_zero_delta_v_needs_no_propellant():
    assert reaction_mass_kg(0.0, 450.0, 1000.0) == 0.0


def test_higher_isp_needs_less_reaction_mass():
    dv, dry = 5000.0, 1000.0
    water = reaction_mass_kg(dv, LOX_LH2_FROM_WATER.isp_s, dry)
    xenon = reaction_mass_kg(dv, XENON_HALL_EP.isp_s, dry)
    assert xenon < water  # high-Isp EP trades mass for economy


def test_propellant_closure_axis():
    # Water route closes on a water body, not on a dry one.
    assert propellant_closure(LOX_LH2_FROM_WATER, body_has_water=True) == 1.0
    assert propellant_closure(WATER_RESISTOJET, body_has_water=True) == 1.0
    assert propellant_closure(LOX_LH2_FROM_WATER, body_has_water=False) == 0.0
    # Noble-gas EP is a hard import wall regardless of water.
    assert propellant_closure(XENON_HALL_EP, body_has_water=True) == 0.0
    assert propellant_closure(XENON_ION_EP, body_has_water=True) == 0.0


def test_xenon_import_wall_matches_nasa_anchor():
    # NASA: a 10 t xenon load is >10% of world annual production.
    frac_high = xenon_supply_fraction(10.0, annual_supply_t=XENON_WORLD_SUPPLY_T_PER_YR[1])
    frac_low = xenon_supply_fraction(10.0, annual_supply_t=XENON_WORLD_SUPPLY_T_PER_YR[0])
    assert frac_high > 0.10  # 10/60 = 0.167
    assert frac_low == pytest.approx(0.25)  # 10/40


def test_the_trade_mass_versus_tether():
    # The payoff: xenon EP carries far less propellant mass, but ALL of it is imported;
    # the water route carries more mass but imports none (on a water body).
    dv, dry = 5000.0, 1000.0
    routes = [LOX_LH2_FROM_WATER, XENON_HALL_EP]
    comps = {c.name: c for c in compare_routes(dv, dry, routes, body_has_water=True)}
    water = comps[LOX_LH2_FROM_WATER.name]
    xenon = comps[XENON_HALL_EP.name]

    # xenon uses less total propellant mass...
    assert xenon.propellant_mass_kg < water.propellant_mass_kg
    # ...but the water route imports zero, while every kg of xenon is a tether to Earth.
    assert water.imported_propellant_kg == 0.0
    assert xenon.imported_propellant_kg == pytest.approx(xenon.propellant_mass_kg)
    # So on a water body the closing route imports strictly less absolute mass.
    assert water.imported_propellant_kg < xenon.imported_propellant_kg


def test_dry_body_forces_water_route_imports_too():
    # No local water: even the "water route" must import its reaction mass.
    dv, dry = 5000.0, 1000.0
    comps = compare_routes(dv, dry, [LOX_LH2_FROM_WATER], body_has_water=False)
    assert comps[0].propellant_closure == 0.0
    assert comps[0].imported_propellant_kg == pytest.approx(comps[0].propellant_mass_kg)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        reaction_mass_kg(-1.0, 450.0, 1000.0)
    with pytest.raises(ValueError):
        reaction_mass_kg(100.0, 450.0, 0.0)
    with pytest.raises(ValueError):
        xenon_supply_fraction(-1.0)
    with pytest.raises(ValueError):
        xenon_supply_fraction(10.0, annual_supply_t=0.0)
