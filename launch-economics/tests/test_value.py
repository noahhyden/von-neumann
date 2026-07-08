"""value validation: the launch-cost-avoided output and the headline debunk.

The defensible output is launch-cost-avoided (definitional arithmetic); the platinum-
market anchors exist only to debunk the "$X quintillion asteroid" figures. See
REFERENCES.md.
"""

import pytest

from launch_economics.launch import launch_cost_usd
from launch_economics.value import (
    PLATINUM_MARKET_ANNUAL_USD,
    PSYCHE_QUOTED_VALUE_USD,
    market_absorption_years,
    output_value_launch_avoided_usd,
    realizable_value_ceiling_usd,
)


def test_launch_cost_avoided_is_mass_times_cost():
    # 1000 t built locally at $3000/kg = $3B of launch avoided.
    v = output_value_launch_avoided_usd(1_000_000.0, 3_000.0)
    assert v == pytest.approx(3.0e9)
    # Same arithmetic as launch_cost_usd, opposite meaning (value returned, not paid).
    assert v == pytest.approx(launch_cost_usd(1_000_000.0, 3_000.0))


def test_zero_mass_returns_zero_value():
    assert output_value_launch_avoided_usd(0.0, 3_000.0) == 0.0


def test_psyche_headline_is_arithmetic_fiction():
    # $10 quintillion at a ~$7.25B/yr market would take >1 billion years to sell.
    years = market_absorption_years(PSYCHE_QUOTED_VALUE_USD)
    assert years == pytest.approx(PSYCHE_QUOTED_VALUE_USD / PLATINUM_MARKET_ANNUAL_USD, rel=1e-9)
    assert years > 1.0e9  # longer than the market could ever absorb


def test_realizable_ceiling_is_bounded_by_the_market():
    # Over a century the most a commodity can realize is ~100 years of market turnover,
    # vastly below the quoted Psyche figure - the honest cap.
    ceiling_100yr = realizable_value_ceiling_usd(100.0)
    assert ceiling_100yr == pytest.approx(100.0 * PLATINUM_MARKET_ANNUAL_USD)
    assert ceiling_100yr < PSYCHE_QUOTED_VALUE_USD / 1.0e6  # off by >6 orders of magnitude


def test_more_mass_more_avoided_value_monotonic():
    small = output_value_launch_avoided_usd(1_000.0, 3_000.0)
    big = output_value_launch_avoided_usd(2_000.0, 3_000.0)
    assert big == pytest.approx(2.0 * small)


def test_sourced_anchor_values():
    assert PLATINUM_MARKET_ANNUAL_USD == 7.25e9
    assert PSYCHE_QUOTED_VALUE_USD == 1.0e19


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        output_value_launch_avoided_usd(-1.0, 3_000.0)
    with pytest.raises(ValueError):
        market_absorption_years(1.0e19, annual_market_usd=0.0)
    with pytest.raises(ValueError):
        realizable_value_ceiling_usd(-1.0)
