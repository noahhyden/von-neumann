"""isru closure-ceiling validation: you cannot build from an absent element.

The lunar feedstock has O/Si/Fe/Ca/Al/Mg/Ti but only ppm C/H/N, so any part needing
bulk carbon/hydrogen/nitrogen falls above the closure ceiling. See REFERENCES.md.
"""

import pytest

from isru.closure import (
    LUNAR_REGOLITH_ELEMENT_WT_PCT,
    Part,
    available_elements,
    closure_ceiling,
    part_producible_locally,
)

LUNAR = available_elements(LUNAR_REGOLITH_ELEMENT_WT_PCT)


def test_lunar_has_the_structural_elements_but_not_volatiles():
    assert {"O", "Si", "Fe", "Ca", "Al", "Mg", "Ti"} <= LUNAR
    # Carbon, hydrogen, nitrogen are only ppm on the Moon - not in the bulk table.
    assert "C" not in LUNAR
    assert "H" not in LUNAR
    assert "N" not in LUNAR


def test_iron_structure_is_producible_polymer_is_not():
    steel_beam = Part("beam", 100.0, frozenset({"Fe", "O"}))
    polymer = Part("insulation", 100.0, frozenset({"C", "H"}))
    assert part_producible_locally(steel_beam, LUNAR)
    assert not part_producible_locally(polymer, LUNAR)


def test_full_local_copy_reaches_ceiling_one():
    parts = [
        Part("beam", 500.0, frozenset({"Fe"})),
        Part("panel", 300.0, frozenset({"Al", "O"})),
        Part("glass", 200.0, frozenset({"Si", "O"})),
    ]
    assert closure_ceiling(parts, LUNAR) == pytest.approx(1.0)


def test_absent_element_caps_the_ceiling_below_one():
    # 800 kg of local structure + 200 kg of carbon-bearing electronics/polymer.
    parts = [
        Part("structure", 800.0, frozenset({"Fe", "Al", "Si", "O"})),
        Part("electronics", 200.0, frozenset({"C", "Si"})),  # needs carbon -> import
    ]
    ceiling = closure_ceiling(parts, LUNAR)
    assert ceiling == pytest.approx(0.8)
    # This is the hard cap: closure-sim's C can never exceed it on the Moon.
    assert ceiling < 1.0


def test_ceiling_is_monotonic_in_available_elements():
    parts = [
        Part("structure", 700.0, frozenset({"Fe", "O"})),
        Part("titanium_part", 300.0, frozenset({"Ti"})),
    ]
    # Low threshold: Ti (3 wt%) available -> full closure possible.
    low_thresh = available_elements(LUNAR_REGOLITH_ELEMENT_WT_PCT, threshold_wt_pct=0.1)
    # High threshold: Ti excluded (below 5 wt%) -> the Ti part must be imported.
    high_thresh = available_elements(LUNAR_REGOLITH_ELEMENT_WT_PCT, threshold_wt_pct=5.0)
    assert "Ti" in low_thresh and "Ti" not in high_thresh
    assert closure_ceiling(parts, low_thresh) == pytest.approx(1.0)
    assert closure_ceiling(parts, high_thresh) == pytest.approx(0.7)
    assert closure_ceiling(parts, high_thresh) <= closure_ceiling(parts, low_thresh)


def test_all_parts_need_absent_element_gives_zero_ceiling():
    parts = [
        Part("a", 50.0, frozenset({"C"})),
        Part("b", 50.0, frozenset({"H"})),
    ]
    assert closure_ceiling(parts, LUNAR) == 0.0


def test_part_with_no_required_elements_is_producible():
    assert part_producible_locally(Part("generic", 1.0, frozenset()), LUNAR)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        closure_ceiling([Part("z", 0.0, frozenset({"Fe"}))], LUNAR)
    with pytest.raises(ValueError):
        available_elements(LUNAR_REGOLITH_ELEMENT_WT_PCT, threshold_wt_pct=-1.0)
