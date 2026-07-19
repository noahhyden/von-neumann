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

from vn_core.uq.distributions import Distribution
from vn_core.uq.sample import MCResult, summarize


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


@dataclass(frozen=True)
class _SaltelliEvals:
    """The finding evaluations of one Saltelli design - the shared substrate.

    ``y_a``/``y_b`` are the finding on the two independent N x K uniform matrices
    (pushed through each input's inverse CDF); ``y_ab[name]`` is the finding on A
    with column ``name`` replaced by B's column. Total finding calls: N*(K+2),
    evaluated exactly once and read by both the GSA estimator and the free UQ.
    """

    names: tuple[str, ...]
    y_a: list[float]
    y_b: list[float]
    y_ab: dict[str, list[float]]
    n: int


def _saltelli_evaluate(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
) -> _SaltelliEvals:
    """Run one Saltelli design and return all N*(K+2) finding evaluations.

    The single model-evaluation path behind both ``sobol_total_order`` and
    ``uq_and_gsa`` - so asking for UQ alongside GSA costs zero extra evaluations.
    """
    if n < 2:
        raise ValueError(f"n must be >= 2, got {n}")
    names = tuple(inputs.keys())
    k = len(names)
    if k < 1:
        raise ValueError("a Saltelli design requires at least one input")

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

    y_ab: dict[str, list[float]] = {}
    for i, name in enumerate(names):
        # AB^(i): copy A, replace column i with B's column i.
        ab_rows = [row.copy() for row in a_u]
        for j in range(n):
            ab_rows[j][i] = b_u[j][i]
        y_ab[name] = [finding(push(row)) for row in ab_rows]

    return _SaltelliEvals(names=names, y_a=y_a, y_b=y_b, y_ab=y_ab, n=n)


def _sobol_from_evals(ev: _SaltelliEvals) -> SobolResult:
    """Jansen total-order indices from a Saltelli design's evaluations."""
    k = len(ev.names)
    # Union variance from A and B evaluations - 2N samples, tighter than either
    # alone. Guard against a degenerate constant finding (var == 0) which would
    # make every S_Ti trivially 0/0.
    combined = ev.y_a + ev.y_b
    var = statistics.pvariance(combined)
    n_eval = ev.n * (k + 2)
    if var == 0.0:
        # No variance in the output means no input contributes any - report zeros
        # rather than dividing by zero, so a truly deterministic finding is
        # honestly labelled as such.
        return SobolResult(
            total_order={name: 0.0 for name in ev.names},
            variance=0.0,
            mean=statistics.fmean(combined),
            n=ev.n,
            n_evaluations=n_eval,
        )

    total_order: dict[str, float] = {}
    for name in ev.names:
        y_ab = ev.y_ab[name]
        # Jansen total-order estimator.
        s = sum((ev.y_a[j] - y_ab[j]) ** 2 for j in range(ev.n))
        total_order[name] = s / (2.0 * ev.n * var)

    return SobolResult(
        total_order=total_order,
        variance=var,
        mean=statistics.fmean(combined),
        n=ev.n,
        n_evaluations=n_eval,
    )


def sobol_total_order(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
) -> SobolResult:
    """Rank inputs by total-order Sobol index.

    n is per-matrix; total finding evaluations = n * (K + 2) where K = len(inputs).
    If you also want the output distribution (error bars), call ``uq_and_gsa``
    instead - it returns both from this same design at no extra evaluations.
    """
    return _sobol_from_evals(_saltelli_evaluate(inputs, finding, n=n, seed=seed))


@dataclass(frozen=True)
class Analysis:
    """Both readouts of one Saltelli design: UQ (spread) and GSA (attribution).

    ``uq`` and ``gsa`` come from the *same* N*(K+2) finding evaluations, so
    getting the uncertainty alongside the sensitivity is free - the UQ is built
    from the 2N independent A+B samples the Sobol estimator already needs. By
    construction ``uq.mean == gsa.mean`` (both are the mean of those 2N samples).
    """

    uq: MCResult
    gsa: SobolResult


def uq_and_gsa(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
) -> Analysis:
    """Propagate uncertainty AND rank drivers from one Saltelli design.

    Runs the finding exactly N*(K+2) times (same as ``sobol_total_order`` alone)
    and reads two answers off it: the output distribution over the 2N independent
    A+B samples (UQ) and the total-order Sobol indices (GSA). This is strictly
    cheaper than a separate ``monte_carlo`` + ``sobol_total_order`` (which would
    re-evaluate the model M extra times), and the free UQ carries 2N samples.

    The A/B matrices are genuine iid draws of the joint input distribution (one
    uniform per independent input, pushed through its inverse CDF), so the UQ
    built from them is a standard Monte Carlo estimate - not an approximation.
    """
    ev = _saltelli_evaluate(inputs, finding, n=n, seed=seed)
    uq = summarize(ev.y_a + ev.y_b, ev.names)
    gsa = _sobol_from_evals(ev)
    return Analysis(uq=uq, gsa=gsa)
