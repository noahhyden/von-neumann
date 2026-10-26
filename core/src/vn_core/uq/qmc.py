"""Randomized quasi-Monte Carlo (RQMC): a faster-converging mean estimator."""

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
    """The n un-randomized quasi-random points in [0,1)^k for the chosen sequence."""
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
    """Estimate the mean of ``finding`` by randomized quasi-Monte Carlo."""
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
