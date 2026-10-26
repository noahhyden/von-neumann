"""Onboard compute demand, and the autonomy wall."""

from __future__ import annotations

from dataclasses import dataclass

# --- Compute-demand anchors, operations per second; honeybee brain ~1e13 is a representative middle of a spike-model floor ~1e10 to full-physiology ~1e16 span, used as the lower autonomy anchor. See REFERENCES.md. ---
HONEYBEE_BRAIN_FLOPS: float = 1e13
# Self-driving car onboard compute: ~140 TOPS (L4-class; vision 50-100 TOPS, full L4 ~320 TOPS); integer ops/s, see the basis warning in REFERENCES.md.
SELF_DRIVING_OPS_PER_S: float = 1.4e14
# Mouse brain: brain-compute estimates span ~1e13-1e17 and 1e15 is a representative middle, used as the upper autonomy anchor.
MOUSE_BRAIN_FLOPS: float = 1e15


@dataclass(frozen=True)
class ComputeDemandBand:
    """The [ESTIMATE] compute-demand band for probe autonomy, operations per second."""

    low_flops: float
    central_flops: float
    high_flops: float


def required_compute_band() -> ComputeDemandBand:
    """The sourced demand band: honeybee (low) - self-driving car (central) - mouse (high)."""
    return ComputeDemandBand(
        low_flops=HONEYBEE_BRAIN_FLOPS,
        central_flops=SELF_DRIVING_OPS_PER_S,
        high_flops=MOUSE_BRAIN_FLOPS,
    )


def required_compute_power_w(
    required_flops: float, efficiency_flops_per_w: float
) -> float:
    """Electrical power (W) to run required compute: required_flops / efficiency."""
    if required_flops <= 0:
        raise ValueError("required_flops must be positive")
    if efficiency_flops_per_w <= 0:
        raise ValueError("efficiency_flops_per_w must be positive")
    return required_flops / efficiency_flops_per_w


def compute_fraction_needed(
    required_flops: float, total_power_w: float, efficiency_flops_per_w: float
) -> float:
    """The share of total power compute demands - the DERIVED replacement for the 0.70 split."""
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
    """Distance (AU) where affordable compute drops below the required compute."""
    if supply_flops_at_1au <= 0:
        raise ValueError("supply_flops_at_1au must be positive")
    if required_flops <= 0:
        raise ValueError("required_flops must be positive")
    return (supply_flops_at_1au / required_flops) ** 0.5
