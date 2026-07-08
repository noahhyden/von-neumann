"""Onboard compute demand, and the autonomy wall.

`probe-sim` already models compute *supply*: the FLOPS a probe's solar array can power,
falling as 1/d^2 with heliocentric distance. What it lacked - and what
`mission`/`multi-probe` papered over with a free 0.70 manufacturing / 0.30 compute split
- is the *demand*: how much compute a probe actually needs to run itself with no human in
the loop. This module supplies that demand, from sourced proxies, and the two sides meet
at an **autonomy wall**: the distance beyond which the probe can no longer power the
thinking it needs.

The demand is deliberately a **band, not a point**, bracketed by three independent lines:

- **honeybee brain ~1e13 FLOPS** (lower bound - a real insect that navigates, forages,
  and makes decisions),
- **a self-driving car ~1.4e14 ops/s** (~140 TOPS - a real autonomous system doing
  perception + control),
- **mouse brain ~1e15 FLOPS** (upper bound - a small mammal).

The self-driving figure lands squarely between the two brains, so three unrelated
estimates converge on the same 1e13-1e15 range. "The FLOPS to run a whole factory" is a
genuine `[GAP]`, but it is boundable to this same band rather than invented.

Basis warning (CLAUDE.md 1): the self-driving figure is TOPS (integer tera-operations),
the brain figures are FLOPS (floating-point). They are compared here only as
order-of-magnitude "operations per second"; the distinction is flagged, not hidden.

Pure accounting over sourced numbers - no neural-net or SLAM simulation (over-nesting,
CLAUDE.md 3), no pimas, no RNG (7). It reuses `power-budget`'s watts<->FLOPS conversion
and closes the loop with `probe-sim`'s supply model. Every number is in REFERENCES.md.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Compute-demand anchors, operations per second. See REFERENCES.md. ---
# Honeybee brain: order-of-magnitude estimate (spike-model floor ~1e10, full-physiology
# ~1e16); 1e13 is a representative middle used as the lower autonomy anchor.
HONEYBEE_BRAIN_FLOPS: float = 1e13
# Self-driving car onboard compute: ~140 TOPS (L4-class; vision 50-100 TOPS, full L4
# ~320 TOPS). Integer ops/s - see the basis warning.
SELF_DRIVING_OPS_PER_S: float = 1.4e14
# Mouse brain: brain-compute estimates span ~1e13-1e17; 1e15 is a representative middle
# used as the upper autonomy anchor.
MOUSE_BRAIN_FLOPS: float = 1e15


@dataclass(frozen=True)
class ComputeDemandBand:
    """The [ESTIMATE] compute-demand band for probe autonomy, operations per second."""

    low_flops: float
    central_flops: float
    high_flops: float


def required_compute_band() -> ComputeDemandBand:
    """The sourced demand band: honeybee (low) - self-driving car (central) - mouse (high).

    Three independent lines converging on 1e13-1e15 ops/s. The central anchor is the
    self-driving car, an engineered system of known capability, not a brain estimate.
    """
    return ComputeDemandBand(
        low_flops=HONEYBEE_BRAIN_FLOPS,
        central_flops=SELF_DRIVING_OPS_PER_S,
        high_flops=MOUSE_BRAIN_FLOPS,
    )


def required_compute_power_w(
    required_flops: float, efficiency_flops_per_w: float
) -> float:
    """Electrical power (W) to run required compute: required_flops / efficiency.

    The inverse of `power_budget.compute_capacity_flops` (flops = power x efficiency).
    """
    if required_flops <= 0:
        raise ValueError("required_flops must be positive")
    if efficiency_flops_per_w <= 0:
        raise ValueError("efficiency_flops_per_w must be positive")
    return required_flops / efficiency_flops_per_w


def compute_fraction_needed(
    required_flops: float, total_power_w: float, efficiency_flops_per_w: float
) -> float:
    """The share of total power compute demands - the DERIVED replacement for the 0.70 split.

    = required_compute_w / total_power_w. Instead of hand-setting manufacturing 0.70 /
    compute 0.30, the compute fraction falls out of the sourced demand and the available
    power. Raises if compute alone would need more than the whole budget (an infeasible
    design at this distance/power).
    """
    if total_power_w <= 0:
        raise ValueError("total_power_w must be positive")
    compute_w = required_compute_power_w(required_flops, efficiency_flops_per_w)
    fraction = compute_w / total_power_w
    if fraction > 1.0:
        raise ValueError(
            "required compute exceeds the entire power budget "
            f"(needs {compute_w:.1f} W of {total_power_w:.1f} W available)"
        )
    return fraction


def affordable_compute_at(supply_flops_at_1au: float, distance_au: float) -> float:
    """Compute a probe can power at a distance: supply_1AU / d^2 (the 1/d^2 supply law)."""
    if supply_flops_at_1au < 0:
        raise ValueError("supply_flops_at_1au must be non-negative")
    if distance_au <= 0:
        raise ValueError("distance_au must be positive")
    return supply_flops_at_1au / (distance_au * distance_au)


def autonomy_wall_au(supply_flops_at_1au: float, required_flops: float) -> float:
    """Distance (AU) where affordable compute drops below the required compute.

    Supply falls as 1/d^2, demand is flat, so they meet at
    d_wall = sqrt(supply_1AU / required). Beyond it the probe cannot think hard enough to
    run itself. This is the compute analogue of power-source's crossover, and it equals
    `probe_sim.max_distance_for_compute` fed this module's sourced demand (loop closed).
    """
    if supply_flops_at_1au <= 0:
        raise ValueError("supply_flops_at_1au must be positive")
    if required_flops <= 0:
        raise ValueError("required_flops must be positive")
    return (supply_flops_at_1au / required_flops) ** 0.5
