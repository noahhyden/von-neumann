"""spine - the cross-scale integrator.

Threads one closure-sim `Factory` through the single-factory, local-fleet, and galaxy
folds so their replication cadences are *derived from one source* rather than assumed
independently at each scale. Its headline contribution: the swarm's per-star
manufacturing dwell (`settle_time_years`), previously an ungrounded `[ESTIMATE]` of 0.0,
is now derived from the same closure-sim build physics the fleet uses - and shown to be a
negligible tax on galactic exploration, because interstellar transit dominates.

Adds no new physics; only routes numbers the existing modules already document (CLAUDE.md
§4). See REFERENCES.md.
"""

from spine.run import (
    DAYS_PER_JULIAN_YEAR,
    DwellTax,
    SpineResult,
    derive_settle_time_years,
    measure_dwell_tax,
    run_spine,
)
from spine.scenario import SpineScenario, default_factory

__all__ = [
    "run_spine",
    "measure_dwell_tax",
    "derive_settle_time_years",
    "SpineResult",
    "DwellTax",
    "SpineScenario",
    "default_factory",
    "DAYS_PER_JULIAN_YEAR",
]
