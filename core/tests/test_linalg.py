"""Validation for vn_core.linalg (shared dense solvers).

- ``solve_linear`` (square, Gaussian elimination) - the solver the implicit ODE
  integrator relies on. Verified against numpy and on hand-checkable systems.
- ``solve_lstsq`` (overdetermined, Householder QR) - the solver PCE regression relies
  on. Verified against numpy.linalg.lstsq, by residual orthogonality, and - the reason
  it exists - shown to be far more accurate than the normal equations on an
  ill-conditioned design (the normal equations square the condition number).

numpy is a dev-only oracle (it comes in via scipy); vn-core itself imports neither.
"""

from __future__ import annotations

import pytest

from vn_core.linalg import solve_least_squares, solve_linear, solve_lstsq


# --- solve_linear --------------------------------------------------------------


def test_solve_linear_known_system():
    # 2x + y = 5 ; x + 3y = 10  ->  x = 1, y = 3
    x = solve_linear([[2.0, 1.0], [1.0, 3.0]], [5.0, 10.0])
    assert x == pytest.approx([1.0, 3.0])


def test_solve_linear_upper_triangular_hits_zero_factor():
    # Below-pivot entries already zero -> the factor==0 fast path.
    x = solve_linear([[2.0, 1.0], [0.0, 3.0]], [4.0, 9.0])
    assert x == pytest.approx([0.5, 3.0])


def test_solve_linear_needs_row_swap():
    # Zero leading pivot forces a partial-pivot row swap.
    x = solve_linear([[0.0, 1.0], [1.0, 0.0]], [2.0, 3.0])
    assert x == pytest.approx([3.0, 2.0])


def test_solve_linear_matches_numpy():
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(1)
    for _ in range(20):
        a = rng.standard_normal((4, 4))
        b = rng.standard_normal(4)
        mine = solve_linear([list(r) for r in a], list(b))
        assert mine == pytest.approx(list(np.linalg.solve(a, b)), abs=1e-9)


def test_solve_linear_rejects_singular():
    with pytest.raises(ValueError, match="singular"):
        solve_linear([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])


def test_solve_linear_rejects_non_square():
    with pytest.raises(ValueError, match="square"):
        solve_linear([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], [1.0, 2.0])


def test_solve_linear_does_not_mutate_inputs():
    a = [[2.0, 1.0], [1.0, 3.0]]
    b = [5.0, 10.0]
    solve_linear(a, b)
    assert a == [[2.0, 1.0], [1.0, 3.0]]
    assert b == [5.0, 10.0]


# --- solve_lstsq ---------------------------------------------------------------


def test_lstsq_exact_on_consistent_overdetermined():
    # Points exactly on the line y = 2 + 3x -> LS recovers (2, 3) exactly.
    xs = [0.0, 1.0, 2.0, 3.0, 4.0]
    a = [[1.0, x] for x in xs]
    b = [2.0 + 3.0 * x for x in xs]
    coeffs = solve_lstsq(a, b)
    assert coeffs == pytest.approx([2.0, 3.0], abs=1e-12)


def test_lstsq_matches_numpy():
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(2)
    for _ in range(20):
        a = rng.standard_normal((7, 3))
        b = rng.standard_normal(7)
        mine = solve_lstsq([list(r) for r in a], list(b))
        ref, *_ = np.linalg.lstsq(a, b, rcond=None)
        assert mine == pytest.approx(list(ref), abs=1e-10)


def test_lstsq_residual_is_orthogonal_to_columns():
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(3)
    a = rng.standard_normal((10, 4))
    b = rng.standard_normal(10)
    x = np.array(solve_lstsq([list(r) for r in a], list(b)))
    resid = a @ x - b
    # Normal-equation optimality: A^T (Ax - b) = 0 at the LS solution.
    assert np.allclose(a.T @ resid, 0.0, atol=1e-10)


