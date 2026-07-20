"""Analytical companions for thermal (issue #50, Phase 2; #14/#15).

`docs/FINDINGS_CLASSIFICATION.md` classes both thermal headlines as A:

- **#14 T^4 leverage** - a hot radiator is ~10x lighter per kW than a cold one.
- **#15 ISS anchor** - Stefan-Boltzmann sizing reproduces flight hardware.

These are not just point values (`test_thermal.py` already checks those); the
companion states the *closed forms* and proves the structural fact the point
tests do not: in the leverage RATIO, the emissivity, the Stefan-Boltzmann
constant, the areal density, the side count, and the heat load all CANCEL. The
leverage is set by the temperature ratio alone (with a sink correction) - the
same "the obvious inputs cancel" shape as #24 (power cancels) and #30.

## Derivation

A two-faced radiator at temperature `T` with emissivity `eps`, radiating to a
sink at `T_s`, rejects (Stefan-Boltzmann, `sides` emitting faces):

    q(T) = sides * eps * sigma * (T^4 - T_s^4)          [W/m^2]           (1)

To reject a heat load `P`, the area is `A = P / q(T)`; at areal density `mu`
(kg/m^2) the mass is `m = mu * A`. Mass per kilowatt is therefore

    mass_per_kw(T) = 1000 * mu / q(T)
                   = 1000 * mu / (sides * eps * sigma * (T^4 - T_s^4))     (2)

which falls as `1/T^4` for `T >> T_s`: the T^4 leverage.

**The leverage ratio (the closed form worth naming).** Compare a cold radiator
at `T_c` to a hot one at `T_h > T_c`, same `eps`, `mu`, `sides`, `sigma`, sink:

    L(T_h, T_c) = mass_per_kw(T_c) / mass_per_kw(T_h)
                = q(T_h) / q(T_c)
                = (T_h^4 - T_s^4) / (T_c^4 - T_s^4)                        (3)

Every common factor - `sides`, `eps`, `sigma`, `mu`, and the heat load `P` -
divides out. The advantage of running hot depends *only* on the two
temperatures and the sink. In the deep-space limit `T_s -> 0`:

    L(T_h, T_c) -> (T_h / T_c)^4                                          (4)

so `L(533, 300) = (533/300)^4 = 9.96` - the "~10x lighter hot radiator".

**Sink correction (sign is derivable).** For `0 < T_s < T_c < T_h`, subtracting
the same `T_s^4` from a larger numerator and smaller denominator *raises* the
ratio: `(a - x)/(b - x) > a/b` when `a > b > x > 0`. So a warm sink makes the
hot radiator's advantage *larger*, not smaller:

    L_sink(T_h, T_c) > (T_h / T_c)^4   for T_s > 0                        (5)

and `L -> infinity` as `T_c -> T_s+` (a radiator barely above its sink rejects
almost nothing per kg, so its mass/kW diverges).

**ISS anchor (#15).** Inverting (1) at the flight point (`P = 35 kW`,
`T = 275 K`, `eps = 0.8`, two-sided, deep-space sink):

    A = P / q(275) = 35000 / (2 * 0.8 * sigma * 275^4)
      = 35000 / 518.9  ~= 67.5 m^2

within ~4% of the real 70.3 m^2 assembly that rejects ~35 kW per loop.

## Test coverage
- `mass_per_kw_kg` matches (2) to 1e-12 relative across a (T, eps, mu, sides) grid.
- The leverage ratio (3)/(4) matches the sim, and is invariant to eps, mu, sides,
  and heat load (the cancellation) - the structural result.
- The sink correction (5) has the derived sign, and L diverges as T_c -> T_s.
- The ISS closed form reproduces the sim AND the real 70.3 m^2 assembly to <5%.
- Limit checks: T_s -> 0 recovers (T_h/T_c)^4; equal temperatures give L = 1.
"""

from __future__ import annotations

import math

import pytest

