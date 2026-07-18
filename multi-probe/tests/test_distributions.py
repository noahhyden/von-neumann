from multi_probe.distributions import (
    ARRAY_EFFICIENCY_DIST,
    DEFAULT_FRACTION_MANUFACTURING_DIST,
)
from probe_sim.distributions import SOLAR_CELL_EFFICIENCY_DIST
from vn_core.uq import Fixed


def test_array_efficiency_is_identity_reexport_from_probe_sim():
    assert ARRAY_EFFICIENCY_DIST is SOLAR_CELL_EFFICIENCY_DIST


def test_manufacturing_fraction_is_a_fixed_design_choice():
    assert isinstance(DEFAULT_FRACTION_MANUFACTURING_DIST, Fixed)
    assert DEFAULT_FRACTION_MANUFACTURING_DIST.value == 0.70
