"""Operational-range mechanism: power vs distance gating replication viability.

These use a small SYNTHETIC factory to exercise the sweep/bisection logic - the
values are test scaffolding, not physical claims (the real Borgue & Hein probe
factory awaits the per-module mass [GAP]; see REFERENCES.md). The assertions are on
structural behaviour: monotonic viability, correct crossover bracketing, and the
underpowered / saturated edges.

With this fixture the crossover is clean: local build energy is 100 kWh/kg over
1000 kg of local mass, so e_local = 100 kWh/kg and energy_cap = power_kwh_per_day /
100. Output reaches the 50 kg/day target iff energy_cap >= 50, i.e. iff
available_power_kw >= 50 * 100 / 24 ~= 208 kW.
"""

import pytest
from closure_sim.models import Factory, ReplicationParams, Subsystem

from probe_sim.environment import SolarArray
from probe_sim.range import is_viable_at, operational_range


def make_factory() -> Factory:
    return Factory(
        name="synthetic-test-probe",
        subsystems=[
            Subsystem(
                name="structure",
                mass_kg=1000.0,
                category="structure",
                producible_locally=True,
                energy_to_produce_kwh_per_kg=100.0,
            ),
            Subsystem(
                name="chips",
                mass_kg=100.0,
                category="electronics",
                producible_locally=False,
            ),
        ],
    )


def make_rep() -> ReplicationParams:
    return ReplicationParams(
        seed_mass_kg=1000.0,
        local_build_rate_kg_per_day=10.0,
        vitamin_resupply_mass_kg=1000.0,  # generous: resupply never binds here
        resupply_cadence_days=30.0,
        available_power_kw=1000.0,  # placeholder; overridden per distance
        target_output_kg_per_day=50.0,
        duration_days=3650,
        dt_days=1.0,
    )


def test_viable_close_in_but_not_far_out():
    array = SolarArray(area_m2=200.0, efficiency=0.30)
    factory, rep = make_factory(), make_rep()
    assert is_viable_at(array, factory, rep, 0.4) is True
    assert is_viable_at(array, factory, rep, 10.0) is False


def test_operational_range_brackets_the_crossover():
    array = SolarArray(area_m2=200.0, efficiency=0.30)
    factory, rep = make_factory(), make_rep()
    result = operational_range(array, factory, rep, lo_au=0.3, hi_au=40.0)

    assert result.operational_range_au is not None
    assert not result.saturated
    d = result.operational_range_au
    assert 0.3 < d < 40.0
    # Viable just inside the range, not viable just outside it.
    assert is_viable_at(array, factory, rep, d - 0.01) is True
    assert is_viable_at(array, factory, rep, d + 0.01) is False


def test_underpowered_probe_has_no_range():
    tiny = SolarArray(area_m2=1.0, efficiency=0.30)  # ~4.5 kW at 0.3 AU, far below 208
    factory, rep = make_factory(), make_rep()
    result = operational_range(tiny, factory, rep, lo_au=0.3, hi_au=40.0)
    assert result.operational_range_au is None
    assert not result.saturated


def test_oversized_array_saturates_search_ceiling():
    huge = SolarArray(area_m2=1_000_000.0, efficiency=0.30)
    factory, rep = make_factory(), make_rep()
    result = operational_range(huge, factory, rep, lo_au=0.3, hi_au=40.0)
    assert result.saturated is True
    assert result.operational_range_au == pytest.approx(40.0)


def test_bigger_array_reaches_farther_by_sqrt_of_area():
    factory, rep = make_factory(), make_rep()
    small = operational_range(
        SolarArray(area_m2=200.0, efficiency=0.30), factory, rep
    ).operational_range_au
    big = operational_range(
        SolarArray(area_m2=800.0, efficiency=0.30), factory, rep
    ).operational_range_au
    assert small is not None and big is not None
    assert big > small
    # 4x collector area -> 2x reach (power ~ area, distance ~ sqrt(power)).
    assert big == pytest.approx(2 * small, rel=0.02)
