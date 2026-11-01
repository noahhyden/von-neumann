"""Analytical companion for the coordination-tax scaling (issue #50, Phase 2)."""

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
    # Predicted 1 + Λ = 1.1.
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
