"""Tiny, dependency-free, seeded statistics for the paired coordination ensemble."""

from __future__ import annotations

import statistics
from math import comb

from swarm.rng import next_u32, seed_state


def sign_test_positive(xs: list[float]) -> tuple[int, int, float]:
    """(#positive, #nonzero, two-sided sign-test p) for penalties tested against 0."""
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
    """Percentile bootstrap (median, lo95, hi95) for the median of ``xs``."""
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
    """(slope, lo95, hi95) of a regression of per-group median against ``x_values``."""
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
