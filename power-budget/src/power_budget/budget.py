"""Splitting a fixed power budget between making things and thinking.

An autonomous self-replicating factory has to divide its (solar-limited) electrical
power between manufacturing/ISRU, onboard computation (the autonomy it needs when
Earth is light-minutes away), and housekeeping (thermal, comms, attitude). This
module is the pure, one-shot accounting of that split, plus the conversion from
compute-watts to compute throughput given a hardware efficiency.

The efficiency (FLOPS per watt) is a per-scenario input, not a constant — a scenario
that fixes one must cite the specific hardware (see REFERENCES.md). Deterministic,
plain data, zero pimas imports (CLAUDE.md §7).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class PowerBudget(BaseModel):
    """A fixed electrical power budget (W) divided into fractional allocations.

    Fractions are of the total; they must not sum to more than 1. Any remainder is
    reported as ``unallocated_w`` (spare / margin).
    """

    total_w: float = Field(gt=0, description="total available electrical power, W")
    fraction_manufacturing: float = Field(ge=0, le=1, default=0.0)
    fraction_compute: float = Field(ge=0, le=1, default=0.0)
    fraction_housekeeping: float = Field(ge=0, le=1, default=0.0)

    @model_validator(mode="after")
    def _fractions_within_one(self) -> "PowerBudget":
        allocated = (
            self.fraction_manufacturing
            + self.fraction_compute
            + self.fraction_housekeeping
        )
        if allocated > 1.0 + 1e-9:
            raise ValueError(
                f"power fractions sum to {allocated:.4f} > 1 (over-allocated budget)"
            )
        return self

    @property
    def manufacturing_w(self) -> float:
        return self.total_w * self.fraction_manufacturing

    @property
    def compute_w(self) -> float:
        return self.total_w * self.fraction_compute

    @property
    def housekeeping_w(self) -> float:
        return self.total_w * self.fraction_housekeeping

    @property
    def unallocated_w(self) -> float:
        allocated = (
            self.fraction_manufacturing
            + self.fraction_compute
            + self.fraction_housekeeping
        )
        return self.total_w * (1.0 - allocated)


def compute_capacity_flops(power_w: float, efficiency_flops_per_w: float) -> float:
    """Compute throughput (FLOPS) a given power (W) buys at a hardware efficiency."""
    if power_w < 0:
        raise ValueError("power_w must be non-negative")
    if efficiency_flops_per_w <= 0:
        raise ValueError("efficiency_flops_per_w must be positive")
    return power_w * efficiency_flops_per_w
