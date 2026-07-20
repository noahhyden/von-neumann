"""Randomized quasi-Monte Carlo (RQMC): a faster-converging mean estimator.

Plain Monte Carlo places samples randomly; its mean estimate converges as
1/sqrt(N). Quasi-Monte Carlo places them on a low-discrepancy sequence that fills the
input cube far more evenly, so for a smooth, low-dimensional finding the mean
converges close to 1/N - a large win at small N (on the Ishigami mean, QMC at N=64
beat plain MC by ~20x).

Two sequences are available (both from [[sequences]]):
- ``"halton"`` (default) - van der Corput in the first primes. The historical
  default; kept as the default so existing seeded results stay bit-identical.
- ``"sobol"`` - a digital (t,s)-sequence with better equidistribution as the input
  count grows (Halton's high-prime bases correlate; Sobol's do not). Prefer it for
  moderate dimension; opt in explicitly so downstream pinned results do not move
  underneath a caller who did not ask.

The honest catch: QMC points are *not* iid, so the usual `std/sqrt(N)` error bar
is invalid for them - reporting it would be a confident lie. The fix is
**randomization** (Cranley-Patterson): run R independent, seeded random shifts of
the sequence; each is an unbiased QMC estimate, and the spread *between* the R
replicate means is an honest error bar. So RQMC keeps the QMC convergence and
recovers a real confidence interval (CLAUDE.md §1), while staying a deterministic
seeded fold (§7).

Scope: this estimates the **mean** (the headline "X" of a finding). For the full
output distribution / quantile error bars, iid `monte_carlo` stays cleaner - QMC's
guarantees are about integrals, not order statistics. Low-dimensional only: both
sequences have a dimension cap, and more inputs than that raises rather than quietly
returning a bad estimate.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from vn_core.uq.distributions import Distribution
from vn_core.uq.sequences import (
    MAX_HALTON_DIM,
    MAX_SOBOL_DIM,
    halton_point,
    sobol_points,
)

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
    sequence: str  # "halton" or "sobol" - which low-discrepancy sequence was used


def _base_points(sequence: str, n: int, k: int) -> list[tuple[float, ...]]:
    """The n un-randomized quasi-random points in [0,1)^k for the chosen sequence.

    Computed once and reused across replicates (only the Cranley-Patterson shift
    differs per replicate), so the sequence work is not repeated R times.
    """
    if sequence == "halton":
        if k > MAX_HALTON_DIM:
            raise ValueError(
                f"qmc_mean(sequence='halton') is low-dimensional: {k} inputs exceeds the "
                f"{MAX_HALTON_DIM} Halton bases. Try sequence='sobol' or monte_carlo."
            )
        # Start at index 1 to avoid the origin corner (index 0 is all zeros).
        return [halton_point(i, k) for i in range(1, n + 1)]
    if sequence == "sobol":
        if k > MAX_SOBOL_DIM:
            raise ValueError(
                f"qmc_mean(sequence='sobol') is low-dimensional: {k} inputs exceeds the "
                f"{MAX_SOBOL_DIM} tabulated Sobol' dimensions. Use monte_carlo instead."
            )
        # skip=1 drops the Sobol' origin, mirroring Halton's start-at-1 convention.
        return sobol_points(n, k, skip=1)
    raise ValueError(f"unknown sequence {sequence!r}; choose 'halton' or 'sobol'")


def qmc_mean(
    inputs: Mapping[str, Distribution],
    finding: Callable[[Mapping[str, float]], float],
    *,
    n: int,
    seed: int,
    replicates: int = 16,
    sequence: str = "halton",
) -> QMCMean:
    """Estimate the mean of ``finding`` by randomized quasi-Monte Carlo.

    ``n`` points per replicate, ``replicates`` independent seeded shifts; total
    finding evaluations = n * replicates. The mean converges faster than plain
    Monte Carlo for smooth low-dimensional findings, and the error bar comes from
    the spread between replicate means (honest, unlike QMC's invalid iid stderr).

    ``sequence`` picks the low-discrepancy sequence: ``"halton"`` (default, the
    historical behavior - seeded results are unchanged) or ``"sobol"`` (better in
    moderate dimension). Raises if there are more inputs than the chosen sequence's
    dimension cap (high-dimensional QMC is not honest here) or if the finding returns
    a nonfinite value.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if replicates < 2:
        raise ValueError(f"replicates must be >= 2 for an error bar, got {replicates}")
    names = tuple(inputs.keys())
    k = len(names)
    if k < 1:
        raise ValueError("qmc_mean requires at least one input")

    base = _base_points(sequence, n, k)

    rng = random.Random(seed)
    replicate_means: list[float] = []
    for _ in range(replicates):
        # Cranley-Patterson: one random shift per dimension, applied mod 1.
        shift = [rng.random() for _ in range(k)]
        acc = 0.0
        for point in base:
            sample = {
                names[d]: inputs[names[d]].quantile((point[d] + shift[d]) % 1.0)
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
        sequence=sequence,
    )
