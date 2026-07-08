"""Structural strength as a mass-penalty parameter (the `structures` decision).

`ROADMAP-PROPOSAL.md` floated `structures` as a possible module: give closure-sim's
``producible_locally`` boolean a physics basis (local material strength vs a required
strength) plus a mass penalty for weaker material. The proposal's own default was to
*demote* it to a parameter inside closure-sim unless the k=1.0 regression shows the
physics moves real closure numbers. This file is that demotion - a small, additive
helper, not a new module - and the tests make the call.

Two effects a weak local material can have:

1. **Mass penalty (strength-scalable parts).** A load-bearing member built from a weaker
   material needs more cross-section to carry the same load, so its mass scales up by
   ``k = required_strength / material_strength`` (>= 1). The part is still made locally;
   it just costs more mass and build time.
2. **Hard threshold (non-scalable parts).** Some parts (a pressure vessel, a precise
   stiffness) need a minimum material strength that no amount of extra mass supplies. If
   the local material is below that threshold, the part cannot be made locally at all -
   it flips to a vitamin (import), which is what actually moves closure.

The key finding the tests confirm: with ``k = 1`` the closure numbers are *identical* to
closure-sim's, and a realistic mass penalty raises closure slightly (more local mass vs
fixed imports) while mostly costing throughput - so the *mass penalty* belongs here as a
parameter, and only the *threshold* (via ``producible_locally``, which closure-sim
already has) moves closure. That is why `structures` stays a parameter, not a directory.

Sintered-regolith strengths span >100x by technique - carry them as a band, never a
point. Numbers in REFERENCES.md. Pure functions, no pimas, no RNG.
"""

from __future__ import annotations

# Sintered lunar-regolith compressive strength by technique, MPa (representative flight-
# simulant values; the span is >100x, so this is a band not a point). See REFERENCES.md.
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
    """Structural mass penalty k = required / material for a weaker local material.

    Clamped at 1.0: a material at or above the required strength gets no penalty (this
    conservative model does not credit over-strength material with mass savings). k > 1
    means a strength-scalable part must be that many times heavier to carry the load.
    """
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
    """Whether a part can be built from the local material.

    For a strength-scalable part (``hard_threshold=False``) the answer is always yes -
    weakness is paid in mass, not feasibility. For a hard-threshold part it is yes only
    if the material meets the required strength; below it, the part must be imported (a
    vitamin), which is the case that lowers closure.
    """
    if hard_threshold:
        return material_strength_mpa >= required_strength_mpa
    return True


def closure_with_structural_penalty(
    local_structural_kg: float,
    other_local_kg: float,
    vitamin_kg: float,
    k: float = 1.0,
) -> float:
    """Closure ratio when local structural mass is scaled by the penalty k.

    new_local = k*structural + other_local; closure = new_local / (new_local + vitamin).
    With k=1 this is exactly closure-sim's local/(local+vitamin) - the regression that
    keeps this a no-op parameter until strength data says otherwise.
    """
    if local_structural_kg < 0 or other_local_kg < 0 or vitamin_kg < 0:
        raise ValueError("masses must be non-negative")
    if k < 1.0:
        raise ValueError("k must be >= 1 (a mass penalty, not a saving)")
    new_local = k * local_structural_kg + other_local_kg
    total = new_local + vitamin_kg
    if total <= 0:
        raise ValueError("total mass must be positive")
    return new_local / total
