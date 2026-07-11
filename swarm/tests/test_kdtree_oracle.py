"""Differential oracle: the k-d tree query must equal the brute-force linear scan, exactly.

Issue #30 replaced the flat cell list with a k-d tree branch-and-bound over the unsettled set,
including the subtle news-in-transit handling for the light-delayed regimes. The whole change is
worthless unless the tree returns the SAME star as the O(N) linear scan for every query - that is
what keeps the fold bit-identical (the pinned-baseline and JSON drift-guard tests then hold by
construction). Here we hammer the two query functions directly against a naive reference across
many randomized states, so a divergence shows up as an isolated query, not a whole-run digest.

The reference IS the pre-#30 scan: nearest *believed*-unsettled star by (distance, lowest index),
using the exact same ``_believes_settled_at`` gate the tree uses on the stars it examines. We vary:
field size across the leaf-bucket boundary, settled fraction, ``state.year`` relative to the settle
times (so beacon-in-transit stars are common under lightspeed), observer points, exclude sets, k,
and coordination mode - the regimes where a wrong prune would surface.
"""

from __future__ import annotations

import pytest

from swarm import SwarmParams
from swarm.models import Coordination
from swarm.rng import next_float, seed_state
from swarm.sim import (
    _believes_settled_at,
    _kd_mark_settled,
    _nearest_k_unsettled_at,
    _nearest_unsettled_at,
    initial_state,
)


def _brute_nearest(s, px, py, pz, year, coord, exclude):
    """Reference: nearest believed-unsettled star by (distance, lowest index) - the pre-#30 scan."""
    best = None
    best_d2 = float("inf")
    for i in range(len(s.xs)):
        if i in exclude or _believes_settled_at(s, px, py, pz, i, year, coord):
            continue
        dx = s.xs[i] - px
        dy = s.ys[i] - py
        dz = s.zs[i] - pz
        d2 = dx * dx + dy * dy + dz * dz
        if d2 < best_d2 or (d2 == best_d2 and best is not None and i < best):
            best_d2 = d2
            best = i
    return best


def _brute_k(s, px, py, pz, year, coord, k, exclude):
    """Reference: the k nearest believed-unsettled stars, sorted by (distance, index)."""
    cands = []
    for i in range(len(s.xs)):
        if i in exclude or _believes_settled_at(s, px, py, pz, i, year, coord):
            continue
        dx = s.xs[i] - px
        dy = s.ys[i] - py
        dz = s.zs[i] - pz
        cands.append((dx * dx + dy * dy + dz * dz, i))
    cands.sort()
    return [i for _, i in cands[:k]]


def _settle_random(s, rng, frac, max_year):
    """Settle a random ~frac of the stars at random years in [0, max_year], keeping the tree exact.

    Uses the real ``_kd_mark_settled`` so the subtree aggregates (kd_nuns/kd_tsmax) stay consistent -
    the same update the fold runs at each settlement. Origin is already settled by initial_state.
    """
    for i in range(len(s.xs)):
        if s.settled_year[i] >= 0.0:
            continue
        u, rng = next_float(rng)
        if u < frac:
            v, rng = next_float(rng)
            s.settled_year[i] = v * max_year
            _kd_mark_settled(s, i)
    return rng


COORDS: tuple[Coordination, ...] = ("instant", "lightspeed", "inflight")


@pytest.mark.parametrize("n", [1, 2, 7, 8, 9, 17, 64, 200, 501])
@pytest.mark.parametrize("frac", [0.0, 0.4, 0.85, 1.0])
def test_nearest_matches_brute_force(n: int, frac: float) -> None:
    # n straddles the leaf-bucket size (8): single-leaf trees, exact-boundary, and deep trees.
    if n <= 1 and frac >= 1.0:
        pytest.skip("a 1-star field is the origin only; nothing to query")
    s = initial_state(SwarmParams(n_stars=max(2, n)), seed=1234 + n)
    rng = seed_state(9876 + n + int(frac * 1000))
    # A box scale to place observers and a year range spanning the settle times, so beacons are
    # in various states of transit (the light-delayed correctness regime).
    L = s.box_side_pc
    rng = _settle_random(s, rng, frac, max_year=5.0)
    for trial in range(12):
        # Pick a year that can be below some settle times (heavy beacon-in-transit) or above all.
        yv, rng = next_float(rng)
        s.year = yv * 8.0
        # Observer: sometimes a random point, sometimes exactly at a star (a real decision site).
        pick, rng = next_float(rng)
        if pick < 0.5:
            ax, rng = next_float(rng)
            ay, rng = next_float(rng)
            az, rng = next_float(rng)
            px, py, pz = ax * L, ay * L, az * L
        else:
            si, rng = next_float(rng)
            j = int(si * len(s.xs)) % len(s.xs)
            px, py, pz = s.xs[j], s.ys[j], s.zs[j]
        # A small random exclude set.
        exclude: set[int] = set()
        ne, rng = next_float(rng)
        for _ in range(int(ne * 4)):
            ei, rng = next_float(rng)
            exclude.add(int(ei * len(s.xs)) % len(s.xs))
        for coord in COORDS:
            got = _nearest_unsettled_at(s, px, py, pz, s.year, coord, exclude)
            want = _brute_nearest(s, px, py, pz, s.year, coord, exclude)
            assert got == want, f"nearest n={n} frac={frac} trial={trial} coord={coord}: {got} != {want}"


