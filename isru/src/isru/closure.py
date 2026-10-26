"""The closure ceiling: you cannot build from an element the body does not have."""

from __future__ import annotations

from dataclasses import dataclass, field

# Representative lunar mare-soil bulk abundance, wt% (Lunar Sourcebook, Apollo averages); trace <0.1 wt% omitted and volatiles H/C/N excluded (ppm solar wind), see REFERENCES.md.
LUNAR_REGOLITH_ELEMENT_WT_PCT: dict[str, float] = {
    "O": 44.0,
    "Si": 21.0,
    "Fe": 13.0,
    "Ca": 10.0,
    "Al": 7.0,
    "Mg": 6.0,
    "Ti": 3.0,
    "Na": 0.3,
    "Mn": 0.2,
    "Cr": 0.2,
    "K": 0.1,
}

# Default usable-abundance floor, wt%: 0.1 is a representative bulk-extraction floor, a documented modelling choice adjustable per scenario (CLAUDE.md 1).
DEFAULT_USABLE_THRESHOLD_WT_PCT: float = 0.1


@dataclass(frozen=True)
class Part:
    """One part of a copy: its mass and the elements it fundamentally requires."""

    name: str
    mass_kg: float
    required_elements: frozenset[str] = field(default_factory=frozenset)


def available_elements(
    composition_wt_pct: dict[str, float],
    threshold_wt_pct: float = DEFAULT_USABLE_THRESHOLD_WT_PCT,
) -> frozenset[str]:
    """Elements present in a feedstock at or above the usable-abundance threshold."""
    if threshold_wt_pct < 0:
        raise ValueError("threshold_wt_pct must be non-negative")
    return frozenset(
        el for el, wt in composition_wt_pct.items() if wt >= threshold_wt_pct
    )


def part_producible_locally(part: Part, available: frozenset[str]) -> bool:
    """True iff every element the part requires is available locally."""
    return part.required_elements <= available


def closure_ceiling(parts: list[Part], available: frozenset[str]) -> float:
    """Max fraction of a copy's mass that can be built locally, given the feedstock."""
    total = sum(p.mass_kg for p in parts)
    if total <= 0:
        raise ValueError("total part mass must be positive")
    local = sum(
        p.mass_kg for p in parts if part_producible_locally(p, available)
    )
    return local / total