from thermal.thermal import (
    DEFAULT_EMISSIVITY,
    ISS_HEAT_REJECTION_PER_LOOP_KW,
    ISS_RADIATOR_ASSEMBLY_AREA_M2,
    ISS_RADIATOR_TEMP_K,
    RADIATOR_SPECIFIC_MASS_KG_M2,
    STEFAN_BOLTZMANN_W_M2_K4,
    mass_per_kw_kg,
    radiator_area_m2,
)

SIGMA = STEFAN_BOLTZMANN_W_M2_K4


def _mass_per_kw_closed_form(
    temp_k: float, emissivity: float, mu_kg_m2: float, sink_temp_k: float, sides: int
) -> float:
    """Eq. (2): 1000 * mu / (sides * eps * sigma * (T^4 - T_s^4))."""
    flux = sides * emissivity * SIGMA * (temp_k**4 - sink_temp_k**4)
    return 1000.0 * mu_kg_m2 / flux


# ---------- (2) point value: mass_per_kw matches the closed form ----------

@pytest.mark.parametrize("temp_k", [200.0, 300.0, 533.0, 800.0])
@pytest.mark.parametrize("emissivity", [0.5, 0.8, 1.0])
@pytest.mark.parametrize("sides", [1, 2])
def test_mass_per_kw_matches_closed_form(temp_k, emissivity, sides):
    mu = RADIATOR_SPECIFIC_MASS_KG_M2
    got = mass_per_kw_kg(temp_k, emissivity=emissivity, sink_temp_k=0.0, sides=sides,
                         specific_mass_kg_m2=mu)
    expected = _mass_per_kw_closed_form(temp_k, emissivity, mu, 0.0, sides)
    assert got == pytest.approx(expected, rel=1e-12)


# ---------- (4) leverage ratio -> (T_h/T_c)^4 in the deep-space limit ----------

@pytest.mark.parametrize("t_cold,t_hot", [(300.0, 533.0), (250.0, 500.0), (300.0, 600.0)])
def test_leverage_ratio_is_temp_ratio_to_the_fourth(t_cold, t_hot):
    cold = mass_per_kw_kg(t_cold, sink_temp_k=0.0)
    hot = mass_per_kw_kg(t_hot, sink_temp_k=0.0)
    assert cold / hot == pytest.approx((t_hot / t_cold) ** 4, rel=1e-12)


def test_headline_530_over_300_is_about_ten():
    cold = mass_per_kw_kg(300.0)
    hot = mass_per_kw_kg(533.0)
    assert cold / hot == pytest.approx(9.96, rel=1e-2)


# ---------- (3) the cancellation: leverage is invariant to eps, mu, sides, load ----------

def test_leverage_ratio_independent_of_emissivity_areal_mass_sides():
    """The structural result: only the temperatures set the leverage.

    Vary emissivity, areal density, and side count together (as long as both
    radiators share them) and the cold/hot ratio must not move.
    """
    t_cold, t_hot = 300.0, 533.0
    baseline = None
    for eps in (0.4, 0.8, 1.0):
        for mu in (3.0, 7.5, 12.0):
            for sides in (1, 2):
                cold = mass_per_kw_kg(t_cold, emissivity=eps, sides=sides,
                                      specific_mass_kg_m2=mu, sink_temp_k=0.0)
                hot = mass_per_kw_kg(t_hot, emissivity=eps, sides=sides,
                                     specific_mass_kg_m2=mu, sink_temp_k=0.0)
                ratio = cold / hot
                if baseline is None:
                    baseline = ratio
                assert ratio == pytest.approx(baseline, rel=1e-12), (
                    f"leverage ratio moved with eps/mu/sides: {ratio} != {baseline}"
                )
    # And it equals the pure temperature form.
    assert baseline == pytest.approx((t_hot / t_cold) ** 4, rel=1e-12)


