"""Analytical companion for the coordination-tax scaling (issue #50, Phase 2).

Formalizes finding #6: the lightspeed-vs-instant fuel tax scales as
`waste_ls / waste_inst = 1 + Λ` where `Λ = v_probe / c`.

## Derivation

Consider one hop of length d and speed v launched at time `t_0` toward a star
whose local settlement rate (density of competing arrivals per unit time in
its neighborhood) is `rho`.

**Instant regime.** The probe sees the true settled set at every moment. The
window during which a competitor can claim the target before this probe
arrives is the travel time itself:

    Δt_inst = d / v                               (1)

Expected wasted arrivals (the probe's target getting claimed while it flies)
scale as `rho * Δt_inst = rho * d / v`.

**Lightspeed regime.** The probe also sees stale information: at launch,
recent settlements within `d/c` of the target have not yet been observed.
The exposure window widens by the light-lag:

    Δt_ls  = d/v + d/c                            (2)

**Ratio.** Since `rho`, `d`, and the collision geometry are identical
between the two runs (they are a paired ensemble, same seed, same field),
the expected-waste ratio is

    E[waste_ls] / E[waste_inst] = (d/v + d/c) / (d/v)
                                = 1 + v/c
                                = 1 + Λ                                 (3)

**Structural consequences.** The `d` factor cancels, so the ratio is
**hop-length-independent**. The `rho` factor cancels, so the ratio is
**density-independent**. These cancellations are the whole reason the tax
comes out as a clean function of the dimensionless `Λ` and nothing else.
Documented and validated at 512 seeds in `swarm/REFERENCES.md`; measured
ratios `1.010 / 1.051 / 1.099 / 1.199` match predicted `1.010 / 1.050 /
1.100 / 1.200` at `Λ = 0.01 / 0.05 / 0.1 / 0.2`.

## Test coverage

This test is a **fast smoke check** that a small-N run reproduces the ratio
at a couple of Λ values within a wide tolerance appropriate to the small
seed count. It is not the finding itself - that lives in the paired 512-seed
sweep. What this test guards against is a code change silently breaking the
`1 + Λ` relation.
"""

import math

import pytest

from swarm import SwarmParams, simulate_swarm


def _paired_ratio(lambda_v: float, n_stars: int, seeds: list[int]) -> float:
    """Mean(waste_ls) / mean(waste_inst) over the given seed set. Powered, event stepping."""
    common = dict(
        n_stars=n_stars, probe_speed_c=lambda_v, policy="powered",
        stepping="event", offspring_per_settlement=2,
    )
    inst_waste = []
    ls_waste = []
    for seed in seeds:
        i = simulate_swarm(SwarmParams(**common, coordination="instant"), seed=seed)
        l = simulate_swarm(SwarmParams(**common, coordination="lightspeed"), seed=seed)
        inst_waste.append(i.wasted_arrivals)
        ls_waste.append(l.wasted_arrivals)
    mean_inst = sum(inst_waste) / len(inst_waste)
    if mean_inst <= 0:
        return math.nan
    return sum(ls_waste) / len(ls_waste) / mean_inst


def test_ratio_matches_one_plus_lambda_at_moderate_lambda():
    """At Λ = 0.1 the ratio should be near 1.1. Wide tolerance for small N and few seeds."""
    seeds = list(range(16))
    lambda_v = 0.1
    ratio = _paired_ratio(lambda_v, n_stars=200, seeds=seeds)
    # Predicted 1 + Λ = 1.1. Small-N spread easily 20-30%; a 1.5x window guards against
    # regressions without failing on Monte Carlo noise.
    assert 1.0 <= ratio <= 1.5, f"ratio={ratio} out of [1.0, 1.5]; predicted ~1.1"


def test_ratio_grows_with_lambda():
    """The ratio is monotone in Λ (up to seed noise): compare Λ=0.05 to Λ=0.2."""
    seeds = list(range(16))
    r_low = _paired_ratio(0.05, n_stars=200, seeds=seeds)
    r_high = _paired_ratio(0.2, n_stars=200, seeds=seeds)
    assert r_high > r_low, (
        f"expected ratio(Λ=0.2)={r_high} > ratio(Λ=0.05)={r_low}"
    )


def test_ratio_is_deterministic():
    """Same seeds reproduce the ratio bit-for-bit."""
    seeds = list(range(8))
    a = _paired_ratio(0.1, n_stars=150, seeds=seeds)
    b = _paired_ratio(0.1, n_stars=150, seeds=seeds)
    assert a == b
