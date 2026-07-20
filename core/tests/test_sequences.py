"""Validation gate for vn_core.uq.sequences (Halton + Sobol').

Layered like the rest of the suite:
- Pure-property tests (no scipy): van der Corput values, unit-cube containment,
  determinism, equidistribution, error branches, and QMC-beats-MC convergence.
- Oracle test (scipy, a dev-only dependency): the Sobol' points are asserted
  bit-identical to scipy.stats.qmc.Sobol, which carries the authoritative Joe-Kuo
  direction numbers. This is what pins the embedded table (CLAUDE.md §1) - a drift in
  either the table or the recurrence is a red test, not a silent bad sequence.
"""

from __future__ import annotations

import math

import pytest

from vn_core.uq.sequences import (
    MAX_HALTON_DIM,
    MAX_SOBOL_DIM,
    halton_point,
    radical_inverse,
    sobol_points,
)


# --- radical inverse / Halton ---------------------------------------------------


def test_radical_inverse_known_base2():
    # van der Corput base 2: 1->.5, 2->.25, 3->.75, 4->.125.
    assert radical_inverse(0, 2) == 0.0
    assert radical_inverse(1, 2) == 0.5
    assert radical_inverse(2, 2) == 0.25
    assert radical_inverse(3, 2) == 0.75
    assert radical_inverse(4, 2) == 0.125


def test_radical_inverse_known_base3():
    assert radical_inverse(1, 3) == pytest.approx(1 / 3)
    assert radical_inverse(2, 3) == pytest.approx(2 / 3)
    assert radical_inverse(3, 3) == pytest.approx(1 / 9)


def test_radical_inverse_rejects_bad_base():
    with pytest.raises(ValueError, match="base must be >= 2"):
        radical_inverse(5, 1)


def test_radical_inverse_rejects_negative_index():
    with pytest.raises(ValueError, match="index must be >= 0"):
        radical_inverse(-1, 2)


def test_halton_point_first_dim_is_van_der_corput():
    for i in range(1, 20):
        assert halton_point(i, 1)[0] == radical_inverse(i, 2)


def test_halton_point_uses_distinct_prime_bases():
    p = halton_point(1, 3)
    assert p == pytest.approx((1 / 2, 1 / 3, 1 / 5))


def test_halton_points_in_unit_cube():
    for i in range(50):
        for c in halton_point(i, 5):
            assert 0.0 <= c < 1.0


def test_halton_point_deterministic():
    assert halton_point(17, 4) == halton_point(17, 4)


def test_halton_point_rejects_bad_dim():
    with pytest.raises(ValueError, match="dim must be in"):
        halton_point(1, 0)
    with pytest.raises(ValueError, match="dim must be in"):
        halton_point(1, MAX_HALTON_DIM + 1)


def test_halton_point_rejects_negative_index():
    with pytest.raises(ValueError, match="index must be >= 0"):
        halton_point(-1, 2)


def test_halton_index_zero_is_origin():
    assert halton_point(0, 3) == (0.0, 0.0, 0.0)


# --- Sobol' pure properties -----------------------------------------------------


def test_sobol_first_point_is_origin():
    pts = sobol_points(4, 3)
    assert pts[0] == (0.0, 0.0, 0.0)


def test_sobol_first_dim_is_gray_code_radical_inverse():
    # Dimension 1 of Sobol' is the base-2 radical inverse in *gray-code* order (the
    # standard Sobol' construction), i.e. 0, 1/2, 3/4, 1/4, 3/8, ... - not the plain
    # van der Corput order. These are the exact dyadic rationals scipy produces.
    pts = sobol_points(8, 1)
    expected = [0.0, 0.5, 0.75, 0.25, 0.375, 0.875, 0.625, 0.125]
    assert [p[0] for p in pts] == expected


def test_sobol_points_in_unit_cube():
    for p in sobol_points(1024, MAX_SOBOL_DIM):
        for c in p:
            assert 0.0 <= c < 1.0


def test_sobol_deterministic():
    assert sobol_points(100, 5) == sobol_points(100, 5)


def test_sobol_count_and_shape():
    pts = sobol_points(37, 4)
    assert len(pts) == 37
    assert all(len(p) == 4 for p in pts)


