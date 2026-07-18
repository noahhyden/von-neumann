"""shielding.distributions: sourced spreads for every REFERENCES.md number."""

import pytest

from shielding.distributions import (
    ALUMINIUM_DENSITY_DIST,
    GCR_DEEP_SPACE_DOSE_DIST,
    GCR_DOSE_MIN_AREAL_DENSITY_DIST,
    JUNO_VAULT_ATTENUATION_DIST,
    JUNO_VAULT_MASS_DIST,
    LUNAR_REGOLITH_DENSITY_DIST,
    TITANIUM_DENSITY_DIST,
)
from shielding.radenv import (
    ALUMINIUM_DENSITY_G_CM3,
    GCR_DEEP_SPACE_DOSE_MSV_PER_DAY,
    JUNO_VAULT_MASS_KG,
    LUNAR_REGOLITH_DENSITY_G_CM3,
    TITANIUM_DENSITY_G_CM3,
)
from vn_core.uq import Fixed, Uniform


def test_metal_densities_are_fixed():
    assert isinstance(TITANIUM_DENSITY_DIST, Fixed)
    assert isinstance(ALUMINIUM_DENSITY_DIST, Fixed)
    assert TITANIUM_DENSITY_DIST.value == TITANIUM_DENSITY_G_CM3
    assert ALUMINIUM_DENSITY_DIST.value == ALUMINIUM_DENSITY_G_CM3


def test_regolith_density_is_uniform_due_to_compaction():
    assert isinstance(LUNAR_REGOLITH_DENSITY_DIST, Uniform)
    assert LUNAR_REGOLITH_DENSITY_DIST.low <= LUNAR_REGOLITH_DENSITY_G_CM3 <= LUNAR_REGOLITH_DENSITY_DIST.high


def test_flight_measurements_are_fixed():
    assert isinstance(JUNO_VAULT_MASS_DIST, Fixed)
    assert JUNO_VAULT_MASS_DIST.value == JUNO_VAULT_MASS_KG


def test_gcr_dose_covers_msl_rad_point_value():
    assert GCR_DEEP_SPACE_DOSE_DIST.low <= GCR_DEEP_SPACE_DOSE_MSV_PER_DAY <= GCR_DEEP_SPACE_DOSE_DIST.high


def test_juno_attenuation_uncertainty_matches_the_geometry_spread():
    assert JUNO_VAULT_ATTENUATION_DIST.low == 500.0
    assert JUNO_VAULT_ATTENUATION_DIST.high == 1000.0


def test_gcr_dose_min_density_covers_hzetrn_band():
    assert GCR_DOSE_MIN_AREAL_DENSITY_DIST.low == 15.0
    assert GCR_DOSE_MIN_AREAL_DENSITY_DIST.high == 25.0
