"""Tiny dense linear algebra - pure Python, zero deps, shared across the repo."""

from __future__ import annotations

import math


def solve_linear(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve the dense system ``a x = b`` by Gaussian elimination w/ partial pivot."""
    n = len(b)
    if any(len(row) != n for row in a) or len(a) != n:
        raise ValueError("a must be square and match len(b)")
    # Work on an augmented copy so callers' data is untouched.
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        # Partial pivot: pick the row with the largest magnitude in this column.
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-300:
            raise ValueError("matrix is singular to working precision")
        if pivot != col:
            m[col], m[pivot] = m[pivot], m[col]
        inv = 1.0 / m[col][col]
        for r in range(col + 1, n):
            factor = m[r][col] * inv
            if factor == 0.0:
                continue
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]
    # Back-substitution.
    x = [0.0] * n
    for row in range(n - 1, -1, -1):
        acc = m[row][n]
        for c in range(row + 1, n):
            acc -= m[row][c] * x[c]
        x[row] = acc / m[row][row]
    return x


def solve_lstsq(a: list[list[float]], b: list[float]) -> list[float]:
    """Least-squares solution of the overdetermined system ``a x ~= b`` by Householder QR."""
    m = len(a)
    if m == 0:
        raise ValueError("solve_lstsq needs at least one equation")
    n = len(a[0])
    if any(len(row) != n for row in a):
        raise ValueError("solve_lstsq: all rows of a must have the same length")
    if len(b) != m:
        raise ValueError(f"solve_lstsq: len(b)={len(b)} must equal rows(a)={m}")
    if m < n:
        raise ValueError(f"solve_lstsq is overdetermined: rows(a)={m} < cols(a)={n}")

    r = [list(row) for row in a]  # m x n working copy, becomes R in its top n rows
    qtb = list(b)  # becomes Q^T b
    for k in range(n):
        # Householder vector zeroing column k below the diagonal.
        norm_x = math.sqrt(sum(r[i][k] * r[i][k] for i in range(k, m)))
        if norm_x == 0.0:
            raise ValueError("solve_lstsq: rank-deficient design (zero column under pivot)")
        # Choose the sign that avoids cancellation in v[k].
        alpha = -norm_x if r[k][k] >= 0 else norm_x
        v = [0.0] * m
        v[k] = r[k][k] - alpha
        for i in range(k + 1, m):
            v[i] = r[i][k]
        vnorm2 = sum(v[i] * v[i] for i in range(k, m))
        if vnorm2 == 0.0:  # pragma: no cover - norm_x != 0 guarantees v != 0
            continue
        # Apply H = I - 2 v v^T / vnorm2 to the trailing columns of R and to Q^T b.
        for j in range(k, n):
            dot = sum(v[i] * r[i][j] for i in range(k, m))
            factor = 2.0 * dot / vnorm2
            for i in range(k, m):
                r[i][j] -= factor * v[i]
        dotb = sum(v[i] * qtb[i] for i in range(k, m))
        fb = 2.0 * dotb / vnorm2
        for i in range(k, m):
            qtb[i] -= fb * v[i]

    # Back-substitute the upper-triangular n x n system R x = (Q^T b)[:n].
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        if r[i][i] == 0.0:  # pragma: no cover - unreachable: R[i][i] was set to alpha
            # Unreachable: R[i][i] was set to alpha with norm_x > 0 as its magnitude and is never modified by later steps.
            raise ValueError("solve_lstsq: rank-deficient design (zero pivot in R)")
        acc = qtb[i]
        for j in range(i + 1, n):
            acc -= r[i][j] * x[j]
        x[i] = acc / r[i][i]
    return x


__all__ = ["solve_least_squares", "solve_linear", "solve_lstsq"]

# Long-form alias for call sites that prefer it.
solve_least_squares = solve_lstsq
