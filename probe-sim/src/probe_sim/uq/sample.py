"""Monte Carlo propagation - seeded, deterministic, no wall clock.

Draws N independent samples of the inputs from their [[distributions]] and
evaluates a `finding` on each. The seeded RNG is threaded through the sample loop
(CLAUDE.md §7: randomness is state, not a wall clock), so the same (inputs, N,
seed) always returns bit-identical `values`.

`finding` is a plain function `dict[str, float] -> float`. It is the pure fold's
observable in disguise: whatever number would go into the paper as an "X" is what
the caller wraps here so we can report "X, +-Y".
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from probe_sim.uq.distributions import Distribution


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
        """Standard error of the empirical mean = std / sqrt(N).

        A convergence diagnostic separate from the error bar itself: the
        90% CI reports the finding's own spread, while this reports how well
        the *mean* is pinned down by the current sample size. If a caller
        wants a Ndigit-of-mean claim they can trust, they should keep N large
        enough that stderr_of_mean is well below whatever precision they
        want to claim - the honest counterpart to "n=1000 is enough because
        it feels round".
        """
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
    """Run n seeded MC evaluations of ``finding`` over sampled ``inputs``.

    Determinism: a fresh ``random.Random(seed)`` is used, and inputs are consumed
    in insertion order (Python dicts preserve it since 3.7). Same seed, same
    inputs, same finding -> byte-identical ``values``.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    rng = random.Random(seed)
    names = tuple(inputs.keys())
    values: list[float] = []
    for _ in range(n):
        # Draw a fresh uniform per input (in fixed name order), push through each
        # distribution's inverse CDF. This is the one place the RNG is used.
        sample = {name: inputs[name].quantile(rng.random()) for name in names}
        values.append(finding(sample))
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
        input_names=names,
    )


def _quantile_of_sorted(sorted_v: list[float], q: float) -> float:
    """Linearly interpolated quantile of a pre-sorted sequence.

    Uses the "type 7" formula (default in numpy.quantile and R): h = q*(n-1),
    result = v[floor(h)] + (h - floor(h)) * (v[floor(h)+1] - v[floor(h)]).
    Correct on the endpoints and monotonic in q.
    """
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
