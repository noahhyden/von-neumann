"""launch_economics.distributions: sourced spreads for every REFERENCES.md number."""

import math

import pytest

from launch_economics.distributions import (
    DELTA_V_LEO_TO_ESCAPE_DIST,
    DELTA_V_LEO_TO_MARS_DIST,
    DELTA_V_LEO_TO_TLI_DIST,
    DELTA_V_SURFACE_TO_LEO_DIST,
    G0_DIST,
    ISP_ELECTRIC_DIST,
    ISP_LOX_LH2_DIST,
    ISP_LOX_RP1_DIST,
    LAUNCH_COST_FALCON_9_DIST,
    LAUNCH_COST_FALCON_HEAVY_DIST,
    LAUNCH_COST_STARSHIP_DIST,
)
from vn_core.uq import Fixed, LogUniform, Uniform, monte_carlo, sobol_total_order


def test_g0_is_definitional():
    assert isinstance(G0_DIST, Fixed)
    assert G0_DIST.value == 9.80665


def test_launch_cost_bands_ordered_by_generation():
    # F9 > FH > Starship at the low ends: the module's own numbers tell the
    # cost-reduction story.
    assert LAUNCH_COST_FALCON_9_DIST.low > LAUNCH_COST_FALCON_HEAVY_DIST.low
    assert LAUNCH_COST_FALCON_HEAVY_DIST.low > LAUNCH_COST_STARSHIP_DIST.high
    # Starship carried as LogUniform because the range spans an order of magnitude.
    assert isinstance(LAUNCH_COST_STARSHIP_DIST, LogUniform)


def test_delta_v_bands_are_all_within_50_percent_of_their_centre():
    # A sanity check that the delta-V bands are honest ranges, not stub
    # zero-spread Fixed values passed through Uniform.
    for name, dist in [
        ("surf->LEO", DELTA_V_SURFACE_TO_LEO_DIST),
        ("LEO->TLI", DELTA_V_LEO_TO_TLI_DIST),
        ("LEO->Mars", DELTA_V_LEO_TO_MARS_DIST),
        ("LEO->escape", DELTA_V_LEO_TO_ESCAPE_DIST),
    ]:
        assert dist.high > dist.low, f"{name} degenerate"
        mid = 0.5 * (dist.low + dist.high)
        assert (dist.high - dist.low) / mid < 0.5


def test_electric_isp_covers_the_1500_to_4000_band():
    assert ISP_ELECTRIC_DIST.low == 1500.0
    assert ISP_ELECTRIC_DIST.high == 4000.0
    assert isinstance(ISP_ELECTRIC_DIST, LogUniform)


def test_launch_cost_uq_leverage_finding():
    # Load-bearing UQ finding for launch-economics: what does 1 tonne of local
    # mass save in launch cost under Starship pricing? Point value at the
    # $500/kg midpoint gives $5e5; but LogUniform(100, 1000) blows the CI up.
    def savings_per_tonne(sample):
        return 1000.0 * sample["cost_per_kg"]

    r = monte_carlo(
        {"cost_per_kg": LAUNCH_COST_STARSHIP_DIST},
        savings_per_tonne,
        n=3000,
        seed=101,
    )
    # 90% CI should span an order of magnitude for the LogUniform band.
    lo, hi = r.error_bar_95
    assert hi / lo > 5.0, "Starship LogUniform must produce a wide CI"


def test_rocket_equation_uq_finds_isp_dominant():
    # Tsiolkovsky rocket equation: m0/mf = exp(dv / (Isp * g0)). Under UQ
    # over both, Isp should dominate because it enters the exponent's
    # denominator - a proportional change there hits harder than the same
    # proportional change in the numerator dv.
    inputs = {
        "dv": DELTA_V_SURFACE_TO_LEO_DIST,
        "isp": ISP_LOX_RP1_DIST,
    }

    def mass_ratio(sample):
        return math.exp(sample["dv"] / (sample["isp"] * 9.80665))

    s = sobol_total_order(inputs, mass_ratio, n=1500, seed=103)
    # Isp has ~20% relative spread, dv has ~7%; Isp in the exponent's
    # denominator + a wider relative band = dominant driver.
    assert s.ranked()[0][0] == "isp"
