"""The probe as a set of modules with a self-replication fraction."""

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


# Fraction of the probe mass it can build itself (Borgue & Hein 2020, ~70%); the rest is imported vitamins (electronics), see REFERENCES.md.
REPLICATED_MASS_FRACTION: float = 0.70
