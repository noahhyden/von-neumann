"""Robotic build rate: how fast a space factory turns feedstock into installed mass.

This is the most load-bearing number in the whole project. `closure-sim` and
`multi-probe` take a *hand-set* `local_build_rate_kg_per_day` (~20 kg/day) as an input,
and that single number sets the fleet's entire doubling cadence: the copy time is
`closure_ratio * seed_mass / build_rate` (FINDINGS #9: ~582 days for the lunar seed).
This module derives that rate from published numbers instead of assuming it.

The derivation is a simple product, not a discrete-event assembly simulator (that would
be over-nesting, CLAUDE.md §3):

    build_rate = manipulators * deposition_rate * hours_per_day * duty_cycle * yield

- **deposition_rate** comes from real metal additive manufacturing: WAAM (wire-arc)
  ~1-10 kg/h, LPBF (laser powder-bed) ~0.2-1.4 kg/h.
- **duty_cycle** and **yield** are grounded in Overall Equipment Effectiveness (OEE):
  world-class ~85%, typical manufacturing ~60%, with the quality (yield) component of
  world-class TPM at ~99.9%.

Because every input is a terrestrial-robot proxy for a space factory that does not yet
exist, the whole result is tagged `[ESTIMATE]`. Its honest form is not a point but a
**band**: a single slow head at world-class OEE lands near closure-sim's 20 kg/day,
while NASA's 1980 self-replicating lunar factory (a 100-tonne seed that copies itself in
one year) implies ~274 kg/day - a >10x spread that propagates straight into the doubling
clock. Every number is sourced in REFERENCES.md.
"""

from __future__ import annotations

from dataclasses import dataclass

# Hours in a day (a factory can run continuously; downtime is captured in duty_cycle).
HOURS_PER_DAY: float = 24.0

# --- Deposition rates, kg/h (metal additive manufacturing). See REFERENCES.md. ---
# WAAM (wire-arc) high-throughput band and LPBF (laser powder-bed) band.
WAAM_RATE_KG_PER_H: tuple[float, float] = (1.0, 10.0)
LPBF_RATE_KG_PER_H: tuple[float, float] = (0.2, 1.4)

# --- Overall Equipment Effectiveness (OEE) anchors. See REFERENCES.md. ---
# World-class OEE = 0.85 (Nakajima/TPM), built from availability>=0.90, performance
# >=0.95, quality>=0.999. Typical discrete manufacturing averages ~0.60.
WORLD_CLASS_OEE: float = 0.85
TYPICAL_OEE: float = 0.60
WORLD_CLASS_QUALITY: float = 0.999  # first-pass yield component of world-class OEE

# --- NASA Advanced Automation for Space Missions (1982, CP-2255) anchor. ---
# A 100-tonne seed factory that produces a full duplicate of itself in one year.
AASM_SEED_MASS_KG: float = 100_000.0
AASM_SELF_COPY_DAYS: float = 365.0


@dataclass(frozen=True)
class BuildRateBand:
    """The [ESTIMATE] build-rate band (kg/day) with a named point in the middle.

    low and high bracket the honest uncertainty; anchor is the single-slow-head,
    world-class-OEE point that reproduces closure-sim's hand-set 20 kg/day.
    """

    low_kg_per_day: float
    anchor_kg_per_day: float
    high_kg_per_day: float

    def __post_init__(self) -> None:
        # [inv:as-band] low > 0, and low <= anchor <= high. Never gated: a band that
        # violates this is malformed and callers must not silently see it in release.
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
    """Derive the local build rate (kg/day) from its physical components.

    build_rate = manipulators * deposition_rate * hours_per_day * duty_cycle * yield.
    duty_cycle is the availability x performance part of OEE; first_pass_yield is the
    quality part (net-of-scrap good mass). Their product is the effective OEE.
    """
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
    """NASA AASM implied build rate: a seed factory that copies itself in self_copy_days.

    100 tonnes / 365 days = ~274 kg/day. This is the aggressive whole-factory upper
    anchor, from a published NASA concept - not a rate this module invents.
    """
    if seed_mass_kg <= 0 or self_copy_days <= 0:
        raise ValueError("seed_mass_kg and self_copy_days must be positive")
    return seed_mass_kg / self_copy_days


def build_rate_band() -> BuildRateBand:
    """The sourced [ESTIMATE] band, from documented parameter corners.

    - low: one LPBF head (0.2 kg/h) at typical OEE (0.60).
    - anchor: one slow WAAM head (1.0 kg/h) at world-class availability x performance
      (0.85) and world-class quality (0.999) -> ~20 kg/day, reproducing closure-sim.
    - high: NASA AASM's 100 t/yr self-copy -> ~274 kg/day.
    """
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
    """Days for one factory/probe to build one copy's worth of *local* structure.

    copy_time = closure_ratio * seed_mass / build_rate. This is exactly
    `multi_probe.time_to_build_one_copy_days` in the machinery-bound regime and
    `closure-sim`'s replication cadence - reproduced here (not re-invented) so this
    module can show how its derived rate sets the doubling clock. It introduces no new
    number: it is the same physics, consuming the rate this module derives.
    """
    if build_rate_kg_per_day <= 0:
        raise ValueError("build_rate_kg_per_day must be positive")
    if seed_mass_kg <= 0:
        raise ValueError("seed_mass_kg must be positive")
    if not 0.0 <= closure_ratio <= 1.0:
        raise ValueError("closure_ratio must be in [0, 1]")
    return closure_ratio * seed_mass_kg / build_rate_kg_per_day
