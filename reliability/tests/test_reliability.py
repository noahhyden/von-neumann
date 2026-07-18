"""reliability validation: seeded-fold determinism, the hazard=0 guard, Aurora, decay.

The load-bearing tests are the RNG discipline (CLAUDE.md 7): same seed reproduces
bit-for-bit, and hazard=0 leaves the population untouched (the mandatory regression
against the failure-free models). See REFERENCES.md.
"""

import pytest

from shielding.radenv import GCR_DEEP_SPACE_DOSE_MSV_PER_DAY

from reliability.aurora import aurora_equilibrium, aurora_integrate
from reliability.degradation import (
    ARRAY_DEGRADATION_PER_YR,
    array_power_fraction,
    cumulative_gcr_dose_msv,
)
from reliability.mortality import (
    SATELLITE_HAZARD_PER_DAY,
    FleetState,
    expected_survival_fraction,
    simulate,
    step,
)
from reliability.rng import next_uniform, seed_state


# --- RNG discipline (the sneakiest bug the project warns about) ---

def test_rng_is_deterministic_and_in_range():
    s = seed_state(12345)
    seq1, state = [], s
    for _ in range(5):
        state, u = next_uniform(state)
        assert 0.0 <= u < 1.0
        seq1.append(u)
    # Replaying from the same seed reproduces the identical stream.
    seq2, state = [], seed_state(12345)
    for _ in range(5):
        state, u = next_uniform(state)
        seq2.append(u)
    assert seq1 == seq2
    # A different seed gives a different stream.
    _, first_other = next_uniform(seed_state(54321))
    assert first_other != seq1[0]


def test_mortality_fold_reproduces_bit_for_bit():
    a = simulate(1000, days=200, hazard_per_day=1e-3, seed=7)
    b = simulate(1000, days=200, hazard_per_day=1e-3, seed=7)
    assert a == b  # frozen dataclass equality: rng, alive, day all identical
    # A different seed diverges (near-certain distinct RNG state).
    c = simulate(1000, days=200, hazard_per_day=1e-3, seed=8)
    assert c.rng != a.rng


# --- THE mandatory guard: hazard=0 is a bit-exact regression vs the failure-free model ---

def test_hazard_zero_leaves_population_untouched():
    for seed in (0, 1, 42, 99999):
        s = simulate(5000, days=365, hazard_per_day=0.0, seed=seed)
        assert s.alive == 5000  # nobody dies -> identical to the current (ageless) models
        assert s.day == 365
    # And a single step with hazard 0 never kills, whatever the RNG draws.
    st = FleetState.initial(1000, seed=3)
    st = step(st, hazard_per_day=0.0)
    assert st.alive == 1000


# --- Mortality behaviour ---

def test_simulation_is_unbiased_around_expected_survival():
    # Over a large fleet the surviving fraction tracks (1 - hazard)^days.
    pop, days, hazard = 40_000, 40, 2e-3
    s = simulate(pop, days=days, hazard_per_day=hazard, seed=2024)
    frac = s.alive / pop
    assert frac == pytest.approx(expected_survival_fraction(days, hazard), rel=0.03)


def test_more_hazard_and_more_time_kill_more():
    base = simulate(20_000, days=50, hazard_per_day=1e-3, seed=5).alive
    longer = simulate(20_000, days=200, hazard_per_day=1e-3, seed=5).alive
    harsher = simulate(20_000, days=50, hazard_per_day=5e-3, seed=5).alive
    assert longer < base
    assert harsher < base


def test_satellite_hazard_is_the_documented_proxy():
    # ~1.1e-5/day proxy -> ~0.4%/yr, a plausible slow attrition.
    annual = 1.0 - expected_survival_fraction(365, SATELLITE_HAZARD_PER_DAY)
    assert SATELLITE_HAZARD_PER_DAY == 1.1e-5
    assert 0.003 < annual < 0.006


# --- Aurora steady-state (Carroll-Nellenback 2019, Eq. 32) ---

def test_aurora_equilibrium_formula():
    # T_l = 1000 (spread), T_s = 5000 (lifetime) -> X_eq = 1 - 1/5 = 0.8.
    assert aurora_equilibrium(1000.0, 5000.0) == pytest.approx(0.8)
    # Plateau requires T_l < T_s; otherwise settlement collapses to 0.
    assert aurora_equilibrium(5000.0, 1000.0) == 0.0
    assert aurora_equilibrium(1000.0, 1000.0) == 0.0


def test_aurora_ode_converges_to_equilibrium():
    t_l, t_s = 1000.0, 5000.0
    # t_end = 50000 is ~10 spread-times, long past the plateau (approach constant
    # ~min(T_l, T_s) = 1000). The adaptive solver picks its own step.
    x_final = aurora_integrate(0.01, t_l, t_s, t_end=50000.0)
    assert x_final == pytest.approx(aurora_equilibrium(t_l, t_s), rel=1e-3)
    # When lifetime <= spread time, the fraction decays toward zero.
    x_decay = aurora_integrate(0.5, 5000.0, 1000.0, t_end=50000.0)
    assert x_decay == pytest.approx(0.0, abs=1e-3)


# --- Deterministic degradation ---

def test_array_degradation_is_monotonic_and_starts_at_one():
    assert array_power_fraction(0.0) == 1.0
    f10 = array_power_fraction(10.0)
    f20 = array_power_fraction(20.0)
    assert 1.0 > f10 > f20 > 0.0
    # ~0.3%/yr over a 17-year build-out leaves ~95% of array power.
    assert array_power_fraction(17.0, ARRAY_DEGRADATION_PER_YR) == pytest.approx(0.950, rel=1e-2)


def test_harsh_environment_degrades_faster():
    benign = array_power_fraction(10.0, environment_multiplier=1.0)
    jovian = array_power_fraction(10.0, environment_multiplier=3.0)
    assert jovian < benign


def test_gcr_dose_uses_shared_radenv():
    # Consumes shielding.radenv's rate - one radiation environment, not two.
    assert cumulative_gcr_dose_msv(100.0) == pytest.approx(100.0 * GCR_DEEP_SPACE_DOSE_MSV_PER_DAY)
    assert cumulative_gcr_dose_msv(365.0) == pytest.approx(365.0 * 1.8)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        step(FleetState.initial(10, seed=1), hazard_per_day=1.5)
    with pytest.raises(ValueError):
        array_power_fraction(-1.0)
    with pytest.raises(ValueError):
        aurora_equilibrium(0.0, 1000.0)
    with pytest.raises(ValueError):
        FleetState.initial(-5, seed=1)
