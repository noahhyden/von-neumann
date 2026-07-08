"""The output side of the economic case - and an honesty check on the headlines.

The rest of `launch-economics` prices what a self-replicating factory *avoids paying*
(launch cost). This adds the value it *returns*, but only the one output that survives
the iron rule (CLAUDE.md 1):

- **Launch-cost-avoided value.** Every kilogram a factory builds in place is a kilogram
  nobody had to launch, so its value is `mass x $/kg-in-orbit` - definitional arithmetic
  over the same specific launch cost the rest of the module already sources. This
  completes `mission`'s payoff with zero new unsourced numbers.

Realized commodity value, settlement value, and $/bit for returned data are all
`[ESTIMATE]`/`[GAP]` and are deliberately NOT modelled as returns.

- **The headline debunk (honesty backbone).** "Asteroid X is worth $Y quintillion" figures
  multiply a spot price by a raw tonnage - but selling that tonnage floods the market and
  collapses the price. The entire annual global platinum market is ~$7.25 billion; 16
  Psyche is quoted at ~$10 quintillion of metal. Valued honestly against a market that
  can absorb only billions of dollars a year, those figures are arithmetic fictions. This
  is an illustration whose point is to debunk, not a return this module claims.

Deterministic, plain data, zero pimas imports (CLAUDE.md 7). Units: kg, USD, tonnes, yr.
See REFERENCES.md.
"""

from __future__ import annotations

# --- Honesty-backbone anchors (sourced; used only for the debunk). See REFERENCES.md. ---
# Entire annual global platinum market value, USD (2024).
PLATINUM_MARKET_ANNUAL_USD: float = 7.25e9
# Annual world platinum mine production, tonnes (2024-2025 ~170-179 t).
PLATINUM_ANNUAL_PRODUCTION_T: float = 175.0
# The widely-quoted "value" of asteroid 16 Psyche's metal at spot prices, USD.
PSYCHE_QUOTED_VALUE_USD: float = 1.0e19


def output_value_launch_avoided_usd(
    local_mass_produced_kg: float, cost_per_kg_usd: float
) -> float:
    """Value returned as launch cost avoided: mass built in place x $/kg-in-orbit.

    The defensible output side of the economic case: a kilogram made locally is a
    kilogram nobody paid to launch. Definitional arithmetic over the module's own
    sourced specific launch cost - no new unsourced number.
    """
    if local_mass_produced_kg < 0:
        raise ValueError("local_mass_produced_kg must be non-negative")
    if cost_per_kg_usd < 0:
        raise ValueError("cost_per_kg_usd must be non-negative")
    return local_mass_produced_kg * cost_per_kg_usd


def market_absorption_years(
    resource_value_usd: float,
    annual_market_usd: float = PLATINUM_MARKET_ANNUAL_USD,
) -> float:
    """Years to sell a resource at the current market's annual turnover: value / market.

    The debunk metric. A quoted asteroid "value" that would take millions or billions of
    years to actually sell at current market volume is not a realizable value - it is a
    spot price multiplied by a tonnage the market cannot absorb.
    """
    if resource_value_usd < 0:
        raise ValueError("resource_value_usd must be non-negative")
    if annual_market_usd <= 0:
        raise ValueError("annual_market_usd must be positive")
    return resource_value_usd / annual_market_usd


def realizable_value_ceiling_usd(
    years: float, annual_market_usd: float = PLATINUM_MARKET_ANNUAL_USD
) -> float:
    """Honest ceiling on realizable commodity value over a horizon: market x years.

    You cannot sell faster than the market absorbs, so the most a resource can realize in
    `years` is the market's turnover over that horizon - regardless of how much metal the
    body physically contains.
    """
    if years < 0:
        raise ValueError("years must be non-negative")
    if annual_market_usd <= 0:
        raise ValueError("annual_market_usd must be positive")
    return years * annual_market_usd
