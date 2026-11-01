"""Monte Carlo propagation - seeded, deterministic, no wall clock."""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from vn_core.uq.distributions import Distribution


@dataclass(frozen=True)
class MCResult:
    """Empirical distribution of a finding under Monte Carlo input sampling."""

    values: tuple[float, ...]
    n: int
    mean: float
    std: float
    q05: float
    q50: float
    q95: float
    input_names: tuple[str, ...]

    @property
    def error_bar_95(self) -> tuple[float, float]:
        """The 90% central credible interval (q05, q95) - the usual "error bar"."""
        return (self.q05, self.q95)

    @property
    def stderr_of_mean(self) -> float:
        """Standard error of the empirical mean = std / sqrt(N)."""
        if self.n < 2:
            return 0.0
        return self.std / math.sqrt(self.n)


def monte_carlo(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
) -> MCResult:
    """Run n seeded MC evaluations of ``finding`` over sampled ``inputs``."""
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    rng = random.Random(seed)
    names = tuple(inputs.keys())
    values: list[float] = []
    for _ in range(n):
        # Draw a fresh uniform per input (in fixed name order) and push it through that input's inverse CDF; this is the one place the RNG is used.
        sample = {name: inputs[name].quantile(rng.random()) for name in names}
        values.append(finding(sample))
    return summarize(values, names)


def summarize(values: list[float], input_names: tuple[str, ...]) -> MCResult:
    """Build an MCResult (mean/std/quantiles) from a list of finding evaluations."""
    n = len(values)
    if any(math.isnan(v) or math.isinf(v) for v in values):
        raise ValueError("finding returned nan/inf - a nonfinite draw is not honest UQ")
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if n >= 2 else 0.0
    sorted_v = sorted(values)
    q05 = _quantile_of_sorted(sorted_v, 0.05)
    q50 = _quantile_of_sorted(sorted_v, 0.50)
    q95 = _quantile_of_sorted(sorted_v, 0.95)
    return MCResult(
        values=tuple(values),
        n=n,
        mean=mean,
        std=std,
        q05=q05,
        q50=q50,
        q95=q95,
        input_names=input_names,
    )


def _quantile_of_sorted(sorted_v: list[float], q: float) -> float:
    """Linearly interpolated quantile of a pre-sorted sequence."""
    if not sorted_v:
        raise ValueError("cannot take a quantile of an empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"q must be in [0, 1], got {q!r}")
    n = len(sorted_v)
    if n == 1:
        return sorted_v[0]
    h = q * (n - 1)
    lo = int(h)
    hi = min(lo + 1, n - 1)
    frac = h - lo
    return sorted_v[lo] + frac * (sorted_v[hi] - sorted_v[lo])
