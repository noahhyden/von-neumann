"""assembly - the robotic build rate that sets the doubling clock."""

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
