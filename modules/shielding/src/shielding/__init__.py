"""shielding - radiation shielding mass, and the GCR trap."""

from shielding.radenv import (
    ALUMINIUM_DENSITY_G_CM3,
    EUROPA_CLIPPER_VAULT_MASS_KG,
    GCR_DEEP_SPACE_DOSE_MSV_PER_DAY,
    GCR_DOSE_MIN_AREAL_DENSITY_G_CM2,
    JUNO_ANTICIPATED_TID_RAD,
    JUNO_VAULT_ATTENUATION_FACTOR,
    JUNO_VAULT_MASS_KG,
    LUNAR_REGOLITH_DENSITY_G_CM3,
    TITANIUM_DENSITY_G_CM3,
    jovian_tid_attenuation_length_g_cm2,
    juno_ti_wall_areal_density_g_cm2,
)
from shielding.shielding import (
    KG_PER_G_CM2_PER_M2,
    areal_density_for_tid_budget,
    areal_density_from_thickness,
    closure_contribution_kg,
    gcr_shielding_is_counterproductive,
    recommend_gcr_areal_density,
    regolith_thickness_for_areal_density_cm,
    shield_mass_kg,
    tid_attenuation_factor,
)

__all__ = [
    # radenv (shared primitive)
    "ALUMINIUM_DENSITY_G_CM3",
    "EUROPA_CLIPPER_VAULT_MASS_KG",
    "GCR_DEEP_SPACE_DOSE_MSV_PER_DAY",
    "GCR_DOSE_MIN_AREAL_DENSITY_G_CM2",
    "JUNO_ANTICIPATED_TID_RAD",
    "JUNO_VAULT_ATTENUATION_FACTOR",
    "JUNO_VAULT_MASS_KG",
    "LUNAR_REGOLITH_DENSITY_G_CM3",
    "TITANIUM_DENSITY_G_CM3",
    "jovian_tid_attenuation_length_g_cm2",
    "juno_ti_wall_areal_density_g_cm2",
    # shielding
    "KG_PER_G_CM2_PER_M2",
    "areal_density_for_tid_budget",
    "areal_density_from_thickness",
    "closure_contribution_kg",
    "gcr_shielding_is_counterproductive",
    "recommend_gcr_areal_density",
    "regolith_thickness_for_areal_density_cm",
    "shield_mass_kg",
    "tid_attenuation_factor",
]
