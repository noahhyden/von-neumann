"""Structural strength as a mass-penalty parameter (the `structures` decision)."""

from __future__ import annotations

# Sintered lunar-regolith compressive strength by technique, MPa: a >100x band, not a point (sources: REFERENCES.md).
SINTERED_REGOLITH_STRENGTH_MPA: dict[str, float] = {
    "solar_3d_printing": 4.2,      # <5 MPa; roller/PBF class
    "microwave_sintering": 37.0,   # KLS-1 simulant
    "sintering_air": 98.0,
    "sintering_vacuum": 152.0,
    "traditional_dense": 232.0,    # 99% density
    "glass_ceramic_800c": 355.0,   # heat-treated glass-ceramic
}
SINTERED_REGOLITH_STRENGTH_BAND_MPA: tuple[float, float] = (2.49, 355.0)


def mass_penalty_k(required_strength_mpa: float, material_strength_mpa: float) -> float:
    """Structural mass penalty k = required / material for a weaker local material."""
    if required_strength_mpa <= 0:
        raise ValueError("required_strength_mpa must be positive")
    if material_strength_mpa <= 0:
        raise ValueError("material_strength_mpa must be positive")
    return max(1.0, required_strength_mpa / material_strength_mpa)


def is_producible_locally(
    material_strength_mpa: float,
    required_strength_mpa: float,
    hard_threshold: bool = False,
) -> bool:
    """Whether a part can be built from the local material."""
    if hard_threshold:
        return material_strength_mpa >= required_strength_mpa
    return True


def closure_with_structural_penalty(
    local_structural_kg: float,
    other_local_kg: float,
    vitamin_kg: float,
    k: float = 1.0,
) -> float:
    """Closure ratio when local structural mass is scaled by the penalty k."""
    if local_structural_kg < 0 or other_local_kg < 0 or vitamin_kg < 0:
        raise ValueError("masses must be non-negative")
    if k < 1.0:
        raise ValueError("k must be >= 1 (a mass penalty, not a saving)")
    new_local = k * local_structural_kg + other_local_kg
    total = new_local + vitamin_kg
    if total <= 0:
        raise ValueError("total mass must be positive")
    return new_local / total
