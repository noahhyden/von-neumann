"""mission.distributions: re-exports of sibling distributions, plus design choices held Fixed at the scenario level."""

import pytest

from launch_economics.distributions import (
    DELTA_V_SURFACE_TO_LEO_DIST,
    ISP_LOX_RP1_DIST,
    LAUNCH_COST_FALCON_9_DIST,
)
from mission.distributions import (
    ARRAY_EFFICIENCY_DIST,
    COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST_MISSION,
    COST_PER_KG_USD_DIST,
    DELTA_V_M_S_DIST,
    FRACTION_COMPUTE_DIST,
    FRACTION_HOUSEKEEPING_DIST,
    FRACTION_MANUFACTURING_DIST,
    SPECIFIC_IMPULSE_S_DIST,
)
from power_budget.distributions import COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST
from probe_sim.distributions import SOLAR_CELL_EFFICIENCY_DIST


def test_sibling_reexports_are_identity_not_copies():
    # THE regression-catcher: mission's distribution objects must BE the sibling objects, not deep-copies, since a copy would silently freeze mission at a stale distribution.
    assert ARRAY_EFFICIENCY_DIST is SOLAR_CELL_EFFICIENCY_DIST
    assert DELTA_V_M_S_DIST is DELTA_V_SURFACE_TO_LEO_DIST
    assert SPECIFIC_IMPULSE_S_DIST is ISP_LOX_RP1_DIST
    assert COST_PER_KG_USD_DIST is LAUNCH_COST_FALCON_9_DIST
    assert COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST_MISSION is COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST


def test_allocation_fractions_sum_to_one():
    total = (
        FRACTION_MANUFACTURING_DIST.value
        + FRACTION_COMPUTE_DIST.value
        + FRACTION_HOUSEKEEPING_DIST.value
    )
    assert total == pytest.approx(1.0, abs=1e-9)
