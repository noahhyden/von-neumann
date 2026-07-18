"""Distributional companions to power-budget's sourced numbers.

Issue #35 (UQ) applied to power-budget. The module's constants split cleanly:

- **Definitional / exact.** `BOLTZMANN_J_PER_K` is exact by SI redefinition;
  reference `TEMPERATURE_K = 300.0` is a documented choice. Fixed.
- **Sourced with a real spread.** `HUMAN_BRAIN_POWER_W = 20.0` W is Raichle
  & Gusnard's resting figure; brain power under load easily varies ~15-25 W
  and REFERENCES.md notes the range. `Uniform(15, 25)` here is the honest
  read of that spread.
- **Explicitly ~2 orders of magnitude uncertain.** REFERENCES.md flags
  `BRAIN_COMPUTE_FLOPS_ESTIMATE = 1e18` as "estimates span 1e15 to 1e20;
  uncertainty ~+/- 2 orders". `LogUniform(1e15, 1e20)` is the direct
  literal-of-the-source distribution - not one order of magnitude equally
  likely, but ALL FIVE, matching the phrasing.
- **Scenario input, per-part.** Compute efficiency (FLOPS/W). Modern
  accelerators sit ~1e10-1e12 FLOPS/W (Koomey's law still moves the
  distribution). `LogUniform(1e10, 1e12)` covers the H100-class range.
"""

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

# Resting human brain power, Raichle & Gusnard 2002 (~20 W). Sourced spread:
# brain metabolic power varies with task ~15-25 W across the literature.
HUMAN_BRAIN_POWER_DIST: Distribution = Uniform(low=15.0, high=25.0)

# Brain FLOPS-equivalent: REFERENCES.md flags "estimates span 1e15 to 1e20,
# uncertainty ~+/- 2 orders of magnitude" verbatim. LogUniform over that band
# reads the source directly.
BRAIN_COMPUTE_FLOPS_DIST: Distribution = LogUniform(low=1e15, high=1e20)

# Present-day accelerator compute efficiency (FLOPS/W). H100-class hardware
# sits around 1e11 FLOPS/W; the historical trend (Koomey) has been ~2x every
# 1.6 years, so the LogUniform range spans two orders of magnitude around
# today's midpoint. Scenarios that pin a specific device should narrow this.
COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST: Distribution = LogUniform(low=1e10, high=1e12)


__all__ = [
    "BOLTZMANN_DIST",
    "REFERENCE_TEMPERATURE_K_DIST",
    "HUMAN_BRAIN_POWER_DIST",
    "BRAIN_COMPUTE_FLOPS_DIST",
    "COMPUTE_EFFICIENCY_FLOPS_PER_W_DIST",
]
