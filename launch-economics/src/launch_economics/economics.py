"""The self-replication launch payoff: leverage from not launching the mass.

The whole economic case for a von Neumann factory is that you launch a small *seed*
and let it build the rest from local material, instead of launching the finished
installation. This compares the two:

- **direct**: launch the entire target installed mass.
- **replication**: launch only the seed plus the "vitamins" (parts that can't be made
  locally) delivered over the campaign.

The ratio of those masses is the **launch-mass leverage** — how many kilograms of
installed capability each launched kilogram ultimately yields. It ties straight to
`closure-sim`: lower mass closure means more vitamins, means less leverage.

Deterministic, plain data, zero pimas imports (CLAUDE.md §7). Units: kg, USD.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReplicationLaunchComparison(BaseModel):
    """Launch cost of replicating in place vs. launching the finished mass."""

    target_installed_mass_kg: float = Field(
        gt=0, description="installed factory mass ultimately wanted at the destination"
    )
    seed_mass_kg: float = Field(gt=0, description="mass of the landed self-replicating seed")
    vitamin_mass_total_kg: float = Field(
        ge=0, default=0.0, description="total imported (non-replicable) mass over the campaign"
    )
    cost_per_kg_usd: float = Field(gt=0, description="specific launch cost, USD/kg")

    @property
    def launched_mass_kg(self) -> float:
        """Mass actually launched under the replication approach (seed + vitamins)."""
        return self.seed_mass_kg + self.vitamin_mass_total_kg

    @property
    def direct_launch_cost_usd(self) -> float:
        return self.target_installed_mass_kg * self.cost_per_kg_usd

    @property
    def replication_launch_cost_usd(self) -> float:
        return self.launched_mass_kg * self.cost_per_kg_usd

    @property
    def mass_leverage(self) -> float:
        """Installed kg per launched kg — the payoff multiplier of replicating in place."""
        return self.target_installed_mass_kg / self.launched_mass_kg

    @property
    def cost_ratio(self) -> float:
        """Replication cost as a fraction of launch-it-all cost (lower is better)."""
        return self.replication_launch_cost_usd / self.direct_launch_cost_usd

    @property
    def cost_savings_usd(self) -> float:
        return self.direct_launch_cost_usd - self.replication_launch_cost_usd
