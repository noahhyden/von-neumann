"""Tiny dense linear algebra for the implicit solver - pure Python, zero deps.

The stiff (implicit) integrator needs to solve a small linear system per Newton
iteration, `J x = b`, and to form `J` by finite differences. The systems here are
the size of the ODE state (scalar or a handful of components), so a dense
Gaussian elimination with partial pivoting is the right tool: correct, simple,
and no numpy dependency (vn-core is deliberately `dependencies = []`).

Keeping this here rather than reaching for numpy is a §7 call as much as a
dependency one: the fold must be deterministic, and hand-written elimination in
a fixed pivot order is trivially reproducible across machines.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence


def solve_linear(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve the dense system ``a x = b`` by Gaussian elimination w/ partial pivot.

    ``a`` is an n x n matrix (list of rows), ``b`` a length-n vector. Returns the
    solution ``x``. Raises ValueError if the matrix is singular to working
    precision. Operates on copies, so the inputs are not mutated.
    """
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


def numerical_jacobian(
    f: Callable[[float, Sequence[float]], Sequence[float]],
    t: float,
    y: Sequence[float],
    f0: Sequence[float],
) -> list[list[float]]:
    """Forward-difference Jacobian ``df_i/dy_j`` of the RHS at ``(t, y)``.

    ``f0 = f(t, y)`` is passed in so it is not recomputed. The perturbation is
    scaled per component, `h = sqrt(eps) * max(|y_j|, 1)`, the standard choice
    that balances truncation against round-off for a forward difference.
    """
    n = len(y)
    eps = 1.4901161193847656e-08  # sqrt(2.22e-16), the usual forward-diff step
    jac = [[0.0] * n for _ in range(n)]
    yj = list(y)
    for j in range(n):
        step = eps * max(abs(y[j]), 1.0)
        yj[j] = y[j] + step
        fj = f(t, yj)
        yj[j] = y[j]
        inv = 1.0 / step
        for i in range(n):
            jac[i][j] = (fj[i] - f0[i]) * inv
    return jac
