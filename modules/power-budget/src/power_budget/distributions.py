"""Distributional companions to power-budget's sourced numbers."""

from __future__ import annotations

from vn_core.uq import Distribution, Fixed, LogUniform, Uniform

from power_budget.physics import (
    BOLTZMANN_J_PER_K,
    BRAIN_COMPUTE_FLOPS_ESTIMATE,
    HUMAN_BRAIN_POWER_W,
)

# Definitional / exact.
BOLTZMANN_DIST: Distribution = Fixed(BOLTZMANN_J_PER_K)
REFERENCE_TEMPERATURE_K_DIST: Distribution = Fixed(300.0)

# Resting human brain power, Raichle & Gusnard 2002 (~20 W); sourced spread is task-dependent brain metabolic power of ~15-25 W across the literature.
HUMAN_BRAIN_POWER_DIST: Distribution = Uniform(low=15.0, high=25.0)

# Brain FLOPS-equivalent: REFERENCES.md flags "estimates span 1e15 to 1e20, uncertainty ~+/- 2 orders of magnitude", so LogUniform over that band reads the source directly.
BRAIN_COMPUTE_FLOPS_DIST: Distribution = LogUniform(low=1e15, high=1e20)

# Present-day accelerator compute efficiency (FLOPS/W): H100-class sits near 1e11 and the Koomey trend is ~2x every 1.6 years, so LogUniform spans two orders of magnitude (narrow it if a device is pinned).
COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST: Distribution = LogUniform(low=1e10, high=1e12)


__all__ = [
    "BOLTZMANN_DIST",
    "REFERENCE_TEMPERATURE_K_DIST",
    "HUMAN_BRAIN_POWER_DIST",
    "BRAIN_COMPUTE_FLOPS_DIST",
    "COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST",
]
