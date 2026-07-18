"""Global sensitivity: Sobol total-order indices via Saltelli-style sampling.

The Monte Carlo in [[sample]] gives error bars; this module gives their attribution.
Total-order index S_Ti is the share of Var(finding) that would remain if input i
were free while all others were pinned - it captures i's direct effect plus every
interaction it participates in, and answers issue #35's headline question: **which
sourced input actually drives this finding?**

Estimator (Jansen 1999 / Saltelli et al. 2010):
  S_Ti = (1 / (2N)) * sum_j (f(A_j) - f(AB^(i)_j))^2  /  Var(f)
where A, B are two independent N x K matrices of uniforms in [0, 1) pushed through
each input's inverse CDF, and AB^(i) is A with column i replaced by B's column i.
Total evaluations: N * (K + 2). Cheap for probe-sim's analytic findings; still
sub-second for a few thousand samples of the bisection-over-closure-sim variant.

Determinism is by construction: one seeded RNG, uniform draws in a fixed order.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from probe_sim.uq.distributions import Distribution


@dataclass(frozen=True)
class SobolResult:
    """Total-order Sobol indices per input, plus context to sanity-check them."""

    total_order: dict[str, float]
    variance: float
    mean: float
    n: int
    n_evaluations: int

    def ranked(self) -> list[tuple[str, float]]:
        """Inputs sorted by decreasing total-order index."""
        return sorted(self.total_order.items(), key=lambda kv: -kv[1])


def sobol_total_order(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
) -> SobolResult:
    """Rank inputs by total-order Sobol index.

    n is per-matrix; total finding evaluations = n * (K + 2) where K = len(inputs).
    """
    if n < 2:
        raise ValueError(f"n must be >= 2, got {n}")
    names = tuple(inputs.keys())
    k = len(names)
    if k < 1:
        raise ValueError("sobol_total_order requires at least one input")

    rng = random.Random(seed)

    # Two independent uniform matrices A, B in [0, 1)^{n x k}. Fill in a fixed
    # (row, col) order so the RNG stream is deterministic and rearrangement of
    # `inputs` keys does not change results below the level of input identity.
    a_u = [[rng.random() for _ in range(k)] for _ in range(n)]
    b_u = [[rng.random() for _ in range(k)] for _ in range(n)]

    def push(u_row: list[float]) -> dict[str, float]:
        return {name: inputs[name].quantile(u) for name, u in zip(names, u_row)}

    y_a = [finding(push(row)) for row in a_u]
    y_b = [finding(push(row)) for row in b_u]

    # Union variance from A and B evaluations - 2N samples, tighter than either
    # alone. Guard against a degenerate constant finding (var == 0) which would
    # make every S_Ti trivially 0/0.
    combined = y_a + y_b
    var = statistics.pvariance(combined)
    if var == 0.0:
        # No variance in the output means no input contributes any - report zeros
        # rather than dividing by zero, so a truly deterministic finding is
        # honestly labelled as such.
        return SobolResult(
            total_order={name: 0.0 for name in names},
            variance=0.0,
            mean=statistics.fmean(combined),
            n=n,
            n_evaluations=n * (k + 2),
        )

    total_order: dict[str, float] = {}
    for i, name in enumerate(names):
        # AB^(i): copy A, replace column i with B's column i.
        ab_rows = [row.copy() for row in a_u]
        for j in range(n):
            ab_rows[j][i] = b_u[j][i]
        y_ab = [finding(push(row)) for row in ab_rows]
        # Jansen total-order estimator.
        s = sum((y_a[j] - y_ab[j]) ** 2 for j in range(n))
        total_order[name] = s / (2.0 * n * var)

    return SobolResult(
        total_order=total_order,
        variance=var,
        mean=statistics.fmean(combined),
        n=n,
        n_evaluations=n * (k + 2),
    )