@pytest.mark.parametrize("n", [2, 8, 9, 40, 200])
@pytest.mark.parametrize("frac", [0.0, 0.5, 0.9])
@pytest.mark.parametrize("k", [1, 3, 30])
def test_k_nearest_matches_brute_force(n: int, frac: float, k: int) -> None:
    s = initial_state(SwarmParams(n_stars=n), seed=555 + n)
    rng = seed_state(222 + n + k + int(frac * 100))
    L = s.box_side_pc
    rng = _settle_random(s, rng, frac, max_year=5.0)
    for trial in range(10):
        yv, rng = next_float(rng)
        s.year = yv * 8.0
        ax, rng = next_float(rng)
        ay, rng = next_float(rng)
        az, rng = next_float(rng)
        px, py, pz = ax * L, ay * L, az * L
        exclude: set[int] = set()
        ne, rng = next_float(rng)
        for _ in range(int(ne * 3)):
            ei, rng = next_float(rng)
            exclude.add(int(ei * len(s.xs)) % len(s.xs))
        for coord in COORDS:
            got = _nearest_k_unsettled_at(s, px, py, pz, s.year, coord, k, exclude)
            want = _brute_k(s, px, py, pz, s.year, coord, k, exclude)
            assert got == want, f"k-nearest n={n} k={k} frac={frac} trial={trial} coord={coord}: {got} != {want}"


def test_beacon_in_transit_star_is_returned_not_pruned() -> None:
    # The correctness crux (issue #30): under a light-delayed regime a recently-settled star whose
    # beacon has NOT reached the observer is believed-unsettled and must be a valid target - the tree
    # must NOT prune it away as "settled". Construct a case where the nearest star is exactly such a
    # star and confirm the tree returns it (and the brute-force agrees).
    s = initial_state(SwarmParams(n_stars=300), seed=42)
    # Settle every star except the origin, all at year 0 (long-ago core) ...
    rng = seed_state(7)
    for i in range(len(s.xs)):
        if s.settled_year[i] < 0.0:
            s.settled_year[i] = 0.0
            _kd_mark_settled(s, i)
    # ... then pick an observer and its true nearest star, and re-settle that nearest star "just now"
    # at a year whose beacon cannot yet have reached the observer. It is then believed-unsettled.
    px, py, pz = s.box_side_pc / 2.0, s.box_side_pc / 2.0, s.box_side_pc / 2.0
    nearest = min(
        range(len(s.xs)),
        key=lambda i: ((s.xs[i] - px) ** 2 + (s.ys[i] - py) ** 2 + (s.zs[i] - pz) ** 2, i),
    )
    d = ((s.xs[nearest] - px) ** 2 + (s.ys[nearest] - py) ** 2 + (s.zs[nearest] - pz) ** 2) ** 0.5
    # Its beacon must still be in transit at the query year: settled_year + d/c > year.
    from swarm.models import C_PC_PER_YEAR
    s.settled_year[nearest] = 100.0
    _kd_mark_settled(s, nearest)
    s.year = 100.0 + (d / C_PC_PER_YEAR) * 0.5  # halfway through the light-travel time
    assert _believes_settled_at(s, px, py, pz, nearest, s.year, "lightspeed") is False
    got = _nearest_unsettled_at(s, px, py, pz, s.year, "lightspeed", set())
    assert got == nearest  # the tree returns the beacon-in-transit star, not a farther one
    assert got == _brute_nearest(s, px, py, pz, s.year, "lightspeed", set())


def test_all_settled_and_arrived_returns_none() -> None:
    # Every star settled long ago: under instant nothing is believed-unsettled, and under lightspeed
    # once every beacon has had time to arrive the answer is also None. The tree must prune to empty.
    s = initial_state(SwarmParams(n_stars=120), seed=3)
    for i in range(len(s.xs)):
        if s.settled_year[i] < 0.0:
            s.settled_year[i] = 0.0
            _kd_mark_settled(s, i)
    s.year = 1e9  # far past every beacon's arrival everywhere in the box
    px, py, pz = s.xs[0], s.ys[0], s.zs[0]
    for coord in COORDS:
        assert _nearest_unsettled_at(s, px, py, pz, s.year, coord, set()) is None
        assert _nearest_k_unsettled_at(s, px, py, pz, s.year, coord, 5, set()) == []
