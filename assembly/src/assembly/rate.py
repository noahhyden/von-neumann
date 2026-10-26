"""Robotic build rate: how fast a space factory turns feedstock into installed mass."""

from __future__ import annotations

from dataclasses import dataclass

# Hours in a day (a factory can run continuously; downtime is captured in duty_cycle).
HOURS_PER_DAY: float = 24.0

# --- Deposition rates, kg/h (metal additive manufacturing): WAAM (wire-arc) high-throughput band and LPBF (laser powder-bed) band. See REFERENCES.md. ---
WAAM_RATE_KG_PER_H: tuple[float, float] = (1.0, 10.0)
LPBF_RATE_KG_PER_H: tuple[float, float] = (0.2, 1.4)

# --- OEE anchors: world-class 0.85 (Nakajima/TPM) from availability>=0.90, performance>=0.95, quality>=0.999; typical discrete manufacturing ~0.60. See REFERENCES.md. ---
WORLD_CLASS_OEE: float = 0.85
TYPICAL_OEE: float = 0.60
WORLD_CLASS_QUALITY: float = 0.999  # first-pass yield component of world-class OEE

# --- NASA Advanced Automation for Space Missions (1982, CP-2255) anchor: a 100-tonne seed factory that produces a full duplicate of itself in one year. ---
AASM_SEED_MASS_KG: float = 100_000.0
AASM_SELF_COPY_DAYS: float = 365.0


@dataclass(frozen=True)
class BuildRateBand:
    """The [ESTIMATE] build-rate band (kg/day) with a named point in the middle."""

    low_kg_per_day: float
    anchor_kg_per_day: float
    high_kg_per_day: float

    def __post_init__(self) -> None:
        # [inv:as-band] low > 0 and low <= anchor <= high; never gated, since a malformed band must not be silently seen in release.
        if self.low_kg_per_day <= 0:
            raise ValueError(
                f"[inv:as-band] low_kg_per_day={self.low_kg_per_day} must be > 0"
            )
        if not (self.low_kg_per_day <= self.anchor_kg_per_day <= self.high_kg_per_day):
            raise ValueError(
                f"[inv:as-band] must have low <= anchor <= high; got "
                f"low={self.low_kg_per_day}, anchor={self.anchor_kg_per_day}, "
                f"high={self.high_kg_per_day}"
            )


def machinery_build_rate_kg_per_day(
    manipulators: int,
    deposition_rate_kg_per_h: float,
    duty_cycle: float,
    first_pass_yield: float,
    hours_per_day: float = HOURS_PER_DAY,
) -> float:
    """Derive the local build rate (kg/day) from its physical components."""
    if manipulators < 1:
        raise ValueError("manipulators must be >= 1")
    if deposition_rate_kg_per_h <= 0:
        raise ValueError("deposition_rate_kg_per_h must be positive")
    if not 0.0 < duty_cycle <= 1.0:
        raise ValueError("duty_cycle must be in (0, 1]")
    if not 0.0 < first_pass_yield <= 1.0:
        raise ValueError("first_pass_yield must be in (0, 1]")
    if hours_per_day <= 0:
        raise ValueError("hours_per_day must be positive")
    return (
        manipulators
        * deposition_rate_kg_per_h
        * hours_per_day
        * duty_cycle
        * first_pass_yield
    )


def aasm_implied_rate_kg_per_day(
    seed_mass_kg: float = AASM_SEED_MASS_KG,
    self_copy_days: float = AASM_SELF_COPY_DAYS,
) -> float:
    """NASA AASM implied build rate: a seed factory that copies itself in self_copy_days."""
    if seed_mass_kg <= 0 or self_copy_days <= 0:
        raise ValueError("seed_mass_kg and self_copy_days must be positive")
    return seed_mass_kg / self_copy_days


def build_rate_band() -> BuildRateBand:
    """The sourced [ESTIMATE] band, from documented parameter corners."""
    low = machinery_build_rate_kg_per_day(
        manipulators=1,
        deposition_rate_kg_per_h=LPBF_RATE_KG_PER_H[0],
        duty_cycle=TYPICAL_OEE,
        first_pass_yield=WORLD_CLASS_QUALITY,
    )
    anchor = machinery_build_rate_kg_per_day(
        manipulators=1,
        deposition_rate_kg_per_h=WAAM_RATE_KG_PER_H[0],
        duty_cycle=WORLD_CLASS_OEE,
        first_pass_yield=WORLD_CLASS_QUALITY,
    )
    high = aasm_implied_rate_kg_per_day()
    return BuildRateBand(
        low_kg_per_day=low,
        anchor_kg_per_day=anchor,
        high_kg_per_day=high,
    )


def copy_time_days(
    build_rate_kg_per_day: float,
    seed_mass_kg: float,
    closure_ratio: float,
) -> float:
    """Days for one factory/probe to build one copy's worth of *local* structure."""
    if build_rate_kg_per_day <= 0:
        raise ValueError("build_rate_kg_per_day must be positive")
    if seed_mass_kg <= 0:
        raise ValueError("seed_mass_kg must be positive")
    if not 0.0 <= closure_ratio <= 1.0:
        raise ValueError("closure_ratio must be in [0, 1]")
    return closure_ratio * seed_mass_kg / build_rate_kg_per_day