def test_sobol_zero_points():
    assert sobol_points(0, 3) == []
    assert sobol_points(0, 3, skip=10) == []


def test_sobol_skip_is_a_tail_of_the_full_sequence():
    full = sobol_points(64, 3)
    tail = sobol_points(48, 3, skip=16)
    assert tail == full[16:]


def test_sobol_equidistribution_balanced_1d_projections():
    # A Sobol' (t,s)-sequence is balanced: the first 2^m points put exactly one point
    # in each of the 2^m equal sub-intervals of every 1-D projection.
    m = 6
    n = 1 << m
    pts = sobol_points(n, 5)
    for d in range(5):
        buckets = [0] * n
        for p in pts:
            buckets[min(int(p[d] * n), n - 1)] += 1
        assert all(b == 1 for b in buckets)


def test_sobol_beats_random_mc_on_smooth_integral():
    # Integrate a smooth product over [0,1]^3; true value is (something)^3. Sobol' at
    # N points should beat a crude pseudo-random Monte Carlo of the same N by a wide
    # margin (the whole reason to prefer a low-discrepancy sequence).
    def g(x):
        return math.prod(math.exp(xi) for xi in x)  # integral over [0,1]^d = (e-1)^d

    d = 3
    truth = (math.e - 1) ** d
    n = 2048
    qmc_est = sum(g(p) for p in sobol_points(n, d)) / n

    # Crude MC with a fixed LCG so the comparison is deterministic.
    state = 12345
    acc = 0.0
    for _ in range(n):
        xs = []
        for _ in range(d):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            xs.append(state / 0x7FFFFFFF)
        acc += g(xs)
    mc_est = acc / n

    qmc_err = abs(qmc_est - truth)
    mc_err = abs(mc_est - truth)
    assert qmc_err < mc_err
    assert qmc_err / truth < 1e-3  # Sobol' is genuinely close, not just better


# --- Sobol' error branches ------------------------------------------------------


def test_sobol_rejects_bad_dim():
    with pytest.raises(ValueError, match="dim must be in"):
        sobol_points(4, 0)
    with pytest.raises(ValueError, match="dim must be in"):
        sobol_points(4, MAX_SOBOL_DIM + 1)


def test_sobol_rejects_negative_n():
    with pytest.raises(ValueError, match="n must be >= 0"):
        sobol_points(-1, 2)


def test_sobol_rejects_negative_skip():
    with pytest.raises(ValueError, match="skip must be >= 0"):
        sobol_points(4, 2, skip=-1)


def test_sobol_rejects_over_capacity():
    with pytest.raises(ValueError, match="exceeds"):
        sobol_points(1, 2, skip=(1 << 30))


# --- Oracle: bit-identical to scipy's Joe-Kuo Sobol' ----------------------------


def test_sobol_matches_scipy_oracle():
    qmc = pytest.importorskip("scipy.stats.qmc", reason="scipy is the Sobol' oracle")
    for dim in (1, 2, 3, 5, 10, MAX_SOBOL_DIM):
        n = 1024
        mine = sobol_points(n, dim)
        ref = qmc.Sobol(d=dim, scramble=False).random(n)
        for i in range(n):
            for d in range(dim):
                assert mine[i][d] == pytest.approx(float(ref[i][d]), abs=1e-12)


def test_embedded_table_matches_scipy_direction_numbers():
    # The stronger pin: the embedded direction integers equal scipy's computed matrix
    # for every tabulated dimension - so the table itself (not just sampled points) is
    # verified against the authoritative source.
    pytest.importorskip("scipy.stats.qmc", reason="scipy carries the Joe-Kuo numbers")
    import numpy as np
    from scipy.stats import qmc

    from vn_core.uq import sequences as seq

    sv = qmc.Sobol(d=MAX_SOBOL_DIM, scramble=False)._sv
    # Dimension 1 (row 0) is the trivial column; dims 2..21 are the embedded table.
    for d in range(1, MAX_SOBOL_DIM):
        assert tuple(int(x) for x in sv[d]) == seq._SOBOL_V[d - 1]
