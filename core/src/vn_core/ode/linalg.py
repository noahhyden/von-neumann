"""ODE-specific linear-algebra helper: the finite-difference Jacobian of the RHS.

The dense square solver the implicit integrator needs (`J x = b` per Newton step)
now lives in the shared ``vn_core.linalg`` (alongside the least-squares solver PCE
uses), so there is one source of truth for dense elimination. What stays here is the
one piece that is genuinely about an ODE right-hand side: forming ``J`` by finite
differences of ``f(t, y)``.

Pure Python, zero deps, deterministic (§7): a fixed-order forward difference is
trivially reproducible across machines.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence


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