def test_leverage_ratio_independent_of_heat_load():
    """mass_per_kw is per-kW, so the leverage cancels the heat load exactly.

    Size both radiators for the same arbitrary load via area; the area ratio is
    the same closed form, load-free.
    """
    t_cold, t_hot = 300.0, 533.0
    for load_w in (1_000.0, 50_000.0, 2_000_000.0):
        a_cold = radiator_area_m2(load_w, t_cold, sink_temp_k=0.0)
        a_hot = radiator_area_m2(load_w, t_hot, sink_temp_k=0.0)
        assert a_cold / a_hot == pytest.approx((t_hot / t_cold) ** 4, rel=1e-12)


# ---------- (5) sink correction: a warm sink widens the hot radiator's lead ----------

def test_warm_sink_increases_the_leverage():
    t_cold, t_hot = 300.0, 533.0
    pure = (t_hot / t_cold) ** 4
    prev = pure
    for t_sink in (0.0, 100.0, 200.0, 290.0):
        cold = mass_per_kw_kg(t_cold, sink_temp_k=t_sink)
        hot = mass_per_kw_kg(t_hot, sink_temp_k=t_sink)
        ratio = cold / hot
        # closed form (3)
        assert ratio == pytest.approx(
            (t_hot**4 - t_sink**4) / (t_cold**4 - t_sink**4), rel=1e-12
        )
        if t_sink > 0.0:
            assert ratio > pure  # (5): warm sink helps the hot radiator more
            assert ratio >= prev - 1e-9  # monotone non-decreasing in the sink
        prev = ratio


def test_leverage_diverges_as_cold_radiator_approaches_its_sink():
    """A radiator just above its sink rejects ~nothing per kg -> mass/kW blows up."""
    t_hot = 533.0
    ratios = []
    for t_cold in (320.0, 305.0, 301.0, 300.05):
        t_sink = 300.0
        cold = mass_per_kw_kg(t_cold, sink_temp_k=t_sink)
        hot = mass_per_kw_kg(t_hot, sink_temp_k=t_sink)
        ratios.append(cold / hot)
    # Strictly increasing and unbounded as t_cold -> t_sink+.
    assert all(b > a for a, b in zip(ratios, ratios[1:]))
    assert ratios[-1] > 1e3


# ---------- limit: equal temperatures give leverage 1 ----------

def test_equal_temperatures_give_unit_leverage():
    for t in (300.0, 533.0):
        assert mass_per_kw_kg(t) / mass_per_kw_kg(t) == pytest.approx(1.0, rel=1e-12)


# ---------- #15 ISS anchor: closed form reproduces sim AND flight hardware ----------

def test_iss_anchor_closed_form_matches_sim_and_flight_hardware():
    load_w = ISS_HEAT_REJECTION_PER_LOOP_KW * 1000.0
    # Closed form A = P / (2 * eps * sigma * T^4), independently computed.
    flux = 2 * 0.8 * SIGMA * ISS_RADIATOR_TEMP_K**4
    area_closed = load_w / flux
    area_sim = radiator_area_m2(load_w, ISS_RADIATOR_TEMP_K, emissivity=0.8)
    assert area_sim == pytest.approx(area_closed, rel=1e-12)
    assert area_closed == pytest.approx(67.5, rel=1e-2)
    # Within <5% of the real 70.3 m^2 assembly - the flight anchor.
    rel_err = abs(area_closed - ISS_RADIATOR_ASSEMBLY_AREA_M2) / ISS_RADIATOR_ASSEMBLY_AREA_M2
    assert rel_err < 0.05


def test_default_emissivity_is_the_flight_value():
    # The ISS anchor and the ~10x leverage both quote eps 0.8 - the module default.
    assert DEFAULT_EMISSIVITY == pytest.approx(0.8)
    assert math.isclose(mass_per_kw_kg(300.0),
                        mass_per_kw_kg(300.0, emissivity=DEFAULT_EMISSIVITY))
