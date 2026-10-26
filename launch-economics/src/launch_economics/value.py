"""The output side of the economic case - and an honesty check on the headlines."""

from __future__ import annotations

# --- Honesty-backbone anchors, used only for the debunk (REFERENCES.md); first is the entire annual global platinum market value, USD (2024). ---
PLATINUM_MARKET_ANNUAL_USD: float = 7.25e9
# Annual world platinum mine production, tonnes (2024-2025 ~170-179 t).
PLATINUM_ANNUAL_PRODUCTION_T: float = 175.0
# The widely-quoted "value" of asteroid 16 Psyche's metal at spot prices, USD.
PSYCHE_QUOTED_VALUE_USD: float = 1.0e19


def output_value_launch_avoided_usd(
    local_mass_produced_kg: float, cost_per_kg_usd: float
) -> float:
    """Value returned as launch cost avoided: mass built in place x $/kg-in-orbit."""
    if local_mass_produced_kg < 0:
        raise ValueError("local_mass_produced_kg must be non-negative")
    if cost_per_kg_usd < 0:
        raise ValueError("cost_per_kg_usd must be non-negative")
    return local_mass_produced_kg * cost_per_kg_usd


def market_absorption_years(
    resource_value_usd: float,
    annual_market_usd: float = PLATINUM_MARKET_ANNUAL_USD,
) -> float:
    """Years to sell a resource at the current market's annual turnover: value / market."""
    if resource_value_usd < 0:
        raise ValueError("resource_value_usd must be non-negative")
    if annual_market_usd <= 0:
        raise ValueError("annual_market_usd must be positive")
    return resource_value_usd / annual_market_usd


def realizable_value_ceiling_usd(
    years: float, annual_market_usd: float = PLATINUM_MARKET_ANNUAL_USD
) -> float:
    """Honest ceiling on realizable commodity value over a horizon: market x years."""
    if years < 0:
        raise ValueError("years must be non-negative")
    if annual_market_usd <= 0:
        raise ValueError("annual_market_usd must be positive")
    return years * annual_market_usd
