"""The probe as a set of modules with a self-replication fraction.

Borgue & Hein (2020) describe a < 100 kg spacecraft of SIX modules that can
replicate ~70% of its own mass; the remaining ~30% is microchips and complex
electronics carried along and not replicated ("vitamins", closure-sim's framing).

Only the sourced quantities live here (the module set, the replicated fraction).
The per-module MASS breakdown is not published at the fidelity we need and is
tracked as a [GAP] in REFERENCES.md - it is deliberately NOT invented.
"""

from __future__ import annotations

from enum import Enum


class ProbeModule(str, Enum):
    """The six modules of the Borgue & Hein (2020) probe (verbatim mapping)."""

    POWER = "power"  # power generation (solar-electric)
    RESOURCE_HARVESTING = "resource_harvesting"  # ISRU / raw-material collection
    REPLICATION = "replication"  # laser powder-bed additive manufacturing
    PROPULSION = "propulsion"
    CONTROL = "control"
    TELEMETRY = "telemetry"  # telemetry, tracking, command + instruments


# Fraction of the probe's mass it can build for itself; the rest is imported
# vitamins (electronics). Borgue & Hein (2020). See REFERENCES.md.
REPLICATED_MASS_FRACTION: float = 0.70
