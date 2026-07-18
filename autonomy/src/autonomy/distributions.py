"""Distributional companions to autonomy's sourced numbers.

Issue #35 (UQ) applied to autonomy. Every constant is an order-of-magnitude
estimate on a biological or engineering compute budget - the honest read is
LogUniform over the range REFERENCES.md names.

- HONEYBEE_BRAIN_FLOPS: 1e13 is the "representative middle" of a documented
  1e10-1e16 span (spike-model floor to full-physiology). LogUniform preserves
  that six-order-of-magnitude honesty.
- MOUSE_BRAIN_FLOPS: 1e15 is the middle of a documented 1e13-1e17 range.
- SELF_DRIVING_OPS_PER_S: 1.4e14 sits inside a documented 5e13-3.2e14 band
  (vision at 50 TOPS to full L4 at 320 TOPS).
"""

from __future__ import annotations

from vn_core.uq import Distribution, LogUniform, Uniform

from autonomy.autonomy import (
    HONEYBEE_BRAIN_FLOPS,
    MOUSE_BRAIN_FLOPS,
    SELF_DRIVING_OPS_PER_S,
)

# Honeybee brain: 6 orders of magnitude between spike-model floor and full-
# physiology ceiling. LogUniform is honest to that spread.
HONEYBEE_BRAIN_FLOPS_DIST: Distribution = LogUniform(low=1e10, high=1e16)

# Mouse brain: 4 orders of magnitude across the estimate range.
MOUSE_BRAIN_FLOPS_DIST: Distribution = LogUniform(low=1e13, high=1e17)

# Self-driving car: relatively tight band (vision to full L4), Uniform.
SELF_DRIVING_OPS_PER_S_DIST: Distribution = Uniform(low=5e13, high=3.2e14)


__all__ = [
    "HONEYBEE_BRAIN_FLOPS_DIST",
    "MOUSE_BRAIN_FLOPS_DIST",
    "SELF_DRIVING_OPS_PER_S_DIST",
]
