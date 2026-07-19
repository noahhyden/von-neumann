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

import math
import random
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from vn_core.uq.distributions import Distribution
from vn_core.uq.sample import MCResult, summarize


@dataclass(frozen=True)
class SobolResult:
    """Sobol indices per input, with confidence intervals to sanity-check them.

    ``total_order`` is the share of variance an input drives directly plus through
    every interaction; ``first_order`` is its direct (main) effect alone. The gap
    ``total_order[i] - first_order[i]`` is how much of i's influence is *interaction*
    - the thing a first-order-only analysis misses (see Ishigami's x3).

    Both carry a 90% confidence interval (``*_ci``, a (low, high) per input). The
    estimators are noisy, so an index reported without a CI can read as resolved
    when it is within sampling noise - the CI is the honest counterpart, the same
    "a spread is a citable claim" discipline the UQ error bars hold. ``ci_method``
    is "asymptotic" (default, from the estimator's standard error - free), or
    "bootstrap" (resampling, opt-in and costlier), or "none" (var == 0).
    """

    total_order: dict[str, float]
    first_order: dict[str, float]
    total_order_ci: dict[str, tuple[float, float]]
    first_order_ci: dict[str, tuple[float, float]]
    variance: float
    mean: float
    n: int
    n_evaluations: int
    ci_method: str

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


# 90% two-sided normal quantile (z_0.95), for the asymptotic CI half-width.
_Z90 = 1.6448536269514722


def _asymptotic_ci(
    rows_by_name: dict[str, list[float]], center: dict[str, float], n: int
) -> dict[str, tuple[float, float]]:
    """90% CI from the estimator's own standard error (each index is a mean of rows).

    stderr = pstdev(per-row terms)/sqrt(N); CI = estimate +- z_0.95 * stderr. O(N),
    so it is effectively free - and matches the bootstrap CI to 2-3 decimals on the
    Ishigami benchmark. Approximate (treats var as fixed, assumes near-normal), the
    documented trade for being cheap enough to always compute.
    """
    out: dict[str, tuple[float, float]] = {}
    for name, rows in rows_by_name.items():
        se = statistics.pstdev(rows) / math.sqrt(n) if n >= 2 else 0.0
        half = _Z90 * se
        out[name] = (center[name] - half, center[name] + half)
    return out


def _bootstrap_ci(
    ev: _SaltelliEvals, mean: float, n_boot: int, seed: int
) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    """90% percentile CIs by resampling the N design rows with replacement.

    More robust than the asymptotic CI (no normality/fixed-var assumption) but O(N
    * n_boot) with no new model evaluations - opt-in because that is slow at large
    N (measured ~4 s at N=8000, n_boot=500). Uses its own RNG stream, so the point
    estimates stay byte-identical. Var and the first-order mean are re-estimated per
    resample (the first-order estimator is centered - see _sobol_from_evals).
    """
    rng = random.Random(seed)
    n = ev.n
    t_num = {nm: [(ev.y_a[j] - ev.y_ab[nm][j]) ** 2 for j in range(n)] for nm in ev.names}
    fb = {nm: [ev.y_b[j] * (ev.y_ab[nm][j] - ev.y_a[j]) for j in range(n)] for nm in ev.names}
    diff = {nm: [ev.y_ab[nm][j] - ev.y_a[j] for j in range(n)] for nm in ev.names}
    boot_total = {nm: [] for nm in ev.names}
    boot_first = {nm: [] for nm in ev.names}
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        comb = [ev.y_a[j] for j in idx] + [ev.y_b[j] for j in idx]
        var_b = statistics.pvariance(comb)
        if var_b == 0.0:
            continue
        mean_b = statistics.fmean(comb)
        for nm in ev.names:
            boot_total[nm].append(sum(t_num[nm][j] for j in idx) / (2.0 * n * var_b))
            # Centered first-order: sum (y_b - mean_b)(y_ab - y_a) = sum fb - mean_b sum diff.
            first_num = sum(fb[nm][j] for j in idx) - mean_b * sum(diff[nm][j] for j in idx)
            boot_first[nm].append(first_num / (n * var_b))

    def ci(vals: list[float]) -> tuple[float, float]:
        if not vals:
            return (0.0, 0.0)
        s = sorted(vals)
        lo = s[int(0.05 * (len(s) - 1))]
        hi = s[int(math.ceil(0.95 * (len(s) - 1)))]
        return (lo, hi)

    return (
        {nm: ci(boot_total[nm]) for nm in ev.names},
        {nm: ci(boot_first[nm]) for nm in ev.names},
    )


