"""The closure ceiling: you cannot build from an element the body does not have.

`closure-sim` marks each subsystem `producible_locally` as a hand-set boolean. This
module gives that boolean a physical basis: a part is producible locally only if every
element it requires is present in the local feedstock above a usable abundance. The
**closure ceiling** is then the mass fraction of a copy made of such parts - a hard
upper bound on closure that no amount of clever manufacturing can beat, because the raw
element simply is not there.

The lunar case makes the point sharp. Mare regolith is rich in O, Si, Fe, Ca, Al, Mg,
Ti - so structure and oxygen close easily - but carbon, hydrogen, and nitrogen occur
only as tens of ppm of solar-wind implantation (polar water ice aside). Anything needing
bulk C/H/N (polymers, many electronics) must be imported: it sits above the ceiling.

Pure accounting over a sourced composition - no geochemistry or extraction simulation
(over-nesting, CLAUDE.md 3). Composition figures are in REFERENCES.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Representative lunar mare-soil elemental abundance, wt% (Lunar Sourcebook, Apollo
# averages). Bulk major elements; trace elements below ~0.1 wt% are omitted. Volatiles
# (H, C, N) are present only as tens of ppm from solar wind - well below any usable
# threshold - so they are deliberately absent from this bulk table. See REFERENCES.md.
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

# Default usable-abundance threshold, wt%. An element below this in the feedstock cannot
# be a bulk local source. 0.1 wt% is a representative bulk-extraction floor; it is a
# documented modelling choice, adjustable per scenario (CLAUDE.md 1).
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
    """True iff every element the part requires is available locally.

    A part with no listed required elements is treated as producible (nothing gates it);
    callers should list the gating elements for parts that have one.
    """
    return part.required_elements <= available


def closure_ceiling(parts: list[Part], available: frozenset[str]) -> float:
    """Max fraction of a copy's mass that can be built locally, given the feedstock.

    ceiling = (mass of parts whose required elements are all available) / (total mass).
    This is the hard upper bound on closure-sim's closure ratio C: C <= ceiling, with
    equality only if every producible part is actually produced locally. Cannot close on
    an element the body lacks - such parts count against the ceiling.
    """
    total = sum(p.mass_kg for p in parts)
    if total <= 0:
        raise ValueError("total part mass must be positive")
    local = sum(
        p.mass_kg for p in parts if part_producible_locally(p, available)
    )
    return local / total
