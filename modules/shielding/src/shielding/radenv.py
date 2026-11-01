"""The radiation environment - one shared primitive, consumed by shielding and reliability."""

from __future__ import annotations

import math

# --- Deep-space GCR dose-equivalent (biological basis, mSv); Mars Science Laboratory RAD measured ~1.8 mSv/day during cruise (Zeitlin et al. 2013). ---
GCR_DEEP_SPACE_DOSE_MSV_PER_DAY: float = 1.8

# Aluminium areal density (g/cm^2) at which GCR dose-EQUIVALENT is minimised; beyond it neutron/secondary build-up makes thicker shielding WORSE (HZETRN studies).
GCR_DOSE_MIN_AREAL_DENSITY_G_CM2: float = 20.0

# --- Jovian TID environment (electronics basis, rad(Si)); Juno anticipated total mission dose behind minimal shielding is ~20 Mrad. ---
JUNO_ANTICIPATED_TID_RAD: float = 2.0e7
# Juno radiation vault: 1 cm titanium walls -> ~800x dose reduction inside.
JUNO_VAULT_ATTENUATION_FACTOR: float = 800.0

# --- Material areal densities (g/cm^2 per cm of thickness = density in g/cm^3). ---
TITANIUM_DENSITY_G_CM3: float = 4.51
ALUMINIUM_DENSITY_G_CM3: float = 2.70
# Bulk lunar regolith (loosely packed ~1.5; compacted higher). Representative 1.6.
LUNAR_REGOLITH_DENSITY_G_CM3: float = 1.6

# --- Flight vault mass anchors (kg). ---
JUNO_VAULT_MASS_KG: float = 200.0
EUROPA_CLIPPER_VAULT_MASS_KG: float = 150.0


def juno_ti_wall_areal_density_g_cm2() -> float:
    """Juno's 1 cm titanium wall areal density: 1 cm x 4.51 g/cm^3 = 4.51 g/cm^2."""
    return 1.0 * TITANIUM_DENSITY_G_CM3


def jovian_tid_attenuation_length_g_cm2() -> float:
    """[ESTIMATE] effective attenuation length (g/cm^2) fit to the Juno anchor."""
    return juno_ti_wall_areal_density_g_cm2() / math.log(JUNO_VAULT_ATTENUATION_FACTOR)
