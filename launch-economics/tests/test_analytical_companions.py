"""Analytical companions for launch-economics (issue #50, Phase 2 pilot).

The pilot Phase-2 derivation from `docs/FINDINGS_CLASSIFICATION.md` #21:
mass leverage tends to `1 / (1 - C)` in the small-seed limit.

## Derivation

Given a target installed mass M, a seed of mass s, and closure C, the mass
that must be built locally is `M - s`. Its vitamin requirement is
`(1 - C) * (M - s)` (each locally-built kilogram needs `1 - C` kg of imports).
Launched mass under the replication approach:

    L = s + (1 - C) * (M - s)
      = s * C + (1 - C) * M

Leverage:

    G(s, C) = M / L
           = 1 / (s*C/M + (1 - C))

The dimensionless small parameter is `eps := s / M`. Expanding around
`eps = 0` at fixed C < 1:

    G(0, C) = 1 / (1 - C)                      # the asymptote
    G(eps, C) = G(0, C) - eps * C / (1 - C)^2 + O(eps^2)

Two boundary cases:
- **C = 1:** G(s, 1) = M / s, unbounded as s / M -> 0.
- **C = 0:** G(s, 0) = 1 for all s <= M (launch everything).

## Test coverage
- Point value at multiple (s, C) pairs matches the closed form to `1e-9`
  relative (this checks the sim's arithmetic).
- The `1 / (1 - C)` limit is approached as `s / M -> 0`, monotonically.
- The C=0 and C=1 boundaries are handled correctly.
"""

from __future__ import annotations

import pytest

from closure_sim import Factory, Subsystem

from launch_economics import ReplicationLaunchComparison, comparison_from_closure


COST_PER_KG = 1_000.0  # arbitrary; cancels from leverage and cost_ratio


def _leverage_closed_form(target: float, seed: float, closure: float) -> float:
    """G(s, C) = M / (s*C + (1-C)*M)."""
    if not 0.0 < closure < 1.0:
        raise ValueError("this closed form applies to C in (0, 1)")
    return target / (seed * closure + (1.0 - closure) * target)


def _factory_at_closure(closure: float) -> Factory:
    """A minimal factory with exactly the requested mass closure."""
    total = 1000.0
    local = total * closure
    vit = total - local
    subs = []
    if local > 0:
        subs.append(Subsystem(name="local", mass_kg=local, category="structure",
                              producible_locally=True, energy_to_produce_kwh_per_kg=2.0))
    if vit > 0:
        subs.append(Subsystem(name="chips", mass_kg=vit, category="compute",
                              producible_locally=False, energy_to_produce_kwh_per_kg=1000.0))
    return Factory(name=f"c{closure}", subsystems=subs)


# ---------- Point-value agreement across (s, C) grid ----------

@pytest.mark.parametrize("closure", [0.1, 0.5, 0.9, 0.97])
@pytest.mark.parametrize("seed_over_target", [0.001, 0.01, 0.1, 0.5])
def test_leverage_matches_closed_form_at_point(closure, seed_over_target):
    target = 100_000.0
    seed = seed_over_target * target
    comparison = comparison_from_closure(
        _factory_at_closure(closure),
        target_installed_mass_kg=target, seed_mass_kg=seed, cost_per_kg_usd=COST_PER_KG,
    )
    expected = _leverage_closed_form(target, seed, closure)
    assert comparison.mass_leverage == pytest.approx(expected, rel=1e-9)


# ---------- Asymptotic 1/(1-C) approach as seed/target -> 0 ----------

@pytest.mark.parametrize("closure", [0.5, 0.9, 0.99])
def test_leverage_approaches_1_over_1_minus_C(closure):
    target = 100_000.0
    asymptote = 1.0 / (1.0 - closure)
    prev_error = None
    for seed_over_target in (0.1, 0.01, 0.001, 0.0001):
        seed = seed_over_target * target
        comparison = comparison_from_closure(
            _factory_at_closure(closure),
            target_installed_mass_kg=target, seed_mass_kg=seed, cost_per_kg_usd=COST_PER_KG,
        )
        error = abs(comparison.mass_leverage - asymptote)
        if prev_error is not None:
            assert error < prev_error, (
                f"error to asymptote should shrink monotonically; "
                f"seed/target ratio dropped and error went {prev_error} -> {error}"
            )
        prev_error = error


# ---------- Leading-order correction: G ~ 1/(1-C) - eps*C/(1-C)^2 ----------

def test_leading_order_correction():
    """Verify the O(eps) correction matches the derivation."""
    closure = 0.9
    target = 100_000.0
    seed = 100.0  # eps = 1e-3
    eps = seed / target
    predicted = 1.0 / (1.0 - closure) - eps * closure / (1.0 - closure) ** 2
    comparison = comparison_from_closure(
        _factory_at_closure(closure),
        target_installed_mass_kg=target, seed_mass_kg=seed, cost_per_kg_usd=COST_PER_KG,
    )
    # Leading + linear correction agrees with sim to O(eps^2 / (1-C)). For eps=1e-3
    # and C=0.9 this is ~8e-4, so we allow 1e-3.
    assert comparison.mass_leverage == pytest.approx(predicted, abs=1e-3)


# ---------- Boundary: closure = 0 collapses to leverage 1 (launch everything) ----------

def test_zero_closure_collapses_to_launch_everything():
    target = 100_000.0
    seed = 1_000.0  # any seed
    comparison = comparison_from_closure(
        _factory_at_closure(0.0),
        target_installed_mass_kg=target, seed_mass_kg=seed, cost_per_kg_usd=COST_PER_KG,
    )
    # At C=0, launched = seed + (target - seed) = target. Leverage exactly 1.
    assert comparison.mass_leverage == pytest.approx(1.0, rel=1e-12)


# ---------- Boundary: closure = 1 collapses to leverage = M / s ----------

def test_full_closure_leverage_is_target_over_seed():
    target = 100_000.0
    seed = 1_000.0
    comparison = comparison_from_closure(
        _factory_at_closure(1.0),
        target_installed_mass_kg=target, seed_mass_kg=seed, cost_per_kg_usd=COST_PER_KG,
    )
    assert comparison.mass_leverage == pytest.approx(target / seed, rel=1e-12)
    assert comparison.vitamin_mass_total_kg == pytest.approx(0.0, abs=1e-9)
