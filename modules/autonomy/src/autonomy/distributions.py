"""Distributional companions to autonomy's sourced numbers."""

from __future__ import annotations

from vn_core.uq import Distribution, LogUniform, Uniform

from autonomy.autonomy import (
    HONEYBEE_BRAIN_FLOPS,
    MOUSE_BRAIN_FLOPS,
    SELF_DRIVING_OPS_PER_S,
)

# Honeybee brain: 6 orders of magnitude between the spike-model floor and the full-physiology ceiling, so LogUniform is honest to that spread (REFERENCES.md).
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
