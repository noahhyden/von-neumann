"""shielding - radiation shielding mass, and the GCR trap.

Turns a radiation dose budget into shield mass from published areal-density attenuation
(no particle transport). Two opposite regimes: TID electronics shielding is monotonic
(shield until the dose budget is met), but GCR dose-equivalent has a MINIMUM near
~20 g/cm^2 aluminium and gets worse beyond it (secondaries) - so the module refuses to
over-shield. Shielding is local-regolith mass that RAISES closure (opposite of imported
vitamins), which reframes the trade as cheap COTS parts behind thick regolith vs imported
rad-hardness. It exposes `radenv`, the shared radiation-environment primitive that
`reliability` also consumes.

Pure, deterministic, no pimas, no RNG (CLAUDE.md 7). Every number traces to a source; see
REFERENCES.md.
"""

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
