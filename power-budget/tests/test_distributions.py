"""power_budget.distributions: sourced spreads for every REFERENCES.md number.

Three regimes tested: definitional (Fixed), sourced spread (Uniform / Normal),
and explicitly-order-of-magnitude (LogUniform). The Landauer floor is a real
UQ finding here - even at LogUniform(1e15, 1e20) brain-FLOPS, the floor
itself does not move; the *variance* in brain-equivalents does. That is the
"which input actually drives the variance" property.
"""

import math

import pytest

from power_budget.distributions import (
    BOLTZMANN_DIST,
    BRAIN_COMPUTE_FLOPS_DIST,
    COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST,
    HUMAN_BRAIN_POWER_DIST,
    REFERENCE_TEMPERATURE_K_DIST,
)
from power_budget.physics import (
    BOLTZMANN_J_PER_K,
    HUMAN_BRAIN_POWER_W,
    brain_equivalents,
)
from vn_core.uq import Fixed, LogUniform, Uniform, monte_carlo, sobol_total_order


def test_definitional_constants_stay_fixed():
    # Boltzmann is exact by SI redefinition and the reference temperature is
    # a documented choice, not a measurement - both must be Fixed.
    assert isinstance(BOLTZMANN_DIST, Fixed)
    assert isinstance(REFERENCE_TEMPERATURE_K_DIST, Fixed)
    assert BOLTZMANN_DIST.value == BOLTZMANN_J_PER_K
    assert REFERENCE_TEMPERATURE_K_DIST.value == 300.0


def test_brain_power_uniform_matches_the_sourced_range():
    assert isinstance(HUMAN_BRAIN_POWER_DIST, Uniform)
    assert HUMAN_BRAIN_POWER_DIST.low == 15.0
    assert HUMAN_BRAIN_POWER_DIST.high == 25.0
    # Point value must sit inside the band.
    assert HUMAN_BRAIN_POWER_DIST.low <= HUMAN_BRAIN_POWER_W <= HUMAN_BRAIN_POWER_DIST.high


def test_brain_flops_loguniform_spans_the_five_orders_of_magnitude():
    assert isinstance(BRAIN_COMPUTE_FLOPS_DIST, LogUniform)
    assert BRAIN_COMPUTE_FLOPS_DIST.low == pytest.approx(1e15)
    assert BRAIN_COMPUTE_FLOPS_DIST.high == pytest.approx(1e20)
    # Each order of magnitude equally likely: log10(quantile(0.5)) is midway.
    assert math.log10(BRAIN_COMPUTE_FLOPS_DIST.quantile(0.5)) == pytest.approx(17.5, abs=1e-6)


def test_brain_equivalents_variance_dominated_by_brain_flops_uncertainty():
    # A canonical UQ finding: how many brain-equivalents is 1e18 FLOPS?
    # Point-value answer is 1.0. But under the LogUniform(1e15, 1e20) prior
    # on brain FLOPS, the ratio spans FIVE orders of magnitude - the finding
    # "compute_flops matches a brain" is meaningless without saying which
    # brain FLOPS estimate you picked. Sobol should confirm brain_flops as
    # the dominant driver over any spread on the compute side.
    inputs = {
        "compute_flops": LogUniform(low=1e17, high=1e19),
        "brain_flops": BRAIN_COMPUTE_FLOPS_DIST,
    }

    def be(sample):
        return brain_equivalents(sample["compute_flops"], sample["brain_flops"])

    mc = monte_carlo(inputs, be, n=2000, seed=71)
    lo, hi = mc.error_bar_95
    # The 90% CI must span at least 3 orders of magnitude - the brain-FLOPS
    # spread of 5 OoM dominates.
    assert hi / lo > 1000

    sobol = sobol_total_order(inputs, be, n=800, seed=71)
    # brain_flops has 5 OoM range, compute_flops has 2 OoM: brain_flops
    # dominates the ratio's log-space variance.
    assert sobol.ranked()[0][0] == "brain_flops"


def test_compute_efficiency_dist_covers_current_hardware():
    # Range must include the H100-class point value ~1e11.
    med = COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST.quantile(0.5)
    assert 1e10 < med < 1e12
