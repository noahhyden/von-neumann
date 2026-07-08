"""structures decision: the k=1.0 regression and the parameter-vs-module verdict.

The mandatory test is that with no mass penalty (k=1.0) the closure numbers are
identical to compute_closure - which is why `structures` stays a parameter here, not a
new module. Sintered-regolith strengths span >100x. See REFERENCES.md and
ROADMAP-PROPOSAL.md.
"""

import pytest

from closure_sim.closure import compute_closure
from closure_sim.models import Factory, Subsystem
from closure_sim.structures import (
    SINTERED_REGOLITH_STRENGTH_BAND_MPA,
    SINTERED_REGOLITH_STRENGTH_MPA,
    closure_with_structural_penalty,
    is_producible_locally,
    mass_penalty_k,
)


def _factory() -> Factory:
    # 700 kg local structure + 200 kg local other + 100 kg imported electronics.
    return Factory(
        name="k-test",
        subsystems=[
            Subsystem(name="frame", mass_kg=700.0, category="structure"),
            Subsystem(name="tanks", mass_kg=200.0, category="structure"),
            Subsystem(name="chips", mass_kg=100.0, category="compute", producible_locally=False),
        ],
    )


def test_mass_penalty_k():
    # Weaker material -> heavier part. Microwave regolith (37) for a 40 MPa need: k=1.08.
    assert mass_penalty_k(40.0, 37.0) == pytest.approx(40.0 / 37.0)
    # Solar-3D regolith (4.2) for the same need: ~9.5x heavier.
    assert mass_penalty_k(40.0, 4.2) == pytest.approx(40.0 / 4.2)
    # Material stronger than required: no penalty (clamped at 1.0).
    assert mass_penalty_k(40.0, 152.0) == 1.0


def test_producible_locally_scalable_vs_threshold():
    # Strength-scalable parts are always buildable (weakness paid in mass).
    assert is_producible_locally(4.2, 40.0, hard_threshold=False)
    # Hard-threshold parts need the material to meet the spec.
    assert is_producible_locally(152.0, 40.0, hard_threshold=True)
    assert not is_producible_locally(4.2, 40.0, hard_threshold=True)


def test_k_equals_one_reproduces_closure_sim_exactly():
    # THE mandatory regression: k=1.0 must reproduce compute_closure bit-for-bit.
    f = _factory()
    baseline = compute_closure(f).closure_ratio
    assert baseline == pytest.approx(0.9)  # 900 local / 1000 total
    penalised = closure_with_structural_penalty(
        local_structural_kg=f.local_mass_kg, other_local_kg=0.0,
        vitamin_kg=f.vitamin_mass_kg, k=1.0,
    )
    assert penalised == pytest.approx(baseline, rel=1e-12)


def test_mass_penalty_raises_closure_not_lowers_it():
    # A weaker material makes local structure heavier, but that mass is still LOCAL, so
    # closure goes UP (fixed imports, more local mass). Weakness costs throughput, not
    # closure - the finding that keeps structures a parameter.
    f = _factory()
    baseline = compute_closure(f).closure_ratio
    heavier = closure_with_structural_penalty(900.0, 0.0, 100.0, k=2.0)
    assert heavier > baseline
    assert heavier == pytest.approx(1800.0 / 1900.0)
    # A realistic small penalty (k=1.08) barely moves closure - <1 point.
    realistic = closure_with_structural_penalty(900.0, 0.0, 100.0, k=40.0 / 37.0)
    assert abs(realistic - baseline) < 0.01


def test_hard_threshold_failure_is_what_actually_moves_closure():
    # If the structure can't meet a hard strength threshold it becomes an import, and
    # THAT collapses closure - the case that would justify a real module.
    if is_producible_locally(4.2, 40.0, hard_threshold=True):
        pytest.fail("weak material should fail a hard threshold")
    # Reclassify the 700 kg frame as a vitamin: closure drops from 0.9 to 0.2.
    f = Factory(
        name="threshold",
        subsystems=[
            Subsystem(name="frame", mass_kg=700.0, category="structure", producible_locally=False),
            Subsystem(name="tanks", mass_kg=200.0, category="structure"),
            Subsystem(name="chips", mass_kg=100.0, category="compute", producible_locally=False),
        ],
    )
    assert compute_closure(f).closure_ratio == pytest.approx(0.2)


def test_sintered_regolith_strength_spans_over_100x():
    # The sourced band (2.49 to 355 MPa) spans >100x - so strength must be a band, not a
    # point. The discrete techniques all fall inside that band.
    lo, hi = SINTERED_REGOLITH_STRENGTH_BAND_MPA
    assert hi / lo > 100.0  # 355 / 2.49 ~ 142x
    for strength in SINTERED_REGOLITH_STRENGTH_MPA.values():
        assert lo <= strength <= hi


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        mass_penalty_k(0.0, 37.0)
    with pytest.raises(ValueError):
        closure_with_structural_penalty(900.0, 0.0, 100.0, k=0.5)  # k < 1 is not a penalty