def test_lstsq_beats_normal_equations_on_ill_conditioned_design():
    """The reason QR is here: on a nearly-collinear design the normal equations lose
    ~half the digits; QR keeps them. This must be a wide, not marginal, margin."""
    np = pytest.importorskip("numpy")
    eps = 1e-7
    a = [[1.0, 1.0 + i * eps] for i in range(50)]
    x_true = [2.0, -3.0]
    b = [row[0] * x_true[0] + row[1] * x_true[1] for row in a]

    qr = np.array(solve_lstsq(a, b))
    am = np.array(a)
    gram = (am.T @ am).tolist()
    proj = list(am.T @ np.array(b))
    normal = np.array(solve_linear(gram, proj))

    qr_err = np.max(np.abs(qr - x_true))
    ne_err = np.max(np.abs(normal - x_true))
    assert qr_err < 1e-9
    assert qr_err < ne_err / 1000.0  # QR is orders of magnitude better


def test_lstsq_stable_householder_sign_on_large_leading_entry():
    """Pins the numerically-stable Householder sign/vector choice. A design with a
    huge leading entry makes the *unstable* sign (v[k] = x[k] +/- alpha with the wrong
    sign) cancel catastrophically and lose ~13 digits; the stable choice stays exact.
    This is what makes the reflection well-conditioned, not just correct in principle."""
    np = pytest.importorskip("numpy")
    a = [[1e8, 1.0], [1.0, 1.0], [1.0, 2.0], [1.0, 3.0]]
    x_true = [2.0, -3.0]
    b = [row[0] * x_true[0] + row[1] * x_true[1] for row in a]
    x = np.array(solve_lstsq(a, b))
    # The unstable sign choices land at ~5e-3 error here; the stable one is ~1e-15.
    assert np.max(np.abs(x - x_true)) < 1e-9


def test_lstsq_handles_negative_leading_pivot():
    # Exercises the Householder sign choice when the pivot is negative.
    a = [[-3.0, 1.0], [-1.0, 2.0], [-2.0, 0.5]]
    b = [1.0, 2.0, 3.0]
    x = solve_lstsq(a, b)
    # cross-check by residual optimality via numpy if available, else just runs
    np = pytest.importorskip("numpy")
    ref, *_ = np.linalg.lstsq(np.array(a), np.array(b), rcond=None)
    assert x == pytest.approx(list(ref), abs=1e-10)


def test_lstsq_square_system_is_exact_solve():
    """m == n is allowed (exactly determined): the LS solution is the exact solve."""
    a = [[2.0, 1.0], [1.0, 3.0]]
    b = [5.0, 10.0]
    assert solve_lstsq(a, b) == pytest.approx([1.0, 3.0], abs=1e-12)


def test_lstsq_long_form_alias():
    a = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    b = [1.0, 2.0, 3.0]
    assert solve_least_squares(a, b) == solve_lstsq(a, b)


def test_lstsq_rejects_empty():
    with pytest.raises(ValueError, match="at least one equation"):
        solve_lstsq([], [])


def test_lstsq_rejects_ragged_rows():
    with pytest.raises(ValueError, match="same length"):
        solve_lstsq([[1.0, 2.0], [3.0]], [1.0, 2.0])


def test_lstsq_rejects_b_length_mismatch():
    with pytest.raises(ValueError, match="must equal rows"):
        solve_lstsq([[1.0], [2.0]], [1.0, 2.0, 3.0])


def test_lstsq_rejects_underdetermined():
    with pytest.raises(ValueError, match="overdetermined"):
        solve_lstsq([[1.0, 2.0, 3.0]], [1.0])


def test_lstsq_rejects_rank_deficient_zero_column():
    # A column that is all zeros below the pivot -> norm_x == 0.
    with pytest.raises(ValueError, match="rank-deficient"):
        solve_lstsq([[0.0, 1.0], [0.0, 2.0]], [1.0, 2.0])


def test_lstsq_does_not_mutate_inputs():
    a = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    b = [1.0, 2.0, 3.0]
    a_copy = [row[:] for row in a]
    b_copy = b[:]
    solve_lstsq(a, b)
    assert a == a_copy
    assert b == b_copy
