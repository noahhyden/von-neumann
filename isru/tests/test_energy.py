"""isru energy validation: the sourced LOX and metal specific energies.

Anchors: PNAS 2025 full-chain LOX (24.3 +/- 5.8 kWh/kg; H2-reduction ~55% +
electrolysis ~38% + liquefaction ~4.8%), and molten-oxide-electrolysis iron
(2.6 theoretical / 3.7 practical kWh/kg). See REFERENCES.md.
"""

import pytest

from isru.energy import (
    CLOSURE_SIM_IRON_KWH_PER_KG,
    OXYGEN_ENERGY_SHARES,
    WATER_ICE_LOX_KWH_PER_KG,
    metal_energy_kwh_per_kg,
    oxygen_energy_kwh_per_kg,
)


def test_oxygen_full_chain_central_and_band():
    b = oxygen_energy_kwh_per_kg()
    assert b.central_kwh_per_kg == pytest.approx(24.3)
    assert b.low_kwh_per_kg == pytest.approx(18.5)
    assert b.high_kwh_per_kg == pytest.approx(30.1)


def test_oxygen_band_within_taylor_carrier_range():
    # Taylor & Carrier (1993) put LOX production across technologies at 18-35 kWh/kg;
    # the PNAS central+band must sit inside that independent envelope.
    b = oxygen_energy_kwh_per_kg()
    assert 18.0 <= b.low_kwh_per_kg
    assert b.high_kwh_per_kg <= 35.0


def test_oxygen_shares_are_reduction_dominated_and_sub_unity():
    total = sum(OXYGEN_ENERGY_SHARES.values())
    # Reduction + electrolysis + liquefaction ~= 0.978; the rest (<5%) is unlisted.
    assert total == pytest.approx(0.978, abs=1e-9)
    assert total < 1.0
    # Hydrogen reduction is the single largest step.
    assert OXYGEN_ENERGY_SHARES["hydrogen_reduction"] == max(OXYGEN_ENERGY_SHARES.values())


def test_dropping_liquefaction_lowers_energy():
    liq = oxygen_energy_kwh_per_kg(include_liquefaction=True).central_kwh_per_kg
    gas = oxygen_energy_kwh_per_kg(include_liquefaction=False).central_kwh_per_kg
    assert gas < liq
    assert gas == pytest.approx(24.3 * (1 - 0.048), rel=1e-9)


def test_metal_moe_retires_closure_sim_five():
    # The derived practical figure grounds and slightly undercuts closure-sim's 5.0.
    practical = metal_energy_kwh_per_kg("practical")
    assert practical == pytest.approx(3.7)
    assert practical < CLOSURE_SIM_IRON_KWH_PER_KG
    # Ordering: thermodynamic floor < practical < global-scale, all below the old 5.0.
    theo = metal_energy_kwh_per_kg("theoretical")
    glob = metal_energy_kwh_per_kg("global_scale")
    assert theo < practical <= glob < CLOSURE_SIM_IRON_KWH_PER_KG


def test_oxygen_far_costlier_than_metal():
    # Oxygen extraction dominates the energy story - it is ~6-7x the metal figure.
    ox = oxygen_energy_kwh_per_kg().central_kwh_per_kg
    metal = metal_energy_kwh_per_kg("practical")
    assert ox / metal > 5.0


def test_water_ice_route_is_a_distinct_cheaper_lox_basis():
    # Kornuta's water-ice LOX (~11.3 kWh/kg) is a different feedstock, cheaper than the
    # regolith route - the seam to the propellant module. Must not be conflated.
    assert WATER_ICE_LOX_KWH_PER_KG == pytest.approx(11.3)
    assert WATER_ICE_LOX_KWH_PER_KG < oxygen_energy_kwh_per_kg().central_kwh_per_kg


def test_invalid_basis_raises():
    with pytest.raises(ValueError):
        metal_energy_kwh_per_kg("magic")
