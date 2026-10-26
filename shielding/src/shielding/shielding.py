"""Radiation shielding mass, and the two ways it behaves."""

from __future__ import annotations

import math

from shielding.radenv import (
    GCR_DOSE_MIN_AREAL_DENSITY_G_CM2,
    LUNAR_REGOLITH_DENSITY_G_CM3,
    jovian_tid_attenuation_length_g_cm2,
)

# 1 g/cm^2 spread over 1 m^2 (= 10^4 cm^2) is 10^4 g = 10 kg.
KG_PER_G_CM2_PER_M2: float = 10.0


def areal_density_from_thickness(
    thickness_cm: float, material_density_g_cm3: float
) -> float:
    """Areal density (g/cm^2) of a slab: thickness (cm) x density (g/cm^3)."""
    if thickness_cm < 0:
        raise ValueError("thickness_cm must be non-negative")
    if material_density_g_cm3 <= 0:
        raise ValueError("material_density_g_cm3 must be positive")
    return thickness_cm * material_density_g_cm3


def shield_mass_kg(areal_density_g_cm2: float, area_m2: float) -> float:
    """Shield mass (kg) = areal density (g/cm^2) x area (m^2) x 10."""
    if areal_density_g_cm2 < 0:
        raise ValueError("areal_density_g_cm2 must be non-negative")
    if area_m2 < 0:
        raise ValueError("area_m2 must be non-negative")
    return areal_density_g_cm2 * area_m2 * KG_PER_G_CM2_PER_M2


def tid_attenuation_factor(
    areal_density_g_cm2: float,
    attenuation_length_g_cm2: float | None = None,
) -> float:
    """TID dose-reduction factor for electronics: exp(-sigma / lambda) (monotonic)."""
    if areal_density_g_cm2 < 0:
        raise ValueError("areal_density_g_cm2 must be non-negative")
    lam = attenuation_length_g_cm2 or jovian_tid_attenuation_length_g_cm2()
    if lam <= 0:
        raise ValueError("attenuation_length_g_cm2 must be positive")
    return math.exp(-areal_density_g_cm2 / lam)


def areal_density_for_tid_budget(
    external_dose_rad: float,
    dose_budget_rad: float,
    attenuation_length_g_cm2: float | None = None,
) -> float:
    """Areal density (g/cm^2) needed to bring an external TID down to a dose budget."""
    if external_dose_rad <= 0 or dose_budget_rad <= 0:
        raise ValueError("doses must be positive")
    if dose_budget_rad >= external_dose_rad:
        return 0.0
    lam = attenuation_length_g_cm2 or jovian_tid_attenuation_length_g_cm2()
    return lam * math.log(external_dose_rad / dose_budget_rad)


def gcr_shielding_is_counterproductive(areal_density_g_cm2: float) -> bool:
    """True if this GCR shield is past the dose-equivalent minimum (thicker = worse)."""
    return areal_density_g_cm2 > GCR_DOSE_MIN_AREAL_DENSITY_G_CM2


def recommend_gcr_areal_density(desired_g_cm2: float) -> float:
    """GCR shield areal density, capped at the dose-equivalent minimum."""
    if desired_g_cm2 < 0:
        raise ValueError("desired_g_cm2 must be non-negative")
    return min(desired_g_cm2, GCR_DOSE_MIN_AREAL_DENSITY_G_CM2)


def regolith_thickness_for_areal_density_cm(
    areal_density_g_cm2: float,
    regolith_density_g_cm3: float = LUNAR_REGOLITH_DENSITY_G_CM3,
) -> float:
    """[ESTIMATE] local-regolith thickness (cm) matching a metal shield's areal density."""
    if areal_density_g_cm2 < 0:
        raise ValueError("areal_density_g_cm2 must be non-negative")
    if regolith_density_g_cm3 <= 0:
        raise ValueError("regolith_density_g_cm3 must be positive")
    return areal_density_g_cm2 / regolith_density_g_cm3


def closure_contribution_kg(shield_mass_kg: float, locally_producible: bool) -> float:
    """Shield mass that counts toward closure: the whole mass if made locally, else 0."""
    if shield_mass_kg < 0:
        raise ValueError("shield_mass_kg must be non-negative")
    return shield_mass_kg if locally_producible else 0.0
