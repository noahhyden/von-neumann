"""Tiny, dependency-free, seeded statistics for the paired coordination ensemble.

The paper reports uncertainty on its headline penalties, and the paired A/B design
(same seed with and without the light-speed gate) makes that cheap. Two assumption-light
tools, both pure and deterministic (CLAUDE.md 1, 7):

- ``sign_test_positive`` - the fraction of seeds whose penalty is positive, with the
  exact sign-test p-value (P[X >= k] under Binomial(n, 1/2), two-sided). "The lag slowed
  every one of the 32 galaxies" is a stronger, more transparent claim than any normal
  approximation, and needs no distributional assumption.
- ``bootstrap_median_ci`` - a percentile bootstrap 95% confidence interval on the median
  penalty. Resampling uses the repo's own seeded mulberry32 (swarm.rng), so the interval
  is bit-reproducible run to run - no ``random`` module, no wall clock.

These operate on the per-seed penalty lists the experiment already produces; they add no
physical numbers of their own.
"""

from __future__ import annotations

import statistics
from math import comb

from swarm.rng import next_u32, seed_state


def sign_test_positive(xs: list[float]) -> tuple[int, int, float]:
    """(#positive, #nonzero, two-sided sign-test p) for penalties tested against 0.

    Ties (exactly-zero penalties, e.g. the powered policy) are dropped, as the sign test
    requires. With ``k`` of ``n`` nonzero penalties positive, the two-sided p-value is
    ``2 * sum_{i>=max(k, n-k)} C(n,i) / 2^n`` (clamped to 1). n == 0 -> p = 1.0.
    """
    nonzero = [x for x in xs if x != 0.0]
    n = len(nonzero)
    k = sum(1 for x in nonzero if x > 0.0)
    if n == 0:
        return 0, 0, 1.0
    hi = max(k, n - k)
    tail = sum(comb(n, i) for i in range(hi, n + 1))
    p = min(1.0, 2.0 * tail / (2.0**n))
    return k, n, p


def bootstrap_median_ci(
    xs: list[float], *, n_resamples: int = 2000, seed: int = 0x5EED1234
) -> tuple[float, float, float]:
    """Percentile bootstrap (median, lo95, hi95) for the median of ``xs``.

    Deterministic: draws resample indices from the seeded mulberry32 stream, so the CI is
    reproducible. Returns the point median plus the 2.5th and 97.5th percentiles of the
    resampled medians. An empty input returns zeros.
    """
    if not xs:
        return 0.0, 0.0, 0.0
    n = len(xs)
    rng = seed_state(seed)
    medians: list[float] = []
    for _ in range(n_resamples):
        sample: list[float] = []
        for _ in range(n):
            u, rng = next_u32(rng)
            sample.append(xs[u % n])
        medians.append(statistics.median(sample))
    medians.sort()
    lo = medians[int(0.025 * n_resamples)]
    hi = medians[min(n_resamples - 1, int(0.975 * n_resamples))]
    return statistics.median(xs), lo, hi


def _ols_slope(xs: list[float], ys: list[float]) -> float:
    """Ordinary-least-squares slope of ys on xs (assumes len(xs) == len(ys) >= 2)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / sxx if sxx else 0.0


def loglog_slope_ci(
    x_values: list[float], groups: list[list[float]], *, n_resamples: int = 2000, seed: int = 0x5EED1234
) -> tuple[float, float, float]:
    """(slope, lo95, hi95) of a regression of per-group median against ``x_values``.

    Used for the finite-size scale trend: ``x_values`` are ``log10(N)`` and ``groups[i]`` is the
    list of per-seed penalties at that ``N``. The point slope fits OLS through the group medians;
    the interval resamples seeds *within each group* (the same seeded mulberry32 the median CI uses),
    refits per resample, and takes the 2.5/97.5 percentiles. This puts the scale regression - a
    number the paper reports - inside the reproducible pipeline rather than only in the prose.
    """
    cleaned = [[v for v in g if v is not None] for g in groups]
    if len(x_values) < 2 or any(not g for g in cleaned):
        return 0.0, 0.0, 0.0
    point = _ols_slope(x_values, [statistics.median(g) for g in cleaned])
    rng = seed_state(seed)
    slopes: list[float] = []
    for _ in range(n_resamples):
        meds: list[float] = []
        for g in cleaned:
            m = len(g)
            sample: list[float] = []
            for _ in range(m):
                u, rng = next_u32(rng)
                sample.append(g[u % m])
            meds.append(statistics.median(sample))
        slopes.append(_ols_slope(x_values, meds))
    slopes.sort()
    lo = slopes[int(0.025 * n_resamples)]
    hi = slopes[min(n_resamples - 1, int(0.975 * n_resamples))]
    return point, lo, hi
