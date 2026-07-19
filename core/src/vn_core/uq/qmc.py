"""Randomized quasi-Monte Carlo (RQMC): a faster-converging mean estimator.

Plain Monte Carlo places samples randomly; its mean estimate converges as
1/sqrt(N). Quasi-Monte Carlo places them on a low-discrepancy sequence (here a
Halton sequence) that fills the input cube far more evenly, so for a smooth,
low-dimensional finding the mean converges close to 1/N - a large win at small N
(on the Ishigami mean, Halton at N=64 beat plain MC by ~20x).

The honest catch: QMC points are *not* iid, so the usual `std/sqrt(N)` error bar
is invalid for them - reporting it would be a confident lie. The fix is
**randomization** (Cranley-Patterson): run R independent, seeded random shifts of
the sequence; each is an unbiased QMC estimate, and the spread *between* the R
replicate means is an honest error bar. So RQMC keeps the QMC convergence and
recovers a real confidence interval (CLAUDE.md §1), while staying a deterministic
seeded fold (§7).

Scope: this estimates the **mean** (the headline "X" of a finding). For the full
output distribution / quantile error bars, iid `monte_carlo` stays cleaner - QMC's
guarantees are about integrals, not order statistics. Low-dimensional only: Halton
degrades in high dimension (high-prime bases correlate), so more inputs than the
prime table below raises rather than quietly returning a bad estimate.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from vn_core.uq.distributions import Distribution

# First primes, used as the per-dimension Halton bases. Halton is a low-dimension
# tool; beyond this many inputs the high-prime bases correlate and the sequence is
# no better than random, so we stop rather than mislead.
_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71)

_Z90 = 1.6448536269514722  # 0.95 standard-normal quantile, for the 90% CI


@dataclass(frozen=True)
class QMCMean:
    """A randomized-QMC estimate of a finding's mean, with an honest error bar."""

    mean: float
    stderr: float  # standard error of the mean, from the replicate spread
    ci: tuple[float, float]  # 90% CI on the mean
    n: int  # points per replicate
    replicates: int
    n_evaluations: int  # n * replicates


def _radical_inverse(i: int, base: int) -> float:
    """The base-``base`` radical inverse of ``i`` - the 1-D Halton value in [0, 1)."""
    f = 1.0
    r = 0.0
    while i > 0:
        f /= base
        r += f * (i % base)
        i //= base
    return r


def qmc_mean(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
    replicates: int = 16,
) -> QMCMean:
    """Estimate the mean of ``finding`` by randomized quasi-Monte Carlo.

    ``n`` points per replicate, ``replicates`` independent seeded shifts; total
    finding evaluations = n * replicates. The mean converges faster than plain
    Monte Carlo for smooth low-dimensional findings, and the error bar comes from
    the spread between replicate means (honest, unlike QMC's invalid iid stderr).

    Raises if there are more inputs than available Halton bases (high-dimensional
    QMC is not honest here) or if the finding returns a nonfinite value.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if replicates < 2:
        raise ValueError(f"replicates must be >= 2 for an error bar, got {replicates}")
    names = tuple(inputs.keys())
    k = len(names)
    if k < 1:
        raise ValueError("qmc_mean requires at least one input")
    if k > len(_PRIMES):
        raise ValueError(
            f"qmc_mean is a low-dimensional tool: {k} inputs exceeds the {len(_PRIMES)} "
            "Halton bases. Use monte_carlo for high-dimensional findings."
        )

    rng = random.Random(seed)
    replicate_means: list[float] = []
    for _ in range(replicates):
        # Cranley-Patterson: one random shift per dimension, applied mod 1.
        shift = [rng.random() for _ in range(k)]
        acc = 0.0
        for i in range(1, n + 1):
            sample = {
                names[d]: inputs[names[d]].quantile(
                    (_radical_inverse(i, _PRIMES[d]) + shift[d]) % 1.0
                )
                for d in range(k)
            }
            y = finding(sample)
            if math.isnan(y) or math.isinf(y):
                raise ValueError("finding returned nan/inf - a nonfinite draw is not honest UQ")
            acc += y
        replicate_means.append(acc / n)

    mean = statistics.fmean(replicate_means)
    stderr = statistics.pstdev(replicate_means) / math.sqrt(replicates)
    half = _Z90 * stderr
    return QMCMean(
        mean=mean,
        stderr=stderr,
        ci=(mean - half, mean + half),
        n=n,
        replicates=replicates,
        n_evaluations=n * replicates,
    )
