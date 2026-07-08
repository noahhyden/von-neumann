"""The radiation environment - one shared primitive, consumed by shielding and reliability.

`shielding` (attenuation -> mass) and `reliability` (dose -> degradation/mortality) both
need the same GCR / solar-particle / Jovian dose numbers. Maintaining them in two places
invites divergence, so they live here once and both modules consume them (the proposal's
cross-cutting note). This file has no logic beyond unit-safe accessors - it is a sourced
reference table.

Two dose bases, deliberately kept distinct (CLAUDE.md 1):

- **TID for electronics** in krad(Si) (or rad) - total ionising dose that degrades chips.
- **Dose-equivalent for biology / mission risk** in mSv - GCR dose weighted by radiation
  quality. These are different quantities on different scales; never add one to the other.

Every number is in REFERENCES.md.
"""

from __future__ import annotations

import math

# --- Deep-space GCR dose-equivalent (biological basis, mSv). ---
# Mars Science Laboratory RAD measured ~1.8 mSv/day during cruise (Zeitlin et al. 2013).
GCR_DEEP_SPACE_DOSE_MSV_PER_DAY: float = 1.8

# Aluminium areal density (g/cm^2) at which GCR dose-EQUIVALENT is minimised. Beyond it,
# neutron/secondary build-up makes thicker shielding WORSE, not better (HZETRN studies).
GCR_DOSE_MIN_AREAL_DENSITY_G_CM2: float = 20.0

# --- Jovian TID environment (electronics basis, rad(Si)). ---
# Juno's anticipated total mission dose behind minimal shielding: ~20 Mrad.
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
    """[ESTIMATE] effective attenuation length (g/cm^2) fit to the Juno anchor.

    Treating TID attenuation as exp(-sigma/lambda), Juno's 4.51 g/cm^2 giving an 800x
    reduction fixes lambda = 4.51 / ln(800) = 0.675 g/cm^2. A single-point exponential
    fit to the Jovian electron spectrum - tagged [ESTIMATE], not a measured constant.
    """
    return juno_ti_wall_areal_density_g_cm2() / math.log(JUNO_VAULT_ATTENUATION_FACTOR)
