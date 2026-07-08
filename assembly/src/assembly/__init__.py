"""assembly - the robotic build rate that sets the doubling clock.

Derives `closure-sim`/`multi-probe`'s hand-set `local_build_rate_kg_per_day` from
published metal-AM deposition rates (WAAM, LPBF) and Overall Equipment Effectiveness,
instead of assuming it. The result is an honest `[ESTIMATE]` band (a single slow head
at world-class OEE ~ closure-sim's 20 kg/day; NASA's 1980 lunar factory ~ 274 kg/day),
and that >10x spread propagates straight into the fleet copy time
`closure_ratio * seed_mass / build_rate` (FINDINGS #9's ~582-day clock).

Pure algebra over sourced numbers - no discrete-event assembly simulator (CLAUDE.md §3),
no pimas, no RNG (§7). Every number traces to a source; see REFERENCES.md.
"""

from assembly.rate import (
    AASM_SEED_MASS_KG,
    AASM_SELF_COPY_DAYS,
    HOURS_PER_DAY,
    LPBF_RATE_KG_PER_H,
    TYPICAL_OEE,
    WAAM_RATE_KG_PER_H,
    WORLD_CLASS_OEE,
    WORLD_CLASS_QUALITY,
    BuildRateBand,
    aasm_implied_rate_kg_per_day,
    build_rate_band,
    copy_time_days,
    machinery_build_rate_kg_per_day,
)

__all__ = [
    "AASM_SEED_MASS_KG",
    "AASM_SELF_COPY_DAYS",
    "HOURS_PER_DAY",
    "LPBF_RATE_KG_PER_H",
    "WAAM_RATE_KG_PER_H",
    "TYPICAL_OEE",
    "WORLD_CLASS_OEE",
    "WORLD_CLASS_QUALITY",
    "BuildRateBand",
    "aasm_implied_rate_kg_per_day",
    "build_rate_band",
    "copy_time_days",
    "machinery_build_rate_kg_per_day",
]
