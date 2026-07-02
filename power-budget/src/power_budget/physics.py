"""The physics that floors and anchors a compute power budget.

Two hard reference points bound "how much thinking a watt buys":

- the **Landauer limit** — the thermodynamic minimum energy to erase one bit,
  E = k_B * T * ln2 (Landauer 1961). At 300 K that is ~2.9e-21 J/bit, i.e. a ceiling
  of ~3.5e20 irreversible bit-operations per joule. No computer, space-borne or not,
  beats it (without reversible computing).
- the **human brain** — ~20 W (Raichle & Gusnard 2002), the canonical scale for
  "general intelligence per watt".

Every number here is sourced — see REFERENCES.md. All energies in joules, powers in
watts, temperatures in kelvin.
"""

from __future__ import annotations

import math

# Boltzmann constant, J/K. Exact by the 2019 SI redefinition. (CODATA / SI.)
BOLTZMANN_J_PER_K: float = 1.380649e-23

# Resting human brain power draw, W. Raichle & Gusnard (2002), PNAS. See REFERENCES.
HUMAN_BRAIN_POWER_W: float = 20.0

# [ESTIMATE] Brain-equivalent compute, FLOPS. Deeply uncertain — estimates span
# ~1e15 to ~1e20; we use 1e18 as an order-of-magnitude midpoint from Sandberg &
# Bostrom (2008), "Whole Brain Emulation: A Roadmap". Treat as a scale marker, not a
# measured value. See REFERENCES.md.
BRAIN_COMPUTE_FLOPS_ESTIMATE: float = 1e18


def landauer_limit_j_per_bit(temperature_k: float = 300.0) -> float:
    """Minimum energy (J) to erase one bit at a given temperature: k_B * T * ln2."""
    if temperature_k <= 0:
        raise ValueError("temperature_k must be positive")
    return BOLTZMANN_J_PER_K * temperature_k * math.log(2)


def max_bit_operations_per_joule(temperature_k: float = 300.0) -> float:
    """Thermodynamic ceiling on irreversible bit-operations per joule (1 / Landauer)."""
    return 1.0 / landauer_limit_j_per_bit(temperature_k)


def brain_equivalents(flops: float, brain_flops: float = BRAIN_COMPUTE_FLOPS_ESTIMATE) -> float:
    """How many brain-equivalents a compute throughput (FLOPS) represents.

    Uses the [ESTIMATE] brain-FLOPS scale — an order-of-magnitude marker, not a
    precise ratio. See REFERENCES.md.
    """
    if brain_flops <= 0:
        raise ValueError("brain_flops must be positive")
    return flops / brain_flops