def _sobol_from_evals(
    ev: _SaltelliEvals, *, bootstrap: int = 0, seed: int = 0
) -> SobolResult:
    """First- and total-order Sobol indices (with CIs) from a Saltelli design."""
    k = len(ev.names)
    # Union variance from A and B evaluations - 2N samples, tighter than either
    # alone. Guard against a degenerate constant finding (var == 0) which would
    # make every index trivially 0/0.
    combined = ev.y_a + ev.y_b
    var = statistics.pvariance(combined)
    n_eval = ev.n * (k + 2)
    mean = statistics.fmean(combined)
    if var == 0.0:
        # No variance in the output means no input contributes any - report zeros
        # rather than dividing by zero, so a truly deterministic finding is
        # honestly labelled as such.
        zeros = {name: 0.0 for name in ev.names}
        zero_ci = {name: (0.0, 0.0) for name in ev.names}
        return SobolResult(
            total_order=dict(zeros), first_order=dict(zeros),
            total_order_ci=dict(zero_ci), first_order_ci=dict(zero_ci),
            variance=0.0, mean=mean, n=ev.n, n_evaluations=n_eval, ci_method="none",
        )

    n = ev.n
    total_order: dict[str, float] = {}
    first_order: dict[str, float] = {}
    total_rows: dict[str, list[float]] = {}
    first_rows: dict[str, list[float]] = {}
    for name in ev.names:
        y_ab = ev.y_ab[name]
        # Jansen total-order estimator (arithmetic kept exactly as before - the
        # point estimate must stay byte-identical to the pre-CI implementation).
        s = sum((ev.y_a[j] - y_ab[j]) ** 2 for j in range(n))
        total_order[name] = s / (2.0 * n * var)
        # Saltelli-2010 first-order estimator, CENTERED: subtract the output mean
        # from y_B. Without it the estimator carries the full output mean and, when
        # the mean is large relative to the spread (low coefficient of variation),
        # catastrophic cancellation makes it wildly noisy - it read 2.459 (and 0.384
        # at N=6000) on a real finding with mean/std ~ 52, where the true value is
        # ~1. Centering fixes it; total-order is immune (it uses differences).
        s_f = sum((ev.y_b[j] - mean) * (y_ab[j] - ev.y_a[j]) for j in range(n))
        first_order[name] = s_f / (n * var)
        total_rows[name] = [(ev.y_a[j] - y_ab[j]) ** 2 / (2.0 * var) for j in range(n)]
        first_rows[name] = [(ev.y_b[j] - mean) * (y_ab[j] - ev.y_a[j]) / var for j in range(n)]

    if bootstrap > 0:
        total_ci, first_ci = _bootstrap_ci(ev, mean, bootstrap, seed)
        ci_method = "bootstrap"
    else:
        total_ci = _asymptotic_ci(total_rows, total_order, n)
        first_ci = _asymptotic_ci(first_rows, first_order, n)
        ci_method = "asymptotic"

    return SobolResult(
        total_order=total_order,
        first_order=first_order,
        total_order_ci=total_ci,
        first_order_ci=first_ci,
        variance=var,
        mean=mean,
        n=ev.n,
        n_evaluations=n_eval,
        ci_method=ci_method,
    )


def sobol_total_order(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
    bootstrap: int = 0,
) -> SobolResult:
    """First- and total-order Sobol indices, each with a 90% confidence interval.

    n is per-matrix; total finding evaluations = n * (K + 2) where K = len(inputs).
    First-order indices are free (they reuse the same evaluations as total-order).
    CIs are asymptotic (standard-error) by default - cheap enough to always compute;
    pass ``bootstrap=B`` (e.g. 500) for percentile CIs by resampling instead, which
    adds no model evaluations but is O(N*B) arithmetic (slow at large N).

    If you also want the output distribution (error bars), call ``uq_and_gsa``
    instead - it returns both from this same design at no extra evaluations.
    """
    ev = _saltelli_evaluate(inputs, finding, n=n, seed=seed)
    return _sobol_from_evals(ev, bootstrap=bootstrap, seed=seed)


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
    bootstrap: int = 0,
) -> Analysis:
    """Propagate uncertainty AND rank drivers from one Saltelli design.

    Runs the finding exactly N*(K+2) times (same as ``sobol_total_order`` alone)
    and reads two answers off it: the output distribution over the 2N independent
    A+B samples (UQ) and the first-/total-order Sobol indices with CIs (GSA). This
    is strictly cheaper than a separate ``monte_carlo`` + ``sobol_total_order``
    (which would re-evaluate the model M extra times), and the free UQ carries 2N
    samples. ``bootstrap`` is forwarded to the GSA CIs (see ``sobol_total_order``).

    The A/B matrices are genuine iid draws of the joint input distribution (one
    uniform per independent input, pushed through its inverse CDF), so the UQ
    built from them is a standard Monte Carlo estimate - not an approximation.
    """
    ev = _saltelli_evaluate(inputs, finding, n=n, seed=seed)
    uq = summarize(ev.y_a + ev.y_b, ev.names)
    gsa = _sobol_from_evals(ev, bootstrap=bootstrap, seed=seed)
    return Analysis(uq=uq, gsa=gsa)
