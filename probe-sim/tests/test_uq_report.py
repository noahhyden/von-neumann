"""one_line_finding: assert the formatting contract, not execution.

The reporter is pure formatting glue - a caller uses it to write "X, +/- Y,
driven by Z" once and get consistent output everywhere. Tests pin the two
regimes: a clear single driver, and a "shared between two" case where no one
input dominates.
"""

import math

import pytest

from vn_core.uq.distributions import Fixed, Normal, Uniform
from vn_core.uq.report import one_line_finding
from vn_core.uq.sample import monte_carlo
from vn_core.uq.sobol import sobol_total_order


def d_max(sample):
    return math.sqrt(
        sample["S0"] * sample["area_m2"] * sample["efficiency"]
        / sample["required_power_w"]
    )


HEADLINE_INPUTS = {
    "S0": Normal(1360.8, 0.5),
    "efficiency": Uniform(0.28, 0.32),
    "area_m2": Fixed(200.0),
    "required_power_w": Fixed(208_000.0),
}


def test_one_line_names_the_dominant_driver():
    mc = monte_carlo(HEADLINE_INPUTS, d_max, n=2000, seed=101)
    sobol = sobol_total_order(HEADLINE_INPUTS, d_max, n=500, seed=101)
    line = one_line_finding("max_reach", "AU", mc, sobol)
    assert "max_reach = " in line
    assert "AU" in line
    assert "90% CI" in line
    assert "driven by efficiency" in line
    assert "S_T=" in line
    # Values should read cleanly, not as scientific-notation gibberish for
    # this scenario (mean ~0.63, std ~0.012, so both fit 4-sig-fig format).
    assert "0.6" in line


def test_one_line_shared_when_no_single_driver_dominates():
    # Two inputs with symmetric additive contributions: neither dominates.
    inputs = {
        "a": Uniform(low=0.0, high=1.0),
        "b": Uniform(low=0.0, high=1.0),
    }
    finding = lambda s: s["a"] + s["b"]  # noqa: E731
    mc = monte_carlo(inputs, finding, n=2000, seed=103)
    sobol = sobol_total_order(inputs, finding, n=1000, seed=103)
    line = one_line_finding("sum_ab", "unit", mc, sobol)
    assert "shared between" in line
    assert "a" in line and "b" in line


def test_one_line_configurable_ci_percentage():
    mc = monte_carlo(HEADLINE_INPUTS, d_max, n=1000, seed=105)
    sobol = sobol_total_order(HEADLINE_INPUTS, d_max, n=300, seed=105)
    line = one_line_finding("reach", "AU", mc, sobol, ci_pct=90)
    assert "90% CI" in line
    other = one_line_finding("reach", "AU", mc, sobol, ci_pct=95)
    assert "95% CI" in other
